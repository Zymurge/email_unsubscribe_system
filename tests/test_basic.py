"""
Basic tests for the email subscription manager.
"""

import sys
import pytest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.database.models import Account, EmailMessage, Subscription
from src.database import DatabaseManager


def test_database_models():
    """Test that database models can be created."""
    # Use in-memory SQLite for testing
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
        
        assert account.id is not None
        assert account.email_address == "test@example.com"
        
        # Create a test message
        message = EmailMessage(
            account_id=account.id,
            message_id="test-message-id",
            uid=123,
            sender_email="sender@example.com",
            subject="Test Subject"
        )
        session.add(message)
        session.commit()
        
        # Verify relationships work
        assert len(account.email_messages) == 1
        assert account.email_messages[0].subject == "Test Subject"


def test_imap_settings():
    """Test IMAP settings lookup."""
    from src.email_processor.imap_client import get_imap_settings
    
    # Test known provider
    gmail_settings = get_imap_settings('gmail')
    assert gmail_settings['server'] == 'imap.gmail.com'
    assert gmail_settings['port'] == 993
    assert gmail_settings['use_ssl'] == True
    
    # Test Comcast
    comcast_settings = get_imap_settings('comcast')
    assert comcast_settings['server'] == 'imap.comcast.net'
    
    # Test unknown provider
    unknown_settings = get_imap_settings('unknown')
    assert unknown_settings['server'] == 'imap.unknown.com'


if __name__ == '__main__':
    pytest.main([__file__])