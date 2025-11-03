"""
Step 1 TDD Tests: Basic Subscription Creation from Emails

These tests will initially FAIL (Red phase) until we implement the SubscriptionDetector.
"""

import sys
import pytest
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.database.models import Account, EmailMessage, Subscription
from src.database import DatabaseManager


class TestSubscriptionDetection:
    """Test subscription creation from email messages."""
    
    def test_create_subscription_from_single_sender(self):
        """Create subscription from multiple emails from same sender."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            # Create test account
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Create multiple emails from same sender
            emails = [
                EmailMessage(
                    account_id=account.id,
                    message_id=f"msg-{i}",
                    uid=i,
                    sender_email="newsletter@company.com",
                    sender_name="Company Newsletter",
                    subject=f"Newsletter {i}",
                    date_sent=datetime(2024, 1, i, 10, 0, 0),
                    has_unsubscribe_header=True
                )
                for i in range(1, 4)  # 3 emails
            ]
            session.add_all(emails)
            session.commit()
            
            # Import and run subscription detection (will fail initially)
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            result = detector.detect_subscriptions_from_emails(account.id, session)
            
            # Verify results
            assert result['created'] == 1
            assert result['updated'] == 0
            assert result['skipped'] == 0
            
            # Verify subscription was created correctly
            subscription = session.query(Subscription).filter(
                Subscription.account_id == account.id
            ).first()
            
            assert subscription is not None
            assert subscription.sender_email == "newsletter@company.com"
            assert subscription.sender_name == "Company Newsletter"
            assert subscription.sender_domain == "company.com"
            assert subscription.email_count == 3
            assert subscription.discovered_at == datetime(2024, 1, 1, 10, 0, 0)
            assert subscription.last_seen == datetime(2024, 1, 3, 10, 0, 0)
            # 3 emails (35 points) + unsubscribe header (15 points) = 50
            assert subscription.confidence_score == 50
    
    def test_create_multiple_subscriptions_different_senders(self):
        """Create separate subscriptions for different senders."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Create emails from different senders
            emails = [
                EmailMessage(
                    account_id=account.id,
                    message_id="msg-1",
                    uid=1,
                    sender_email="news@site1.com",
                    subject="News Update",
                    date_sent=datetime(2024, 1, 1, 10, 0, 0)
                ),
                EmailMessage(
                    account_id=account.id,
                    message_id="msg-2", 
                    uid=2,
                    sender_email="alerts@site2.com",
                    subject="Alert Message",
                    date_sent=datetime(2024, 1, 2, 10, 0, 0)
                )
            ]
            session.add_all(emails)
            session.commit()
            
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            result = detector.detect_subscriptions_from_emails(account.id, session)
            
            assert result['created'] == 2
            assert result['updated'] == 0
            
            # Verify both subscriptions created
            subscriptions = session.query(Subscription).filter(
                Subscription.account_id == account.id
            ).all()
            
            assert len(subscriptions) == 2
            sender_emails = {sub.sender_email for sub in subscriptions}
            assert sender_emails == {"news@site1.com", "alerts@site2.com"}
    
    def test_sender_domain_extraction(self):
        """Extract full sender domain correctly."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Test various domain formats
            test_cases = [
                ("newsletter@company.com", "company.com"),
                ("no-reply@marketing.bigcorp.co.uk", "marketing.bigcorp.co.uk"),
                ("user+tag@subdomain.example.org", "subdomain.example.org"),
                ("simple@domain.net", "domain.net")
            ]
            
            emails = []
            for i, (sender_email, expected_domain) in enumerate(test_cases):
                emails.append(EmailMessage(
                    account_id=account.id,
                    message_id=f"msg-{i}",
                    uid=i,
                    sender_email=sender_email,
                    subject="Test",
                    date_sent=datetime(2024, 1, 1, 10, 0, 0)
                ))
            
            session.add_all(emails)
            session.commit()
            
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            detector.detect_subscriptions_from_emails(account.id, session)
            
            # Verify domains extracted correctly
            subscriptions = session.query(Subscription).filter(
                Subscription.account_id == account.id
            ).all()
            
            for sub in subscriptions:
                expected_domain = next(
                    domain for email, domain in test_cases 
                    if email == sub.sender_email
                )
                assert sub.sender_domain == expected_domain
    
    def test_confidence_scoring_algorithm(self):
        """Test deterministic confidence scoring algorithm."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Test case 1: 1 email, no unsubscribe info = 15 points
            email1 = EmailMessage(
                account_id=account.id,
                message_id="msg-1",
                uid=1,
                sender_email="single@test.com",
                subject="One Email",
                date_sent=datetime(2024, 1, 1, 10, 0, 0),
                has_unsubscribe_header=False,
                has_unsubscribe_link=False
            )
            
            # Test case 2: 3 emails with unsubscribe header = 35 + 15 = 50 points
            emails_with_unsub = [
                EmailMessage(
                    account_id=account.id,
                    message_id=f"msg-unsub-{i}",
                    uid=10 + i,
                    sender_email="unsub@test.com",
                    subject="Newsletter",
                    date_sent=datetime(2024, 1, i, 10, 0, 0),
                    has_unsubscribe_header=True
                )
                for i in range(1, 4)  # 3 emails
            ]
            
            # Test case 3: 8 emails with unsubscribe + marketing keywords = 75 + 15 + 10 = 100
            emails_marketing = [
                EmailMessage(
                    account_id=account.id,
                    message_id=f"msg-marketing-{i}",
                    uid=20 + i,
                    sender_email="marketing@test.com",
                    subject="EXCLUSIVE SALE - Weekly Newsletter",  # Marketing keywords
                    date_sent=datetime(2024, 1, i, 10, 0, 0),
                    has_unsubscribe_header=True
                )
                for i in range(1, 9)  # 8 emails
            ]
            
            all_emails = [email1] + emails_with_unsub + emails_marketing
            session.add_all(all_emails)
            session.commit()
            
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            detector.detect_subscriptions_from_emails(account.id, session)
            
            # Verify confidence scores
            subscriptions = session.query(Subscription).filter(
                Subscription.account_id == account.id
            ).all()
            
            confidence_by_sender = {
                sub.sender_email: sub.confidence_score 
                for sub in subscriptions
            }
            
            assert confidence_by_sender["single@test.com"] == 15
            assert confidence_by_sender["unsub@test.com"] == 50
            assert confidence_by_sender["marketing@test.com"] == 100
    
    def test_skip_emails_with_insufficient_data(self):
        """Skip emails with insufficient data and log occurrences."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Mix of valid and invalid emails
            emails = [
                # Valid email - should process
                EmailMessage(
                    account_id=account.id,
                    message_id="valid-1",
                    uid=1,
                    sender_email="valid@test.com",
                    subject="Valid Email",
                    date_sent=datetime(2024, 1, 1, 10, 0, 0)
                ),
                # Missing sender_email - should skip
                EmailMessage(
                    account_id=account.id,
                    message_id="invalid-1",
                    uid=2,
                    sender_email="",  # Empty sender email
                    subject="Invalid Email",
                    date_sent=datetime(2024, 1, 1, 10, 0, 0)
                ),
                # Missing date_sent - should skip  
                EmailMessage(
                    account_id=account.id,
                    message_id="invalid-2",
                    uid=3,
                    sender_email="nodate@test.com",
                    subject="No Date",
                    date_sent=None
                ),
                # Missing sender_name and subject - should still process
                EmailMessage(
                    account_id=account.id,
                    message_id="valid-2",
                    uid=4,
                    sender_email="minimal@test.com",
                    sender_name=None,
                    subject=None,
                    date_sent=datetime(2024, 1, 1, 10, 0, 0)
                )
            ]
            
            session.add_all(emails)
            session.commit()
            
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            result = detector.detect_subscriptions_from_emails(account.id, session)
            
            # Should create 2 subscriptions, skip 2 emails
            assert result['created'] == 2
            assert result['skipped'] == 2
            
            # Verify only valid subscriptions were created
            subscriptions = session.query(Subscription).filter(
                Subscription.account_id == account.id
            ).all()
            
            sender_emails = {sub.sender_email for sub in subscriptions}
            assert sender_emails == {"valid@test.com", "minimal@test.com"}
    
    def test_marketing_keyword_detection(self):
        """Detect marketing keywords in email subjects for confidence scoring."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Test various subjects with and without marketing keywords
            test_cases = [
                ("Weekly Newsletter Update", True),   # 'newsletter', 'weekly'
                ("Your Order Confirmation", False),   # No marketing keywords
                ("EXCLUSIVE SALE - 50% OFF!", True),  # 'exclusive', 'sale'
                ("", False),                          # Empty subject
                ("Limited Time Offer - Free Shipping", True)  # 'limited time', 'offer', 'free'
            ]
            
            emails = []
            for i, (subject, has_keywords) in enumerate(test_cases):
                emails.append(EmailMessage(
                    account_id=account.id,
                    message_id=f"msg-{i}",
                    uid=i,
                    sender_email=f"test{i}@example.com",
                    subject=subject,
                    date_sent=datetime(2024, 1, 1, 10, 0, 0)
                ))
            
            session.add_all(emails)
            session.commit()
            
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            detector.detect_subscriptions_from_emails(account.id, session)
            
            # Verify marketing keyword bonus applied correctly
            subscriptions = session.query(Subscription).filter(
                Subscription.account_id == account.id
            ).all()
            
            for sub in subscriptions:
                subject, has_keywords = next(
                    (subj, has_kw) for i, (subj, has_kw) in enumerate(test_cases)
                    if f"test{i}@example.com" == sub.sender_email
                )
                
                expected_score = 15  # Base score for 1 email
                if has_keywords:
                    expected_score += 10  # Marketing keyword bonus
                
                assert sub.confidence_score == expected_score
    
    def test_prevent_duplicate_subscriptions(self):
        """Prevent duplicate subscriptions and update existing ones."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Create initial email
            initial_email = EmailMessage(
                account_id=account.id,
                message_id="msg-1",
                uid=1,
                sender_email="sender@test.com",
                subject="First Email",
                date_sent=datetime(2024, 1, 1, 10, 0, 0)
            )
            session.add(initial_email)
            session.commit()
            
            # First detection run
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            result1 = detector.detect_subscriptions_from_emails(account.id, session)
            
            assert result1['created'] == 1
            assert result1['updated'] == 0
            
            # Add more emails from same sender
            new_emails = [
                EmailMessage(
                    account_id=account.id,
                    message_id=f"msg-{i}",
                    uid=i,
                    sender_email="sender@test.com",
                    subject=f"Email {i}",
                    date_sent=datetime(2024, 1, i, 10, 0, 0),
                    has_unsubscribe_header=True
                )
                for i in range(2, 5)  # 3 more emails
            ]
            session.add_all(new_emails)
            session.commit()
            
            # Second detection run - should update existing subscription
            result2 = detector.detect_subscriptions_from_emails(account.id, session)
            
            assert result2['created'] == 0
            assert result2['updated'] == 1
            
            # Verify subscription was updated, not duplicated
            subscriptions = session.query(Subscription).filter(
                Subscription.account_id == account.id
            ).all()
            
            assert len(subscriptions) == 1
            subscription = subscriptions[0]
            assert subscription.email_count == 4  # 1 initial + 3 new
            assert subscription.last_seen == datetime(2024, 1, 4, 10, 0, 0)
            # 4 emails (55 points) + unsubscribe header (15 points) = 70
            assert subscription.confidence_score == 70
    
    def test_integration_with_existing_violations(self):
        """Integration with existing violation tracking."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Create existing emails that led to the subscription
            existing_emails = [
                EmailMessage(
                    account_id=account.id,
                    message_id=f"existing-msg-{i}",
                    uid=100 + i,
                    sender_email="existing@test.com",
                    subject=f"Existing Email {i}",
                    date_sent=datetime(2023, 12, i, 10, 0, 0)
                )
                for i in range(1, 6)  # 5 existing emails
            ]
            session.add_all(existing_emails)
            session.commit()
            
            # Create existing subscription with violation data (based on above emails)
            existing_subscription = Subscription(
                account_id=account.id,
                sender_email="existing@test.com",
                sender_name="Existing Sender",
                sender_domain="test.com",
                email_count=5,
                confidence_score=60,
                unsubscribe_status='unsubscribed',
                unsubscribed_at=datetime(2024, 1, 1, 10, 0, 0),
                emails_after_unsubscribe=3,
                violation_count=2,
                last_violation_at=datetime(2024, 1, 15, 10, 0, 0),
                discovered_at=datetime(2023, 12, 1, 10, 0, 0),
                last_seen=datetime(2024, 1, 10, 10, 0, 0)
            )
            session.add(existing_subscription)
            session.commit()
            
            # Add new emails from existing sender
            new_emails = [
                EmailMessage(
                    account_id=account.id,
                    message_id=f"new-msg-{i}",
                    uid=i,
                    sender_email="existing@test.com",
                    subject=f"New Email {i}",
                    date_sent=datetime(2024, 2, i, 10, 0, 0)
                )
                for i in range(1, 3)  # 2 new emails
            ]
            session.add_all(new_emails)
            session.commit()
            
            # Run detection - should update but preserve violation data
            from src.email_processor.subscription_detector import SubscriptionDetector
            detector = SubscriptionDetector()
            result = detector.detect_subscriptions_from_emails(account.id, session)
            
            assert result['updated'] == 1
            
            # Verify violation data preserved and email count updated
            session.refresh(existing_subscription)
            assert existing_subscription.email_count == 7  # 5 existing + 2 new (all emails in DB)
            assert existing_subscription.last_seen == datetime(2024, 2, 2, 10, 0, 0)
            # Preserve violation tracking
            assert existing_subscription.unsubscribe_status == 'unsubscribed'
            assert existing_subscription.emails_after_unsubscribe == 3
            assert existing_subscription.violation_count == 2
            assert existing_subscription.last_violation_at == datetime(2024, 1, 15, 10, 0, 0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])