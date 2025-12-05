"""
TDD Tests for Email Deletion Feature (Phase 5)

This test suite defines the specifications for deleting subscription emails
after successful unsubscribe. Following the Red-Green-Refactor cycle.

Safety Requirements (ALL must be met):
1. Subscription must be successfully unsubscribed
2. Subscription cannot be marked as "keep"
3. Waiting period must have elapsed (default 7 days)
4. Subscription must have NO violations
5. Must have valid unsubscribe link

Deletion Rules:
- Only delete emails received BEFORE unsubscribe date
- Preserve ALL emails received ON or AFTER unsubscribe date
- Two-phase deletion: IMAP first, then database
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Account, EmailMessage, Subscription
from src.email_processor.email_deleter import EmailDeleter, DeletionResult


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def account(db_session):
    """Create test account."""
    account = Account(
        email_address='test@example.com',
        provider='test',
        imap_server='imap.example.com',
        imap_port=993
    )
    db_session.add(account)
    db_session.commit()
    return account


@pytest.fixture
def subscription_ready_for_deletion(db_session, account):
    """
    Create subscription that meets all deletion criteria:
    - Successfully unsubscribed
    - Not marked keep
    - Unsubscribed 10 days ago (past 7-day waiting period)
    - No violations
    - Has unsubscribe link
    """
    sub = Subscription(
        account_id=account.id,
        sender_email='marketing@company.com',
        sender_name='Company Marketing',
        sender_domain='company.com',
        email_count=100,
        confidence_score=85,
        unsubscribe_status='unsubscribed',
        unsubscribed_at=datetime.now() - timedelta(days=10),
        keep_subscription=False,
        violation_count=0,
        unsubscribe_link='https://company.com/unsubscribe?token=xyz',
        unsubscribe_method='http_get'
    )
    db_session.add(sub)
    db_session.commit()
    return sub


@pytest.fixture
def emails_before_and_after_unsubscribe(db_session, subscription_ready_for_deletion):
    """
    Create emails before and after unsubscribe date.
    - 3 emails BEFORE unsubscribe (should be deleted)
    - 2 emails AFTER unsubscribe (should be preserved)
    """
    unsub_date = subscription_ready_for_deletion.unsubscribed_at
    
    # Emails before unsubscribe (should be deleted)
    email1 = EmailMessage(
        account_id=subscription_ready_for_deletion.account_id,
        message_id='<msg1@company.com>',
        uid=1001,
        sender_email='marketing@company.com',
        subject='Old Marketing Email 1',
        date_sent=unsub_date - timedelta(days=5),
        folder='INBOX'
    )
    email2 = EmailMessage(
        account_id=subscription_ready_for_deletion.account_id,
        message_id='<msg2@company.com>',
        uid=1002,
        sender_email='marketing@company.com',
        subject='Old Marketing Email 2',
        date_sent=unsub_date - timedelta(days=3),
        folder='INBOX'
    )
    email3 = EmailMessage(
        account_id=subscription_ready_for_deletion.account_id,
        message_id='<msg3@company.com>',
        uid=1003,
        sender_email='marketing@company.com',
        subject='Old Marketing Email 3',
        date_sent=unsub_date - timedelta(days=1),
        folder='INBOX'
    )
    
    # Emails after unsubscribe (should be preserved - violations)
    email4 = EmailMessage(
        account_id=subscription_ready_for_deletion.account_id,
        message_id='<msg4@company.com>',
        uid=1004,
        sender_email='marketing@company.com',
        subject='Violation Email 1',
        date_sent=unsub_date + timedelta(days=2),
        folder='INBOX'
    )
    email5 = EmailMessage(
        account_id=subscription_ready_for_deletion.account_id,
        message_id='<msg5@company.com>',
        uid=1005,
        sender_email='marketing@company.com',
        subject='Violation Email 2',
        date_sent=unsub_date + timedelta(days=5),
        folder='INBOX'
    )
    
    db_session.add_all([email1, email2, email3, email4, email5])
    db_session.commit()
    
    return {
        'before': [email1, email2, email3],
        'after': [email4, email5]
    }


# ============================================================================
# ELIGIBILITY CHECK TESTS
# ============================================================================

class TestEligibilityChecks:
    """Test all safety checks for deletion eligibility."""
    
    def test_eligible_subscription_passes_all_checks(
        self, db_session, subscription_ready_for_deletion
    ):
        """Subscription meeting all criteria should be eligible."""
        deleter = EmailDeleter(db_session)
        eligible, reason = deleter.is_eligible_for_deletion(
            subscription_ready_for_deletion
        )
        
        assert eligible is True
        assert reason == "Eligible for deletion"
    
    def test_kept_subscription_not_eligible(self, db_session, subscription_ready_for_deletion):
        """Subscription marked 'keep' should not be eligible."""
        subscription_ready_for_deletion.keep_subscription = True
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        eligible, reason = deleter.is_eligible_for_deletion(
            subscription_ready_for_deletion
        )
        
        assert eligible is False
        assert "marked to keep" in reason.lower()
    
    def test_not_unsubscribed_not_eligible(self, db_session, account):
        """Subscription not unsubscribed should not be eligible."""
        sub = Subscription(
            account_id=account.id,
            sender_email='active@company.com',
            sender_domain='company.com',
            email_count=50,
            confidence_score=70,
            unsubscribe_status='active',  # Not unsubscribed
            keep_subscription=False,
            violation_count=0,
            unsubscribe_link='https://company.com/unsub'
        )
        db_session.add(sub)
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        eligible, reason = deleter.is_eligible_for_deletion(sub)
        
        assert eligible is False
        assert "not unsubscribed" in reason.lower()
    
    def test_no_unsubscribe_date_not_eligible(
        self, db_session, subscription_ready_for_deletion
    ):
        """Subscription without unsubscribe date should not be eligible."""
        subscription_ready_for_deletion.unsubscribed_at = None
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        eligible, reason = deleter.is_eligible_for_deletion(
            subscription_ready_for_deletion
        )
        
        assert eligible is False
        assert "no unsubscribe date" in reason.lower()
    
    def test_waiting_period_not_elapsed_not_eligible(self, db_session, account):
        """Subscription unsubscribed recently should not be eligible."""
        sub = Subscription(
            account_id=account.id,
            sender_email='recent@company.com',
            sender_domain='company.com',
            email_count=30,
            confidence_score=75,
            unsubscribe_status='unsubscribed',
            unsubscribed_at=datetime.now() - timedelta(days=3),  # Only 3 days ago
            keep_subscription=False,
            violation_count=0,
            unsubscribe_link='https://company.com/unsub'
        )
        db_session.add(sub)
        db_session.commit()
        
        deleter = EmailDeleter(db_session, waiting_days=7)
        eligible, reason = deleter.is_eligible_for_deletion(sub)
        
        assert eligible is False
        assert "waiting period" in reason.lower()
        assert "3/7" in reason  # Shows days elapsed
    
    def test_custom_waiting_period(self, db_session, subscription_ready_for_deletion):
        """Should respect custom waiting period."""
        # Subscription is 10 days old
        deleter = EmailDeleter(db_session, waiting_days=14)  # Require 14 days
        eligible, reason = deleter.is_eligible_for_deletion(
            subscription_ready_for_deletion
        )
        
        assert eligible is False
        assert "10/14" in reason
    
    def test_has_violations_not_eligible(self, db_session, subscription_ready_for_deletion):
        """Subscription with violations should not be eligible."""
        subscription_ready_for_deletion.violation_count = 3
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        eligible, reason = deleter.is_eligible_for_deletion(
            subscription_ready_for_deletion
        )
        
        assert eligible is False
        assert "3 violations" in reason.lower()
        assert "preserve evidence" in reason.lower()
    
    def test_no_unsubscribe_link_not_eligible(
        self, db_session, subscription_ready_for_deletion
    ):
        """Subscription without unsubscribe link should not be eligible."""
        subscription_ready_for_deletion.unsubscribe_link = None
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        eligible, reason = deleter.is_eligible_for_deletion(
            subscription_ready_for_deletion
        )
        
        assert eligible is False
        assert "no unsubscribe link" in reason.lower()
    
    def test_empty_unsubscribe_link_not_eligible(
        self, db_session, subscription_ready_for_deletion
    ):
        """Subscription with empty unsubscribe link should not be eligible."""
        subscription_ready_for_deletion.unsubscribe_link = ''
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        eligible, reason = deleter.is_eligible_for_deletion(
            subscription_ready_for_deletion
        )
        
        assert eligible is False
        assert "no unsubscribe link" in reason.lower()


# ============================================================================
# EMAIL SELECTION TESTS
# ============================================================================

class TestEmailSelection:
    """Test identification of deletable vs preservable emails."""
    
    def test_get_deletable_emails_only_before_unsubscribe(
        self, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should return only emails before unsubscribe date."""
        deleter = EmailDeleter(db_session)
        deletable = deleter.get_deletable_emails(subscription_ready_for_deletion)
        
        assert len(deletable) == 3
        for email in deletable:
            assert email.date_sent < subscription_ready_for_deletion.unsubscribed_at
    
    def test_get_deletable_emails_preserves_after_unsubscribe(
        self, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should not return emails on or after unsubscribe date."""
        deleter = EmailDeleter(db_session)
        deletable = deleter.get_deletable_emails(subscription_ready_for_deletion)
        
        deletable_uids = [e.uid for e in deletable]
        
        # Verify violation emails are NOT in deletable list
        assert '1004' not in deletable_uids
        assert '1005' not in deletable_uids
    
    def test_get_deletable_emails_empty_when_all_after_unsubscribe(
        self, db_session, account
    ):
        """Should return empty list if all emails after unsubscribe."""
        unsub_date = datetime.now() - timedelta(days=10)
        sub = Subscription(
            account_id=account.id,
            sender_email='violations@company.com',
            sender_domain='company.com',
            email_count=2,
            confidence_score=80,
            unsubscribe_status='unsubscribed',
            unsubscribed_at=unsub_date,
            keep_subscription=False,
            violation_count=2,
            unsubscribe_link='https://company.com/unsub'
        )
        db_session.add(sub)
        db_session.commit()
        
        # Add emails only AFTER unsubscribe
        email1 = EmailMessage(
            account_id=account.id,
            message_id='<msg2001@company.com>',
            uid=2001,
            sender_email='violations@company.com',
            subject='After unsub',
            date_sent=unsub_date + timedelta(days=1),
            folder='INBOX'
        )
        email2 = EmailMessage(
            account_id=account.id,
            message_id='<msg2002@company.com>',
            uid=2002,
            sender_email='violations@company.com',
            subject='After unsub 2',
            date_sent=unsub_date + timedelta(days=3),
            folder='INBOX'
        )
        db_session.add_all([email1, email2])
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        deletable = deleter.get_deletable_emails(sub)
        
        assert len(deletable) == 0
    
    def test_get_deletable_emails_handles_exact_unsubscribe_time(
        self, db_session, account
    ):
        """Email at exact unsubscribe time should be preserved."""
        unsub_date = datetime.now() - timedelta(days=10)
        sub = Subscription(
            account_id=account.id,
            sender_email='exact@company.com',
            sender_domain='company.com',
            email_count=2,
            confidence_score=80,
            unsubscribe_status='unsubscribed',
            unsubscribed_at=unsub_date,
            keep_subscription=False,
            violation_count=0,
            unsubscribe_link='https://company.com/unsub'
        )
        db_session.add(sub)
        db_session.commit()
        
        # Email at exact unsubscribe time
        email_exact = EmailMessage(
            account_id=account.id,
            message_id='<msg3001@company.com>',
            uid=3001,
            sender_email='exact@company.com',
            subject='Exact time',
            date_sent=unsub_date,  # Exact same time
            folder='INBOX'
        )
        db_session.add(email_exact)
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        deletable = deleter.get_deletable_emails(sub)
        
        # Should NOT include email at exact time (>= preserves it)
        assert len(deletable) == 0


# ============================================================================
# DRY-RUN MODE TESTS
# ============================================================================

class TestDryRunMode:
    """Test dry-run preview functionality."""
    
    def test_dry_run_returns_preview_without_deletion(
        self, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Dry-run should return preview without deleting anything."""
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=True
        )
        
        assert result.success is True
        assert result.dry_run is True
        assert result.emails_to_delete == 3
        assert result.emails_to_preserve == 2
        assert "would delete" in result.message.lower()
        
        # Verify no emails were actually deleted
        remaining = db_session.query(EmailMessage).filter(
            EmailMessage.account_id == subscription_ready_for_deletion.account_id,
            EmailMessage.sender_email == subscription_ready_for_deletion.sender_email
        ).count()
        assert remaining == 5
    
    def test_dry_run_shows_date_range(
        self, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Dry-run should include date range of deletable emails."""
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=True
        )
        
        assert result.oldest_email_date is not None
        assert result.newest_email_date is not None
        assert result.oldest_email_date < result.newest_email_date
    
    def test_dry_run_fails_on_ineligible_subscription(
        self, db_session, subscription_ready_for_deletion
    ):
        """Dry-run should still check eligibility."""
        subscription_ready_for_deletion.keep_subscription = True
        db_session.commit()
        
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=True
        )
        
        assert result.success is False
        assert "marked to keep" in result.message.lower()


# ============================================================================
# IMAP DELETION TESTS
# ============================================================================

class TestImapDeletion:
    """Test IMAP email deletion operations."""
    
    @patch('src.email_processor.email_deleter.CredentialStore')
    @patch('src.email_processor.email_deleter.IMAPConnection')
    def test_delete_from_imap_success(
        self, mock_imap_class, mock_cred_store_class, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should successfully delete emails from IMAP."""
        # Mock credential store
        mock_cred_store = MagicMock()
        mock_cred_store_class.return_value = mock_cred_store
        mock_cred_store.get_password.return_value = "test_password"
        
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        
        # Mock successful connection and folder selection
        mock_imap.connect.return_value = True
        mock_imap.select_folder.return_value = True
        
        # Mock successful UID STORE operations
        mock_imap.connection.uid.return_value = ('OK', None)
        
        deleter = EmailDeleter(db_session)
        deletable = deleter.get_deletable_emails(subscription_ready_for_deletion)
        
        success_count, failure_count, errors = deleter._delete_from_imap(
            subscription_ready_for_deletion.account,
            [e.uid for e in deletable]
        )
        
        assert success_count == 3
        assert failure_count == 0
        assert len(errors) == 0
        assert mock_imap.connection.uid.call_count == 3
        assert mock_imap.connection.expunge.called
    
    @patch('src.email_processor.email_deleter.CredentialStore')
    @patch('src.email_processor.email_deleter.IMAPConnection')
    def test_delete_from_imap_partial_failure(
        self, mock_imap_class, mock_cred_store_class, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should handle partial IMAP deletion failures."""
        # Mock credential store
        mock_cred_store = MagicMock()
        mock_cred_store_class.return_value = mock_cred_store
        mock_cred_store.get_password.return_value = "test_password"
        
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        
        # Mock successful connection
        mock_imap.connect.return_value = True
        mock_imap.select_folder.return_value = True
        
        # Make second UID fail
        def uid_side_effect(command, uid, *args):
            if uid == 1002:  # UID is now an integer
                raise Exception("IMAP error for UID 1002")
            return ('OK', None)
        
        mock_imap.connection.uid.side_effect = uid_side_effect
        
        deleter = EmailDeleter(db_session)
        deletable = deleter.get_deletable_emails(subscription_ready_for_deletion)
        
        success_count, failure_count, errors = deleter._delete_from_imap(
            subscription_ready_for_deletion.account,
            [e.uid for e in deletable]
        )
        
        assert success_count == 2
        assert failure_count == 1
        assert len(errors) == 1
        assert "1002" in errors[0]


# ============================================================================
# DATABASE DELETION TESTS
# ============================================================================

class TestDatabaseDeletion:
    """Test database record deletion."""
    
    @patch('src.email_processor.email_deleter.CredentialStore')
    @patch('src.email_processor.email_deleter.IMAPConnection')
    def test_full_deletion_success(
        self, mock_imap_class, mock_cred_store_class, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should delete from IMAP and database successfully."""
        # Mock credential store
        mock_cred_store = MagicMock()
        mock_cred_store_class.return_value = mock_cred_store
        mock_cred_store.get_password.return_value = "test_password"
        
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        
        # Mock successful IMAP operations
        mock_imap.connect.return_value = True
        mock_imap.select_folder.return_value = True
        mock_imap.connection.uid.return_value = ('OK', None)
        
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=False
        )
        
        assert result.success is True
        assert result.emails_deleted == 3
        
        # Verify database deletions
        remaining = db_session.query(EmailMessage).filter(
            EmailMessage.account_id == subscription_ready_for_deletion.account_id,
            EmailMessage.sender_email == subscription_ready_for_deletion.sender_email
        ).all()
        
        assert len(remaining) == 2
        # Verify only violation emails remain
        remaining_uids = [e.uid for e in remaining]
        assert 1004 in remaining_uids
        assert 1005 in remaining_uids
    
    @patch('src.email_processor.email_deleter.CredentialStore')
    @patch('src.email_processor.email_deleter.IMAPConnection')
    def test_database_deletion_only_after_imap_success(
        self, mock_imap_class, mock_cred_store_class, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should not delete from database if IMAP fails."""
        # Mock credential store
        mock_cred_store = MagicMock()
        mock_cred_store_class.return_value = mock_cred_store
        mock_cred_store.get_password.return_value = "test_password"
        
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        
        # Mock successful connection but failed UID operations
        mock_imap.connect.return_value = True
        mock_imap.select_folder.return_value = True
        mock_imap.connection.uid.side_effect = Exception("IMAP connection lost")
        
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=False
        )
        
        assert result.success is False
        assert "IMAP deletion failed" in result.message
        
        # Verify NO database deletions occurred
        remaining = db_session.query(EmailMessage).filter(
            EmailMessage.account_id == subscription_ready_for_deletion.account_id,
            EmailMessage.sender_email == subscription_ready_for_deletion.sender_email
        ).count()
        
        assert remaining == 5  # All emails still there
    
    @patch('src.email_processor.email_deleter.CredentialStore')
    @patch('src.email_processor.email_deleter.IMAPConnection')
    def test_subscription_email_count_updated(
        self, mock_imap_class, mock_cred_store_class, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should update subscription email_count after deletion."""
        # Mock credential store
        mock_cred_store = MagicMock()
        mock_cred_store_class.return_value = mock_cred_store
        mock_cred_store.get_password.return_value = "test_password"
        
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        
        # Mock successful IMAP operations
        mock_imap.connect.return_value = True
        mock_imap.select_folder.return_value = True
        mock_imap.connection.uid.return_value = ('OK', None)
        mock_imap_class.return_value = mock_imap
        
        original_count = subscription_ready_for_deletion.email_count
        
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=False
        )
        
        assert result.success is True
        
        # Refresh subscription from database
        db_session.refresh(subscription_ready_for_deletion)
        
        # Email count should be updated to reflect remaining emails
        assert subscription_ready_for_deletion.email_count == 2


# ============================================================================
# RESULT OBJECT TESTS
# ============================================================================

class TestDeletionResult:
    """Test DeletionResult data structure."""
    
    def test_result_contains_all_required_fields(self):
        """DeletionResult should have all necessary fields."""
        result = DeletionResult(
            success=True,
            message="Deleted 10 emails",
            emails_deleted=10,
            emails_to_delete=10,
            emails_to_preserve=2,
            oldest_email_date=datetime.now() - timedelta(days=30),
            newest_email_date=datetime.now() - timedelta(days=1),
            dry_run=False
        )
        
        assert result.success is True
        assert result.message == "Deleted 10 emails"
        assert result.emails_deleted == 10
        assert result.emails_to_delete == 10
        assert result.emails_to_preserve == 2
        assert result.oldest_email_date is not None
        assert result.newest_email_date is not None
        assert result.dry_run is False
    
    def test_result_string_representation(self):
        """DeletionResult should have readable string representation."""
        result = DeletionResult(
            success=True,
            message="Success",
            emails_deleted=5,
            emails_to_delete=5,
            emails_to_preserve=1,
            dry_run=False
        )
        
        result_str = str(result)
        assert "5" in result_str
        assert "1" in result_str


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_subscription_with_no_emails(self, db_session, subscription_ready_for_deletion):
        """Should handle subscription with no emails gracefully."""
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=False
        )
        
        assert result.success is True
        assert result.emails_deleted == 0
        assert "no emails" in result.message.lower() or result.emails_deleted == 0
    
    @patch('src.email_processor.email_deleter.CredentialStore')
    @patch('src.email_processor.email_deleter.IMAPConnection')
    def test_imap_connection_failure(
        self, mock_imap_class, mock_cred_store_class, db_session, subscription_ready_for_deletion,
        emails_before_and_after_unsubscribe
    ):
        """Should handle IMAP connection failures gracefully."""
        # Mock credential store
        mock_cred_store = MagicMock()
        mock_cred_store_class.return_value = mock_cred_store
        mock_cred_store.get_password.return_value = "test_password"
        
        # Make IMAP connection throw exception
        mock_imap_class.side_effect = Exception("Connection refused")
        
        deleter = EmailDeleter(db_session)
        result = deleter.delete_subscription_emails(
            subscription_ready_for_deletion,
            dry_run=False
        )
        
        assert result.success is False
        assert "connection" in result.message.lower() or "error" in result.message.lower()
    
    def test_zero_waiting_days(self, db_session, account):
        """Should allow zero waiting days for immediate deletion."""
        sub = Subscription(
            account_id=account.id,
            sender_email='immediate@company.com',
            sender_domain='company.com',
            email_count=10,
            confidence_score=80,
            unsubscribe_status='unsubscribed',
            unsubscribed_at=datetime.now(),  # Just now
            keep_subscription=False,
            violation_count=0,
            unsubscribe_link='https://company.com/unsub'
        )
        db_session.add(sub)
        db_session.commit()
        
        deleter = EmailDeleter(db_session, waiting_days=0)
        eligible, reason = deleter.is_eligible_for_deletion(sub)
        
        assert eligible is True
