"""
Subscription detection from email messages.

This module analyzes stored email messages to create and maintain Subscription records.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..database.models import EmailMessage, Subscription

# Set up logging
logger = logging.getLogger(__name__)


class SubscriptionDetector:
    """Detects subscriptions from stored email messages."""
    
    # Marketing keywords for confidence scoring
    MARKETING_KEYWORDS = {
        'sale', 'deal', 'offer', 'discount', 'promo', 'coupon',
        'newsletter', 'update', 'news', 'weekly', 'monthly',
        'limited time', 'exclusive', 'special', 'free'
    }
    
    def detect_subscriptions_from_emails(self, account_id: int, session: Session) -> Dict[str, int]:
        """
        Detect subscriptions from stored email messages.
        
        Args:
            account_id: Account to process emails for
            session: Database session
            
        Returns:
            Dict with counts: {'created': int, 'updated': int, 'skipped': int}
        """
        # Get all emails for this account (process all for now - optimization later)
        emails = session.query(EmailMessage).filter(
            EmailMessage.account_id == account_id
        ).all()
        
        # Group emails by sender and validate
        emails_by_sender, skipped_count = self._group_and_validate_emails(emails)
        
        created = 0
        updated = 0
        
        # Process each sender's emails
        for sender_email, sender_emails in emails_by_sender.items():
            # Check if subscription already exists
            existing_subscription = session.query(Subscription).filter(
                and_(
                    Subscription.account_id == account_id,
                    Subscription.sender_email == sender_email
                )
            ).first()
            
            if existing_subscription:
                # Update existing subscription
                self._update_subscription(existing_subscription, sender_emails, session)
                updated += 1
            else:
                # Create new subscription
                self._create_subscription(account_id, sender_email, sender_emails, session)
                created += 1
        
        session.commit()
        
        return {
            'created': created,
            'updated': updated,
            'skipped': skipped_count
        }
    
    def _group_and_validate_emails(self, emails: List[EmailMessage]) -> Tuple[Dict[str, List[EmailMessage]], int]:
        """
        Group emails by sender and validate data.
        
        Returns:
            Tuple of (valid_emails_by_sender, skipped_count)
        """
        emails_by_sender = defaultdict(list)
        skipped_count = 0
        
        for email in emails:
            # Validate required data
            if not self._is_valid_email_data(email):
                logger.warning(f"Skipping email {email.message_id}: insufficient data")
                skipped_count += 1
                continue
                
            emails_by_sender[email.sender_email].append(email)
        
        return dict(emails_by_sender), skipped_count
    
    def _is_valid_email_data(self, email: EmailMessage) -> bool:
        """Check if email has sufficient data for processing."""
        # Required: sender_email and date_sent
        if not email.sender_email or email.sender_email.strip() == "":
            return False
        if not email.date_sent:
            return False
        
        # Basic email format validation
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email.sender_email):
            return False
            
        return True
    
    def _create_subscription(self, account_id: int, sender_email: str, 
                           emails: List[EmailMessage], session: Session) -> None:
        """Create a new subscription from email data."""
        # Aggregate email data
        email_data = self._aggregate_email_data(emails)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(email_data)
        
        # Extract domain
        sender_domain = self._extract_sender_domain(sender_email)
        
        # Get sender name (use most recent non-null name)
        sender_name = None
        for email in reversed(emails):  # Most recent first
            if email.sender_name:
                sender_name = email.sender_name
                break
        
        # Create subscription
        subscription = Subscription(
            account_id=account_id,
            sender_email=sender_email,
            sender_name=sender_name,
            sender_domain=sender_domain,
            email_count=email_data['count'],
            confidence_score=confidence_score,
            discovered_at=email_data['earliest_date'],
            last_seen=email_data['latest_date']
        )
        
        session.add(subscription)
    
    def _update_subscription(self, subscription: Subscription, 
                           emails: List[EmailMessage], session: Session) -> None:
        """Update existing subscription with new email data."""
        # Get ALL emails for this sender from database
        all_emails = session.query(EmailMessage).filter(
            and_(
                EmailMessage.account_id == subscription.account_id,
                EmailMessage.sender_email == subscription.sender_email
            )
        ).all()
        
        # Aggregate email data from database
        email_data = self._aggregate_email_data(all_emails)
        
        # Update email count to reflect all emails in database for this sender
        # Database is authoritative - subscription should reflect actual email count
        subscription.email_count = email_data['count']
        
        # Update dates
        subscription.last_seen = max(subscription.last_seen or email_data['earliest_date'], 
                                   email_data['latest_date'])
        
        if subscription.discovered_at is None or email_data['earliest_date'] < subscription.discovered_at:
            subscription.discovered_at = email_data['earliest_date']
        
        # Recalculate confidence score only for active subscriptions
        if subscription.unsubscribe_status == 'active':
            # Use the higher count for confidence calculation
            confidence_email_data = email_data.copy()
            confidence_email_data['count'] = subscription.email_count
            subscription.confidence_score = self._calculate_confidence_score(confidence_email_data)
        
        # Update sender name if we have a better one
        for email in reversed(all_emails):
            if email.sender_name and not subscription.sender_name:
                subscription.sender_name = email.sender_name
                break
    
    def _aggregate_email_data(self, emails: List[EmailMessage]) -> Dict[str, Any]:
        """Aggregate data from multiple emails from same sender."""
        if not emails:
            return {}
        
        # Sort by date
        sorted_emails = sorted(emails, key=lambda e: e.date_sent)
        
        # Collect all subjects for keyword analysis
        subjects = [email.subject or "" for email in emails]
        
        # Check for unsubscribe information
        has_unsubscribe = any(
            email.has_unsubscribe_header or email.has_unsubscribe_link 
            for email in emails
        )
        
        return {
            'count': len(emails),
            'earliest_date': sorted_emails[0].date_sent,
            'latest_date': sorted_emails[-1].date_sent,
            'subjects': subjects,
            'has_unsubscribe': has_unsubscribe
        }
    
    def _calculate_confidence_score(self, email_data: Dict[str, Any]) -> int:
        """Calculate confidence score using deterministic algorithm."""
        count = email_data['count']
        
        # Base score by email count
        if count == 1:
            base_score = 15
        elif count <= 3:
            base_score = 35
        elif count <= 5:
            base_score = 55
        elif count <= 10:
            base_score = 75
        else:  # 11+
            base_score = 85
        
        # Apply bonuses
        bonus = 0
        
        # Unsubscribe information bonus
        if email_data.get('has_unsubscribe', False):
            bonus += 15
        
        # Marketing keywords bonus
        if self._has_marketing_keywords(email_data.get('subjects', [])):
            bonus += 10
        
        # TODO: Regular pattern bonus (+10) - implement in future iteration
        
        # Cap at 100
        return min(base_score + bonus, 100)
    
    def _has_marketing_keywords(self, subjects: List[str]) -> bool:
        """Check if any subject contains marketing keywords."""
        if not subjects:
            return False
        
        # Combine all subjects into one text for analysis
        combined_text = " ".join(subjects).lower()
        
        # Strong marketing terms that indicate promotional content
        strong_marketing_terms = {'sale', 'deal', 'offer', 'discount', 'promo', 'coupon', 
                                'limited time', 'exclusive', 'special', 'free'}
        
        # Check for strong marketing terms first (word boundaries)
        for term in strong_marketing_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', combined_text):
                return True
        
        # For weaker terms, require multiple DIFFERENT keywords in the combined text
        weak_marketing_terms = {'newsletter', 'update', 'news', 'weekly', 'monthly'}
        
        # Count unique weak marketing terms using word boundaries
        unique_weak_terms = set()
        for term in weak_marketing_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', combined_text):
                unique_weak_terms.add(term)
        
        # Require at least 2 different weak marketing terms
        return len(unique_weak_terms) >= 2
    
    def _extract_sender_domain(self, sender_email: str) -> str:
        """Extract full domain from sender email."""
        try:
            # Split on @ and take the domain part
            domain = sender_email.split('@')[1]
            return domain
        except (IndexError, AttributeError):
            logger.warning(f"Could not extract domain from: {sender_email}")
            return ""