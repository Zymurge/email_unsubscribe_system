"""
Tests for database constraints and deduplication functionality.
"""

import sys
import pytest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.database.models import Account, EmailMessage, Subscription
from src.database import DatabaseManager
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import IntegrityError


def test_email_message_different_folders_allowed():
    """Test that same UID in different folders is allowed."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        # Create a test account
        account = Account(
            email_address="test@example.com",
            provider="test"
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create message in INBOX
        message1 = EmailMessage(
            account_id=account.id,
            message_id="test-message-1",
            uid=123,
            folder="INBOX",
            sender_email="sender@example.com",
            subject="Test Subject"
        )
        session.add(message1)
        session.commit()
        
        # Create message with same UID in different folder - should work
        message2 = EmailMessage(
            account_id=account.id,
            message_id="test-message-2",
            uid=123,  # Same UID
            folder="Sent",  # Different folder
            sender_email="sender@example.com",
            subject="Test Subject"
        )
        session.add(message2)
        session.commit()  # Should not raise an error
        
        # Verify both messages exist
        messages = session.query(EmailMessage).filter(
            EmailMessage.account_id == account.id
        ).all()
        assert len(messages) == 2


def test_email_message_different_accounts_allowed():
    """Test that same UID and folder for different accounts is allowed."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        # Create two test accounts
        account1 = Account(email_address="test1@example.com", provider="test")
        account2 = Account(email_address="test2@example.com", provider="test")
        session.add_all([account1, account2])
        session.commit()
        session.refresh(account1)
        session.refresh(account2)
        
        # Create message for account1
        message1 = EmailMessage(
            account_id=account1.id,
            message_id="test-message-1",
            uid=123,
            folder="INBOX",
            sender_email="sender@example.com",
            subject="Test Subject"
        )
        session.add(message1)
        session.commit()
        
        # Create message with same UID and folder for account2 - should work
        message2 = EmailMessage(
            account_id=account2.id,  # Different account
            message_id="test-message-2",
            uid=123,  # Same UID
            folder="INBOX",  # Same folder
            sender_email="sender@example.com",
            subject="Test Subject"
        )
        session.add(message2)
        session.commit()  # Should not raise an error
        
        # Verify both messages exist
        total_messages = session.query(EmailMessage).count()
        assert total_messages == 2


def test_subscription_unique_constraint():
    """Test that the unique constraint on (account_id, sender_email) works."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.initialize_database()
    
    with db_manager.get_session() as session:
        # Create a test account
        account = Account(
            email_address="test@example.com",
            provider="test"
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # Create first subscription
        subscription1 = Subscription(
            account_id=account.id,
            sender_email="newsletter@example.com",
            sender_name="Example Newsletter",
            category="newsletter"
        )
        session.add(subscription1)
        session.commit()
        
        # Try to create duplicate subscription with same (account_id, sender_email)
        subscription2 = Subscription(
            account_id=account.id,
            sender_email="newsletter@example.com",  # Same sender
            sender_name="Different Name",
            category="marketing"  # Different category
        )
        session.add(subscription2)
        
        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            session.commit()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])