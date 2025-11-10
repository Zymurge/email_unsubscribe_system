"""
Test to verify the keep_subscription database schema change works.
This can be run independently to validate the database schema.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.database.models import Account, Subscription
from src.database import DatabaseManager


def test_keep_subscription_schema():
    """Test that the keep_subscription field works in the database."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        # Create test account
        account = Account(email_address="test@example.com", provider="test")
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create subscription with default keep_subscription value
        subscription = Subscription(
            account_id=account.id,
            sender_email="newsletter@company.com",
            sender_name="Company Newsletter"
        )
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        
        # Verify default value
        assert subscription.keep_subscription == False
        assert subscription.should_skip_unsubscribe() == False
        
        # Update keep_subscription to True
        subscription.keep_subscription = True
        session.commit()
        session.refresh(subscription)
        
        assert subscription.keep_subscription == True
        assert subscription.should_skip_unsubscribe() == True
        
        # Test mark_keep_subscription method
        subscription.mark_keep_subscription(False)
        session.commit()
        session.refresh(subscription)
        
        assert subscription.keep_subscription == False
        assert subscription.should_skip_unsubscribe() == False
        
        # Test query filtering by keep_subscription
        subscription.mark_keep_subscription(True)
        session.commit()
        
        # Should be able to query for kept subscriptions
        kept_subs = session.query(Subscription).filter(
            Subscription.keep_subscription == True
        ).all()
        
        assert len(kept_subs) == 1
        assert kept_subs[0].sender_email == "newsletter@company.com"
        
        print("✅ keep_subscription database schema working correctly!")


if __name__ == '__main__':
    test_keep_subscription_schema()