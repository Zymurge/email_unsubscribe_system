"""
Email Deleter - Phase 5: Delete subscription emails after successful unsubscribe

This module provides safe email deletion functionality with multiple safety checks:
- Only deletes from successfully unsubscribed subscriptions
- Requires waiting period since unsubscribe (default 7 days)
- Preserves all post-unsubscribe emails (violation evidence)
- Never deletes from subscriptions marked "keep"
- Never deletes if subscription has violations
- Two-phase deletion: IMAP first, then database
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import logging

from sqlalchemy.orm import Session

from src.database.models import EmailMessage, Subscription, Account
from src.email_processor.imap_client import IMAPConnection
from src.config.credentials import CredentialStore


logger = logging.getLogger(__name__)


@dataclass
class DeletionResult:
    """Result of email deletion operation."""
    success: bool
    message: str
    emails_deleted: int = 0
    emails_to_delete: int = 0
    emails_to_preserve: int = 0
    oldest_email_date: Optional[datetime] = None
    newest_email_date: Optional[datetime] = None
    dry_run: bool = False
    
    def __str__(self) -> str:
        if self.dry_run:
            return (
                f"DRY RUN: Would delete {self.emails_to_delete} emails, "
                f"preserve {self.emails_to_preserve} emails"
            )
        else:
            return (
                f"Deleted {self.emails_deleted} emails, "
                f"preserved {self.emails_to_preserve} emails"
            )


class EmailDeleter:
    """
    Handles safe deletion of subscription emails after unsubscribe.
    
    Safety Requirements (ALL must be met):
    1. Subscription successfully unsubscribed
    2. Not marked as "keep"
    3. Waiting period elapsed (default 7 days)
    4. No violations (preserves evidence)
    5. Has unsubscribe link
    """
    
    def __init__(self, session: Session, waiting_days: int = 7):
        """
        Initialize email deleter.
        
        Args:
            session: Database session
            waiting_days: Days to wait after unsubscribe before allowing deletion
        """
        self.session = session
        self.waiting_days = waiting_days
    
    def is_eligible_for_deletion(
        self, 
        subscription: Subscription
    ) -> Tuple[bool, str]:
        """
        Check if subscription is eligible for email deletion.
        
        Args:
            subscription: Subscription to check
            
        Returns:
            Tuple of (eligible: bool, reason: str)
        """
        # Check 1: Not marked as keep
        if subscription.keep_subscription:
            return False, "Subscription marked to keep"
        
        # Check 2: Successfully unsubscribed
        if subscription.unsubscribe_status != 'unsubscribed':
            return False, "Not unsubscribed"
        
        # Check 3: Has unsubscribe date
        if subscription.unsubscribed_at is None:
            return False, "No unsubscribe date recorded"
        
        # Check 4: Waiting period elapsed
        days_since_unsubscribe = (datetime.now() - subscription.unsubscribed_at).days
        if days_since_unsubscribe < self.waiting_days:
            return False, (
                f"Waiting period not elapsed "
                f"({days_since_unsubscribe}/{self.waiting_days} days)"
            )
        
        # Check 5: No violations (preserve evidence)
        if subscription.violation_count > 0:
            return False, (
                f"Has {subscription.violation_count} violations "
                f"(preserve evidence)"
            )
        
        # Check 6: Has unsubscribe link
        if not subscription.unsubscribe_link:
            return False, "No unsubscribe link available"
        
        return True, "Eligible for deletion"
    
    def get_deletable_emails(
        self,
        subscription: Subscription
    ) -> List[EmailMessage]:
        """
        Get list of emails that can be safely deleted.
        
        Only includes emails received BEFORE unsubscribe date.
        Preserves all emails on or after unsubscribe (violation evidence).
        
        Args:
            subscription: Subscription to get deletable emails for
            
        Returns:
            List of EmailMessage objects that can be deleted
        """
        if subscription.unsubscribed_at is None:
            return []
        
        return self.session.query(EmailMessage).filter(
            EmailMessage.account_id == subscription.account_id,
            EmailMessage.sender_email == subscription.sender_email,
            EmailMessage.date_sent < subscription.unsubscribed_at
        ).all()
    
    def delete_subscription_emails(
        self,
        subscription: Subscription,
        dry_run: bool = False
    ) -> DeletionResult:
        """
        Delete emails for a subscription.
        
        Two-phase deletion:
        1. Delete from IMAP server
        2. Delete from database (only if IMAP succeeds)
        
        Args:
            subscription: Subscription to delete emails for
            dry_run: If True, preview without deleting
            
        Returns:
            DeletionResult with operation details
        """
        # Check eligibility
        eligible, reason = self.is_eligible_for_deletion(subscription)
        if not eligible:
            return DeletionResult(
                success=False,
                message=reason,
                dry_run=dry_run
            )
        
        # Get deletable and preservable emails
        deletable_emails = self.get_deletable_emails(subscription)
        
        all_emails = self.session.query(EmailMessage).filter(
            EmailMessage.account_id == subscription.account_id,
            EmailMessage.sender_email == subscription.sender_email
        ).all()
        preserve_count = len(all_emails) - len(deletable_emails)
        
        # Get date range for deletable emails
        oldest_date = None
        newest_date = None
        if deletable_emails:
            dates = [e.date_sent for e in deletable_emails]
            oldest_date = min(dates)
            newest_date = max(dates)
        
        # Dry-run mode: return preview
        if dry_run:
            return DeletionResult(
                success=True,
                message=f"Would delete {len(deletable_emails)} emails",
                emails_to_delete=len(deletable_emails),
                emails_to_preserve=preserve_count,
                oldest_email_date=oldest_date,
                newest_email_date=newest_date,
                dry_run=True
            )
        
        # Handle case where there are no emails to delete
        if not deletable_emails:
            return DeletionResult(
                success=True,
                message="No emails to delete",
                emails_deleted=0,
                emails_to_delete=0,
                emails_to_preserve=preserve_count,
                dry_run=False
            )
        
        # Phase 1: Delete from IMAP
        try:
            uids_to_delete = [email.uid for email in deletable_emails]
            success_count, failure_count, errors = self._delete_from_imap(
                subscription.account,
                uids_to_delete
            )
            
            if failure_count > 0:
                return DeletionResult(
                    success=False,
                    message=f"IMAP deletion failed for {failure_count} emails",
                    emails_to_delete=len(deletable_emails),
                    emails_to_preserve=preserve_count,
                    oldest_email_date=oldest_date,
                    newest_email_date=newest_date,
                    dry_run=False
                )
        
        except Exception as e:
            logger.error(f"IMAP deletion error: {e}")
            return DeletionResult(
                success=False,
                message=f"IMAP error: {str(e)}",
                emails_to_delete=len(deletable_emails),
                emails_to_preserve=preserve_count,
                oldest_email_date=oldest_date,
                newest_email_date=newest_date,
                dry_run=False
            )
        
        # Phase 2: Delete from database (only if IMAP succeeded)
        try:
            for email in deletable_emails:
                self.session.delete(email)
            
            # Update subscription email count
            remaining_count = self.session.query(EmailMessage).filter(
                EmailMessage.account_id == subscription.account_id,
                EmailMessage.sender_email == subscription.sender_email
            ).count()
            subscription.email_count = remaining_count
            
            self.session.commit()
            
            return DeletionResult(
                success=True,
                message=f"Deleted {success_count} emails successfully",
                emails_deleted=success_count,
                emails_to_delete=len(deletable_emails),
                emails_to_preserve=preserve_count,
                oldest_email_date=oldest_date,
                newest_email_date=newest_date,
                dry_run=False
            )
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Database deletion error: {e}")
            return DeletionResult(
                success=False,
                message=f"Database error: {str(e)}",
                emails_deleted=0,
                emails_to_delete=len(deletable_emails),
                emails_to_preserve=preserve_count,
                oldest_email_date=oldest_date,
                newest_email_date=newest_date,
                dry_run=False
            )
    
    def _delete_from_imap(
        self,
        account: Account,
        uids: List[str]
    ) -> Tuple[int, int, List[str]]:
        """
        Delete emails from IMAP server.
        
        Args:
            account: Account to delete from
            uids: List of email UIDs to delete
            
        Returns:
            Tuple of (success_count, failure_count, error_messages)
        """
        success_count = 0
        failure_count = 0
        errors = []
        
        # Get credentials
        cred_store = CredentialStore()
        password = cred_store.get_password(account.email_address)
        
        if not password:
            errors.append(f"No stored password for {account.email_address}")
            return 0, len(uids), errors
        
        # Connect to IMAP
        imap_conn = IMAPConnection(
            account.imap_server,
            account.imap_port,
            use_ssl=True
        )
        
        try:
            # Connect and authenticate
            if not imap_conn.connect(account.email_address, password):
                errors.append("Failed to connect to IMAP server")
                return 0, len(uids), errors
            
            # Select INBOX folder
            if not imap_conn.select_folder('INBOX'):
                errors.append("Failed to select INBOX folder")
                imap_conn.disconnect()
                return 0, len(uids), errors
            
            # Delete each email using UID
            for uid in uids:
                try:
                    # Use UID STORE command to mark for deletion
                    status, _ = imap_conn.connection.uid(
                        'STORE',
                        uid,
                        '+FLAGS',
                        '(\\Deleted)'
                    )
                    if status == 'OK':
                        success_count += 1
                    else:
                        failure_count += 1
                        errors.append(f"UID {uid}: STORE command failed")
                        logger.error(f"Failed to delete UID {uid}: status={status}")
                except Exception as e:
                    failure_count += 1
                    errors.append(f"UID {uid}: {str(e)}")
                    logger.error(f"Failed to delete UID {uid}: {e}")
            
            # Expunge to permanently remove marked messages
            try:
                imap_conn.connection.expunge()
            except Exception as e:
                logger.error(f"Expunge failed: {e}")
                # Don't fail the operation if expunge fails after marking
            
            # Disconnect
            imap_conn.disconnect()
            
        except Exception as e:
            logger.error(f"IMAP operation error: {e}")
            errors.append(f"IMAP error: {str(e)}")
            try:
                imap_conn.disconnect()
            except:
                pass
            return success_count, len(uids) - success_count, errors
        
        return success_count, failure_count, errors
