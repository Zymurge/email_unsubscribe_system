"""
Unit tests for list-subscriptions command functionality.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Account, Subscription


class TestListSubscriptionsCommand:
    """Test the list-subscriptions command functionality."""
    
    @pytest.fixture
    def session(self):
        """Create an in-memory database session for testing."""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    @pytest.fixture
    def test_account(self, session):
        """Create a test account."""
        account = Account(
            email_address='test@example.com',
            provider='gmail',
            imap_server='imap.gmail.com',
            imap_port=993
        )
        session.add(account)
        session.commit()
        return account
    
    def test_no_subscriptions(self, session, test_account):
        """Test query when account has no subscriptions."""
        # Query with no filter
        subscriptions = session.query(Subscription).filter_by(
            account_id=test_account.id
        ).all()
        
        assert len(subscriptions) == 0
    
    def test_list_all_subscriptions(self, session, test_account):
        """Test listing all subscriptions without filters."""
        # Create test subscriptions with different states
        subs = [
            Subscription(
                account_id=test_account.id,
                sender_email='kept@example.com',
                sender_domain='example.com',
                email_count=10,
                keep_subscription=True,
                unsubscribe_method='http_get'
            ),
            Subscription(
                account_id=test_account.id,
                sender_email='regular@example.com',
                sender_domain='example.com',
                email_count=20,
                keep_subscription=False,
                unsubscribe_method='oneclick'
            ),
            Subscription(
                account_id=test_account.id,
                sender_email='unsubscribed@example.com',
                sender_domain='example.com',
                email_count=15,
                keep_subscription=False,
                unsubscribed_at=datetime.now(),
                unsubscribe_method='http_post'
            ),
        ]
        
        for sub in subs:
            session.add(sub)
        session.commit()
        
        # Query all subscriptions
        all_subs = session.query(Subscription).filter_by(
            account_id=test_account.id
        ).all()
        
        assert len(all_subs) == 3
    
    def test_filter_keep_yes(self, session, test_account):
        """Test filtering for kept subscriptions only."""
        # Create subscriptions with different keep status
        kept_sub = Subscription(
            account_id=test_account.id,
            sender_email='kept@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=True,
            unsubscribe_method='http_get'
        )
        not_kept_sub = Subscription(
            account_id=test_account.id,
            sender_email='notkept@example.com',
            sender_domain='example.com',
            email_count=20,
            keep_subscription=False,
            unsubscribe_method='oneclick'
        )
        
        session.add(kept_sub)
        session.add(not_kept_sub)
        session.commit()
        
        # Query only kept subscriptions
        kept_subs = session.query(Subscription).filter_by(
            account_id=test_account.id,
            keep_subscription=True
        ).all()
        
        assert len(kept_subs) == 1
        assert kept_subs[0].sender_email == 'kept@example.com'
        assert kept_subs[0].keep_subscription is True
    
    def test_filter_keep_no(self, session, test_account):
        """Test filtering for non-kept subscriptions only."""
        # Create subscriptions
        kept_sub = Subscription(
            account_id=test_account.id,
            sender_email='kept@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=True
        )
        not_kept_sub1 = Subscription(
            account_id=test_account.id,
            sender_email='notkept1@example.com',
            sender_domain='example.com',
            email_count=20,
            keep_subscription=False
        )
        not_kept_sub2 = Subscription(
            account_id=test_account.id,
            sender_email='notkept2@example.com',
            sender_domain='example.com',
            email_count=15,
            keep_subscription=False
        )
        
        session.add_all([kept_sub, not_kept_sub1, not_kept_sub2])
        session.commit()
        
        # Query only non-kept subscriptions
        not_kept_subs = session.query(Subscription).filter_by(
            account_id=test_account.id,
            keep_subscription=False
        ).all()
        
        assert len(not_kept_subs) == 2
        assert all(sub.keep_subscription is False for sub in not_kept_subs)
    
    def test_ordering_by_email_count(self, session, test_account):
        """Test that subscriptions are ordered by email count descending."""
        # Create subscriptions with different email counts
        subs = [
            Subscription(
                account_id=test_account.id,
                sender_email='low@example.com',
                sender_domain='example.com',
                email_count=5
            ),
            Subscription(
                account_id=test_account.id,
                sender_email='high@example.com',
                sender_domain='example.com',
                email_count=50
            ),
            Subscription(
                account_id=test_account.id,
                sender_email='medium@example.com',
                sender_domain='example.com',
                email_count=25
            ),
        ]
        
        for sub in subs:
            session.add(sub)
        session.commit()
        
        # Query with ordering
        ordered_subs = session.query(Subscription).filter_by(
            account_id=test_account.id
        ).order_by(Subscription.email_count.desc()).all()
        
        assert len(ordered_subs) == 3
        assert ordered_subs[0].sender_email == 'high@example.com'
        assert ordered_subs[0].email_count == 50
        assert ordered_subs[1].sender_email == 'medium@example.com'
        assert ordered_subs[1].email_count == 25
        assert ordered_subs[2].sender_email == 'low@example.com'
        assert ordered_subs[2].email_count == 5
    
    def test_subscription_statistics(self, session, test_account):
        """Test calculating subscription statistics."""
        # Create diverse set of subscriptions
        subs = [
            # Kept subscription
            Subscription(
                account_id=test_account.id,
                sender_email='kept1@example.com',
                sender_domain='example.com',
                email_count=10,
                keep_subscription=True
            ),
            Subscription(
                account_id=test_account.id,
                sender_email='kept2@example.com',
                sender_domain='example.com',
                email_count=15,
                keep_subscription=True
            ),
            # Already unsubscribed
            Subscription(
                account_id=test_account.id,
                sender_email='unsubbed@example.com',
                sender_domain='example.com',
                email_count=20,
                keep_subscription=False,
                unsubscribed_at=datetime.now()
            ),
            # Ready to unsubscribe
            Subscription(
                account_id=test_account.id,
                sender_email='ready1@example.com',
                sender_domain='example.com',
                email_count=25,
                keep_subscription=False
            ),
            Subscription(
                account_id=test_account.id,
                sender_email='ready2@example.com',
                sender_domain='example.com',
                email_count=30,
                keep_subscription=False
            ),
        ]
        
        for sub in subs:
            session.add(sub)
        session.commit()
        
        # Get all subscriptions
        all_subs = session.query(Subscription).filter_by(
            account_id=test_account.id
        ).all()
        
        # Calculate stats
        kept_count = sum(1 for s in all_subs if s.keep_subscription)
        unsubscribed_count = sum(1 for s in all_subs if s.unsubscribed_at)
        ready_count = sum(1 for s in all_subs if not s.keep_subscription and not s.unsubscribed_at)
        
        assert len(all_subs) == 5
        assert kept_count == 2
        assert unsubscribed_count == 1
        assert ready_count == 2
    
    def test_unsubscribed_with_violations(self, session, test_account):
        """Test subscriptions that have violations after unsubscribing."""
        # Create unsubscribed subscription with violations
        unsub_date = datetime.now() - timedelta(days=10)
        sub = Subscription(
            account_id=test_account.id,
            sender_email='violator@example.com',
            sender_domain='example.com',
            email_count=30,
            keep_subscription=False,
            unsubscribed_at=unsub_date,
            violation_count=5,
            last_violation_at=datetime.now(),
            unsubscribe_method='http_get'
        )
        
        session.add(sub)
        session.commit()
        
        # Query the subscription
        result = session.query(Subscription).filter_by(
            sender_email='violator@example.com'
        ).first()
        
        assert result is not None
        assert result.unsubscribed_at is not None
        assert result.violation_count == 5
        assert result.last_violation_at is not None
    
    def test_subscription_without_unsubscribe_method(self, session, test_account):
        """Test subscriptions that don't have an unsubscribe method."""
        sub = Subscription(
            account_id=test_account.id,
            sender_email='nomethod@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_method=None
        )
        
        session.add(sub)
        session.commit()
        
        # Query the subscription
        result = session.query(Subscription).filter_by(
            sender_email='nomethod@example.com'
        ).first()
        
        assert result is not None
        assert result.unsubscribe_method is None
    
    def test_long_sender_email_truncation(self, session, test_account):
        """Test that long sender emails are handled properly."""
        long_email = 'very.long.email.address.that.exceeds.normal.length@example.com'
        sub = Subscription(
            account_id=test_account.id,
            sender_email=long_email,
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False
        )
        
        session.add(sub)
        session.commit()
        
        # Query and verify
        result = session.query(Subscription).filter_by(
            account_id=test_account.id
        ).first()
        
        assert result is not None
        assert result.sender_email == long_email
        
        # Test truncation logic (as would be used in display)
        sender_display = long_email[:34] if len(long_email) > 34 else long_email
        assert len(sender_display) == 34
    
    def test_multiple_unsubscribe_methods(self, session, test_account):
        """Test subscriptions with different unsubscribe methods."""
        methods = ['http_get', 'http_post', 'mailto', 'oneclick', None]
        
        for i, method in enumerate(methods):
            sub = Subscription(
                account_id=test_account.id,
                sender_email=f'sender{i}@example.com',
                sender_domain='example.com',
                email_count=10 + i,
                unsubscribe_method=method
            )
            session.add(sub)
        
        session.commit()
        
        # Query all and verify methods
        subs = session.query(Subscription).filter_by(
            account_id=test_account.id
        ).all()
        
        assert len(subs) == 5
        found_methods = [s.unsubscribe_method for s in subs]
        assert set(found_methods) == set(methods)
    
    def test_keep_indicator_display(self, session, test_account):
        """Test the keep indicator display logic."""
        sub_kept = Subscription(
            account_id=test_account.id,
            sender_email='kept@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=True
        )
        sub_not_kept = Subscription(
            account_id=test_account.id,
            sender_email='notkept@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False
        )
        
        session.add_all([sub_kept, sub_not_kept])
        session.commit()
        
        # Verify keep status
        kept = session.query(Subscription).filter_by(
            sender_email='kept@example.com'
        ).first()
        not_kept = session.query(Subscription).filter_by(
            sender_email='notkept@example.com'
        ).first()
        
        # Test display indicators
        kept_indicator = "[✓]" if kept.keep_subscription else "[ ]"
        not_kept_indicator = "[✓]" if not_kept.keep_subscription else "[ ]"
        
        assert kept_indicator == "[✓]"
        assert not_kept_indicator == "[ ]"
    
    def test_violation_display_logic(self, session, test_account):
        """Test violation count display logic."""
        # Subscription with violations (unsubscribed)
        sub_with_violations = Subscription(
            account_id=test_account.id,
            sender_email='violations@example.com',
            sender_domain='example.com',
            email_count=10,
            unsubscribed_at=datetime.now(),
            violation_count=3
        )
        
        # Subscription without unsubscribe (no violations to show)
        sub_without_unsub = Subscription(
            account_id=test_account.id,
            sender_email='nounsub@example.com',
            sender_domain='example.com',
            email_count=10
        )
        
        session.add_all([sub_with_violations, sub_without_unsub])
        session.commit()
        
        # Test display logic
        with_viol = session.query(Subscription).filter_by(
            sender_email='violations@example.com'
        ).first()
        without_unsub = session.query(Subscription).filter_by(
            sender_email='nounsub@example.com'
        ).first()
        
        # Violations display: show count if unsubscribed, "-" otherwise
        viol_display = str(with_viol.violation_count) if with_viol.unsubscribed_at else "-"
        no_viol_display = str(without_unsub.violation_count) if without_unsub.unsubscribed_at else "-"
        
        assert viol_display == "3"
        assert no_viol_display == "-"
