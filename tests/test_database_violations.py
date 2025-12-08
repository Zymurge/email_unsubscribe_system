"""
Tests for unsubscribe violation tracking functionality.
"""

import sys
import pytest
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.database.models import Account, EmailMessage, Subscription
from src.database import DatabaseManager
from src.database.violations import ViolationReporter, generate_violation_report


def test_subscription_violation_methods():
    """Test the violation tracking methods on Subscription model."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        # Create test account
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create subscription (initially active)
        subscription = Subscription(
            account_id=account.id,
            sender_email="newsletter@store.com",
            sender_name="Store Newsletter"
        )
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        
        # Initially no violations
        assert not subscription.has_violations()
        assert subscription.unsubscribe_status == 'active'
        assert subscription.emails_after_unsubscribe == 0
        assert subscription.violation_count == 0
        
        # Mark as unsubscribed
        unsubscribe_time = datetime(2024, 1, 1, 12, 0, 0)
        subscription.mark_unsubscribed(unsubscribe_time)
        
        assert subscription.unsubscribe_status == 'unsubscribed'
        assert subscription.unsubscribed_at == unsubscribe_time
        assert not subscription.is_active
        
        # Test violation detection
        before_unsubscribe = datetime(2023, 12, 31, 12, 0, 0)
        after_unsubscribe = datetime(2024, 1, 2, 12, 0, 0)
        
        assert not subscription.is_violation_email(before_unsubscribe)
        assert subscription.is_violation_email(after_unsubscribe)
        
        # Record violations
        violation1 = datetime(2024, 1, 3, 10, 0, 0)
        violation2 = datetime(2024, 1, 5, 14, 0, 0)
        
        subscription.record_violation(violation1)
        assert subscription.emails_after_unsubscribe == 1
        assert subscription.violation_count == 1
        assert subscription.last_violation_at == violation1
        assert subscription.has_violations()
        
        subscription.record_violation(violation2)
        assert subscription.emails_after_unsubscribe == 2
        assert subscription.violation_count == 2
        assert subscription.last_violation_at == violation2  # Should update to latest
        
        # Recording a non-violation shouldn't change counters
        subscription.record_violation(before_unsubscribe)
        assert subscription.emails_after_unsubscribe == 2
        assert subscription.violation_count == 2


def test_violation_reporter_summary():
    """Test ViolationReporter summary functionality."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        # Create test account
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create subscriptions with violations
        sub1 = Subscription(
            account_id=account.id,
            sender_email="spammer1@bad.com",
            sender_name="Bad Sender 1",
            unsubscribe_status='unsubscribed',
            unsubscribed_at=datetime(2024, 1, 1),
            emails_after_unsubscribe=5,
            violation_count=3,
            last_violation_at=datetime(2024, 1, 10)
        )
        
        sub2 = Subscription(
            account_id=account.id,
            sender_email="spammer2@bad.com",
            sender_name="Bad Sender 2",
            unsubscribe_status='unsubscribed',
            unsubscribed_at=datetime(2024, 1, 2),
            emails_after_unsubscribe=3,
            violation_count=2,
            last_violation_at=datetime(2024, 1, 8)
        )
        
        # Non-violating subscription
        sub3 = Subscription(
            account_id=account.id,
            sender_email="good@sender.com",
            sender_name="Good Sender",
            unsubscribe_status='unsubscribed',
            unsubscribed_at=datetime(2024, 1, 3),
            emails_after_unsubscribe=0,
            violation_count=0
        )
        
        session.add_all([sub1, sub2, sub3])
        session.commit()
        
        # Test summary
        reporter = ViolationReporter(session)
        summary = reporter.get_violations_summary(account.id)
        
        assert summary['total_violations'] == 2  # Only sub1 and sub2
        assert summary['total_violation_emails'] == 8  # 5 + 3
        assert len(summary['violations_by_sender']) == 2
        
        # Check specific violation details
        violation_details = summary['violations_by_sender']
        spammer1 = next(v for v in violation_details if v['sender_email'] == 'spammer1@bad.com')
        assert spammer1['violation_count'] == 3
        assert spammer1['emails_after_unsubscribe'] == 5
        assert spammer1['days_since_unsubscribe'] == 9  # Jan 10 - Jan 1


def test_violation_reporter_recent_violations():
    """Test recent violations functionality."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        now = datetime.now()
        recent_violation = now - timedelta(days=3)
        old_violation = now - timedelta(days=10)
        
        # Recent violator
        sub1 = Subscription(
            account_id=account.id,
            sender_email="recent@bad.com",
            unsubscribe_status='unsubscribed',
            violation_count=1,
            last_violation_at=recent_violation
        )
        
        # Old violator
        sub2 = Subscription(
            account_id=account.id,
            sender_email="old@bad.com",
            unsubscribe_status='unsubscribed',
            violation_count=1,
            last_violation_at=old_violation
        )
        
        session.add_all([sub1, sub2])
        session.commit()
        
        reporter = ViolationReporter(session)
        
        # Get recent violations (last 7 days)
        recent = reporter.get_recent_violations(days=7, account_id=account.id)
        assert len(recent) == 1
        assert recent[0]['sender_email'] == 'recent@bad.com'
        
        # Get recent violations (last 15 days) - should include both
        recent_15 = reporter.get_recent_violations(days=15, account_id=account.id)
        assert len(recent_15) == 2


def test_violation_reporter_worst_offenders():
    """Test worst offenders functionality."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create subscriptions with different violation counts
        subscriptions = [
            Subscription(
                account_id=account.id,
                sender_email=f"sender{i}@bad.com",
                sender_name=f"Bad Sender {i}",
                sender_domain="bad.com",
                unsubscribe_status='unsubscribed',
                emails_after_unsubscribe=i * 2,  # 2, 4, 6, 8, 10
                violation_count=i
            )
            for i in range(1, 6)
        ]
        
        session.add_all(subscriptions)
        session.commit()
        
        reporter = ViolationReporter(session)
        worst = reporter.get_worst_offenders(limit=3, account_id=account.id)
        
        # Should be ordered by emails_after_unsubscribe (descending)
        assert len(worst) == 3
        assert worst[0]['sender_email'] == 'sender5@bad.com'  # 10 emails
        assert worst[0]['emails_after_unsubscribe'] == 10
        assert worst[1]['sender_email'] == 'sender4@bad.com'  # 8 emails
        assert worst[2]['sender_email'] == 'sender3@bad.com'  # 6 emails


