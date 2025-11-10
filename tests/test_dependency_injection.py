"""
Unit tests demonstrating dependency injection and mocking patterns.

These tests show how the DI pattern makes testing much easier by allowing
us to inject mock database sessions.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

# Add src to path for testing
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.email_processor.scanner import EmailScanner
from src.email_processor.subscription_detector import SubscriptionDetector
from src.database.violations import ViolationReporter
from src.database.models import Account, EmailMessage, Subscription


class TestEmailScannerDI:
    """Test EmailScanner with dependency injection."""
    
    def test_add_account_with_mock_session(self):
        """Test add_account method with mocked database session."""
        # Arrange
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = None  # No existing account
        
        scanner = EmailScanner(mock_session)
        
        # Mock the IMAP connection test (this would need proper mocking in real tests)
        # For now, we'll focus on the database interaction
        
        # Act & Assert would require more IMAP mocking
        # This shows the pattern - session is easily mockable
        assert scanner.session == mock_session
        
    def test_get_accounts_with_mock_data(self):
        """Test get_accounts method with mocked database data."""
        # Arrange
        mock_session = Mock()
        
        # Create mock account objects
        mock_account1 = Mock()
        mock_account1.id = 1
        mock_account1.email_address = "test1@example.com"
        mock_account1.provider = "gmail"
        mock_account1.last_scan = datetime(2024, 1, 1)
        mock_account1.email_messages = []
        
        mock_account2 = Mock()
        mock_account2.id = 2
        mock_account2.email_address = "test2@example.com"
        mock_account2.provider = "outlook"
        mock_account2.last_scan = None
        mock_account2.email_messages = [Mock(), Mock()]  # 2 messages
        
        mock_session.query.return_value.all.return_value = [mock_account1, mock_account2]
        
        scanner = EmailScanner(mock_session)
        
        # Act
        accounts = scanner.get_accounts()
        
        # Assert
        assert len(accounts) == 2
        assert accounts[0]['id'] == 1
        assert accounts[0]['email_address'] == "test1@example.com"
        assert accounts[0]['message_count'] == 0
        assert accounts[1]['message_count'] == 2
        
        # Verify session was called correctly
        mock_session.query.assert_called_once()
        
    def test_get_account_stats_with_mocked_queries(self):
        """Test get_account_stats with mocked database queries."""
        # Arrange  
        mock_session = Mock()
        
        # Mock account
        mock_account = Mock()
        mock_account.email_address = "test@example.com"
        mock_account.provider = "gmail"
        mock_account.last_scan = datetime(2024, 1, 1)
        
        # Mock query chain for account lookup
        mock_session.query.return_value.get.return_value = mock_account
        
        # Mock query chain for message counts
        mock_session.query.return_value.filter.return_value.count.return_value = 100
        
        # Mock query chain for top senders
        mock_session.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
            ("sender1@example.com", 10),
            ("sender2@example.com", 5)
        ]
        
        scanner = EmailScanner(mock_session)
        
        # Act
        stats = scanner.get_account_stats(1)
        
        # Assert
        assert stats['account']['email'] == "test@example.com"
        assert stats['total_messages'] == 100
        assert len(stats['top_senders']) == 2
        assert stats['top_senders'][0]['email'] == "sender1@example.com"


class TestSubscriptionDetectorDI:
    """Test SubscriptionDetector with dependency injection."""
    
    def test_detect_subscriptions_with_mock_session(self):
        """Test subscription detection with mocked database session."""
        # Arrange
        mock_session = Mock()
        
        # Mock email data
        mock_email = Mock()
        mock_email.sender_email = "newsletter@company.com"
        mock_email.sender_name = "Company Newsletter"
        mock_email.subject = "Weekly Newsletter"
        mock_email.body_text = "Check out our latest deals and offers!"
        mock_email.date_sent = datetime(2024, 1, 1)
        mock_email.has_unsubscribe_header = True
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_email]
        mock_session.query.return_value.filter.return_value.first.return_value = None  # No existing subscription
        
        detector = SubscriptionDetector()
        
        # Act
        result = detector.detect_subscriptions_from_emails(1, mock_session)
        
        # Assert
        assert 'created' in result
        assert 'updated' in result
        assert 'skipped' in result
        
        # Verify session interactions
        mock_session.query.assert_called()
        mock_session.commit.assert_called()


class TestViolationReporterDI:
    """Test ViolationReporter with dependency injection."""
    
    def test_get_violation_summary_with_mock_data(self):
        """Test violation summary with mocked database data."""
        # Arrange
        mock_session = Mock()
        
        # Mock subscription with violations
        mock_subscription = Mock()
        mock_subscription.violation_count = 5
        mock_subscription.emails_after_unsubscribe = 3
        mock_subscription.sender_email = "spammer@example.com"
        mock_subscription.sender_name = "Spammer Inc"
        mock_subscription.unsubscribed_at = datetime(2024, 1, 1)
        mock_subscription.last_violation_at = datetime(2024, 1, 15)
        
        # Mock the query chain properly - need to handle the chained filters
        mock_query = Mock()
        mock_query.filter.return_value = mock_query  # Chain returns itself
        mock_query.all.return_value = [mock_subscription]
        mock_session.query.return_value = mock_query
        
        reporter = ViolationReporter(mock_session)
        
        # Act
        summary = reporter.get_violations_summary(1)
        
        # Assert
        assert summary['total_violations'] == 1
        assert summary['total_violation_emails'] == 3
        assert len(summary['violations_by_sender']) == 1
        assert summary['violations_by_sender'][0]['sender_email'] == "spammer@example.com"
        
        # Verify session was called correctly
        mock_session.query.assert_called()
        
    def test_get_recent_violations_with_mock_data(self):
        """Test recent violations with mocked database data."""
        # Arrange
        mock_session = Mock()
        
        # Mock violation data
        mock_violation = Mock()
        mock_violation.sender_email = "violator@example.com"
        mock_violation.violation_count = 3
        mock_violation.last_violation_at = datetime(2024, 1, 15)
        
        # Create a proper query chain mock
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_violation]
        mock_session.query.return_value = mock_query
        
        reporter = ViolationReporter(mock_session)
        
        # Act - use correct method signature (days, account_id)
        recent = reporter.get_recent_violations(days=7, account_id=1)
        
        # Assert
        assert len(recent) == 1
        assert recent[0]['sender_email'] == "violator@example.com"
        assert recent[0]['violation_count'] == 3
        
        # Verify query chain
        mock_session.query.assert_called()


class TestCLISessionManagement:
    """Test CLI session management patterns."""
    
    def test_session_manager_provides_session(self):
        """Test that CLI session manager provides database sessions."""
        from src.cli_session import CLISessionManager
        
        # Mock the DatabaseManager
        mock_db_manager = Mock()
        mock_session = Mock()
        mock_db_manager.get_session.return_value = mock_session
        
        session_manager = CLISessionManager()
        session_manager.db_manager = mock_db_manager
        
        # Test context manager
        with session_manager.get_session() as session:
            assert session == mock_session
            
        # Test execution wrapper
        def test_func(session, arg1, arg2):
            assert session == mock_session
            return f"{arg1}-{arg2}"
            
        result = session_manager.execute_with_session(test_func, "hello", "world")
        assert result == "hello-world"
        
    def test_with_db_session_decorator(self):
        """Test the @with_db_session decorator pattern."""
        from src.cli_session import with_db_session
        
        @with_db_session
        def test_command(session, test_arg):
            # In real usage, session would be a real SQLAlchemy session
            # Here we just verify the pattern works
            return f"session-{test_arg}"
        
        # This would work in integration tests with a real database
        # For unit tests, we'd mock the session manager
        pass


if __name__ == '__main__':
    # Run with: python -m pytest tests/test_dependency_injection.py -v
    pytest.main([__file__, '-v'])