def test_violation_reporter_check_new_violations():
    """Test checking for new violations against email messages."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create unsubscribed subscription
        unsubscribe_date = datetime(2024, 1, 1, 12, 0, 0)
        subscription = Subscription(
            account_id=account.id,
            sender_email="spammer@bad.com",
            unsubscribe_status='unsubscribed',
            unsubscribed_at=unsubscribe_date
        )
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        
        # Create email messages - some before, some after unsubscribe
        messages = [
            EmailMessage(
                account_id=account.id,
                sender_email="spammer@bad.com",
                message_id="before-1",
                uid=1,
                subject="Before Unsubscribe",
                date_sent=datetime(2023, 12, 31, 10, 0, 0)  # Before
            ),
            EmailMessage(
                account_id=account.id,
                sender_email="spammer@bad.com",
                message_id="after-1",
                uid=2,
                subject="After Unsubscribe 1",
                date_sent=datetime(2024, 1, 2, 10, 0, 0)  # After - violation!
            ),
            EmailMessage(
                account_id=account.id,
                sender_email="spammer@bad.com",
                message_id="after-2",
                uid=3,
                subject="After Unsubscribe 2",
                date_sent=datetime(2024, 1, 3, 15, 0, 0)  # After - violation!
            ),
            EmailMessage(
                account_id=account.id,
                sender_email="good@sender.com",
                message_id="different-sender",
                uid=4,
                subject="Different Sender",
                date_sent=datetime(2024, 1, 4, 10, 0, 0)  # Different sender
            )
        ]
        
        session.add_all(messages)
        session.commit()
        
        # Check for new violations
        reporter = ViolationReporter(session)
        violations = reporter.check_for_new_violations(account.id)
        
        assert len(violations) == 1  # Only one subscription with violations
        violation = violations[0]
        assert violation['subscription'].sender_email == 'spammer@bad.com'
        assert violation['violation_count'] == 2  # Two emails after unsubscribe
        assert len(violation['violating_emails']) == 2
        
        # Check that subscription was updated
        session.refresh(subscription)
        assert subscription.emails_after_unsubscribe == 2
        assert subscription.violation_count == 2
        assert subscription.last_violation_at == datetime(2024, 1, 3, 15, 0, 0)


def test_generate_violation_report():
    """Test the formatted violation report generation."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create some violations
        now = datetime.now()
        subscription = Subscription(
            account_id=account.id,
            sender_email="spammer@bad.com",
            sender_name="Bad Spammer",
            sender_domain="bad.com",
            unsubscribe_status='unsubscribed',
            unsubscribed_at=now - timedelta(days=10),
            emails_after_unsubscribe=5,
            violation_count=3,
            last_violation_at=now - timedelta(days=2)
        )
        session.add(subscription)
        session.commit()
        
        # Generate report
        report = generate_violation_report(session, account.id)
        
        assert "UNSUBSCRIBE VIOLATION REPORT" in report
        assert "Total violating subscriptions: 1" in report
        assert "Total emails after unsubscribe: 5" in report
        assert "spammer@bad.com" in report
        assert "Recent Violations" in report
        assert "Worst Offenders" in report


def test_subscription_violation_edge_cases():
    """Test edge cases for violation tracking."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Test subscription that was never unsubscribed
        active_sub = Subscription(
            account_id=account.id,
            sender_email="active@sender.com"
        )
        session.add(active_sub)
        session.commit()
        
        # Should not have violations
        assert not active_sub.has_violations()
        assert not active_sub.is_violation_email(datetime.now())
        
        # Recording violation on active subscription should do nothing
        original_count = active_sub.emails_after_unsubscribe
        active_sub.record_violation(datetime.now())
        assert active_sub.emails_after_unsubscribe == original_count
        
        # Test subscription with unsubscribe date but no violations yet
        unsubscribed_sub = Subscription(
            account_id=account.id,
            sender_email="clean@sender.com",
            unsubscribe_status='unsubscribed',
            unsubscribed_at=datetime(2024, 1, 1)
        )
        session.add(unsubscribed_sub)
        session.commit()
        
        assert not unsubscribed_sub.has_violations()  # No violations yet
        assert unsubscribed_sub.is_violation_email(datetime(2024, 1, 2))  # But would be a violation


if __name__ == '__main__':
    pytest.main([__file__, '-v'])