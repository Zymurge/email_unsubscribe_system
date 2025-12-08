"""
TDD Tests for Info/Scan CLI Commands (Phase 3)

Commands covered:
- scan: Scan email account for messages
- scan-analyze: Combined scan and analysis
- detect-subscriptions: Detect subscriptions from scanned emails
- list-subscriptions: List all subscriptions with filters
- violations: Show violation reports

Following TDD Red-Green-Refactor cycle.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

from src.cli.main import cli


class TestScanCommand:
    """Test 'scan' command - scan email account."""
    
    def test_scan_requires_email(self):
        """Scan should require email address."""
        runner = CliRunner()
        result = runner.invoke(cli, ['scan'])
        
        # Should fail or prompt for email
        assert result.exit_code != 0 or 'email' in result.output.lower()
    
    def test_scan_with_email(self):
        """Scan should work with email address."""
        runner = CliRunner()
        
        with patch('src.cli.commands.scan.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.scan.EmailScanner') as mock_scanner, \
             patch('src.cli.commands.scan.get_password_for_account') as mock_pwd:
            
            mock_session = MagicMock()
            mock_account = Mock(id=1, email_address='test@gmail.com', provider='gmail')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_pwd.return_value = 'password123'
            mock_scanner_instance = MagicMock()
            mock_scanner_instance.scan_account.return_value = 10
            mock_scanner.return_value = mock_scanner_instance
            
            result = runner.invoke(cli, ['scan', '--email', 'test@gmail.com'])
            
            assert result.exit_code == 0
            assert 'scan' in result.output.lower() or '10' in result.output
    
    def test_scan_with_limit(self):
        """Scan should respect message limit."""
        runner = CliRunner()
        
        with patch('src.cli.commands.scan.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.scan.EmailScanner') as mock_scanner, \
             patch('src.cli.commands.scan.get_password_for_account') as mock_pwd:
            
            mock_session = MagicMock()
            mock_account = Mock(id=1, email_address='test@gmail.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_pwd.return_value = 'password123'
            mock_scanner_instance = MagicMock()
            mock_scanner.return_value = mock_scanner_instance
            
            result = runner.invoke(cli, ['scan', '--email', 'test@gmail.com', '--limit', '50'])
            
            assert result.exit_code == 0
            mock_scanner_instance.scan_account.assert_called()


class TestScanAnalyzeCommand:
    """Test 'scan-analyze' command - combined scan and analysis."""
    
    def test_scan_analyze_with_email(self):
        """Scan-analyze should work with email."""
        runner = CliRunner()
        
        with patch('src.cli.commands.scan.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.scan.CombinedEmailScanner') as mock_scanner, \
             patch('src.cli.commands.scan.get_password_for_account') as mock_pwd:
            
            mock_session = MagicMock()
            mock_account = Mock(id=1, email_address='test@gmail.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_pwd.return_value = 'password123'
            mock_scanner_instance = MagicMock()
            mock_scanner_instance.scan_account_with_analysis.return_value = (5, 3)
            mock_scanner.return_value = mock_scanner_instance
            
            result = runner.invoke(cli, ['scan-analyze', '--email', 'test@gmail.com'])
            
            assert result.exit_code == 0


class TestDetectSubscriptionsCommand:
    """Test 'detect-subscriptions' command."""
    
    def test_detect_subscriptions(self):
        """Detect subscriptions should work."""
        runner = CliRunner()
        
        with patch('src.cli.commands.subscription.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.subscription.SubscriptionDetector') as mock_detector:
            
            mock_session = MagicMock()
            mock_account = Mock(id=1, email_address='test@gmail.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_detector_instance = MagicMock()
            mock_detector_instance.detect_subscriptions.return_value = 5
            mock_detector.return_value = mock_detector_instance
            
            result = runner.invoke(cli, ['detect-subscriptions', '--email', 'test@gmail.com'])
            
            assert result.exit_code == 0
            assert '5' in result.output or 'subscription' in result.output.lower()


class TestListSubscriptionsCommand:
    """Test 'list-subscriptions' command."""
    
    def test_list_subscriptions_all(self):
        """List all subscriptions."""
        runner = CliRunner()
        
        with patch('src.cli.commands.subscription.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_account = Mock(id=1, email_address='test@gmail.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            
            mock_subs = [
                Mock(id=1, sender_email='news@example.com', email_count=10, 
                     keep_subscription=False, unsubscribed_at=None),
                Mock(id=2, sender_email='alerts@site.com', email_count=5,
                     keep_subscription=True, unsubscribed_at=None)
            ]
            mock_session.query.return_value.filter_by.return_value.all.return_value = mock_subs
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['list-subscriptions', '--email', 'test@gmail.com'])
            
            assert result.exit_code == 0
            assert 'news@example.com' in result.output or 'subscription' in result.output.lower()
    
    def test_list_subscriptions_with_filter(self):
        """List subscriptions with filters."""
        runner = CliRunner()
        
        with patch('src.cli.commands.subscription.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_account = Mock(id=1, email_address='test@gmail.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            mock_session.query.return_value.filter_by.return_value.all.return_value = []
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['list-subscriptions', '--email', 'test@gmail.com', '--filter', 'keep'])
            
            assert result.exit_code == 0


class TestViolationsCommand:
    """Test 'violations' command."""
    
    def test_violations_shows_report(self):
        """Violations should show report."""
        runner = CliRunner()
        
        with patch('src.cli.commands.subscription.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.subscription.ViolationReporter') as mock_reporter:
            
            mock_session = MagicMock()
            mock_account = Mock(id=1, email_address='test@gmail.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_reporter_instance = MagicMock()
            mock_reporter_instance.generate_report.return_value = "Violations: 3"
            mock_reporter.return_value = mock_reporter_instance
            
            result = runner.invoke(cli, ['violations', '--email', 'test@gmail.com'])
            
            assert result.exit_code == 0


class TestCommandHelp:
    """Test help text for info commands."""
    
    def test_scan_help(self):
        """Scan command should have help."""
        runner = CliRunner()
        result = runner.invoke(cli, ['scan', '--help'])
        
        assert result.exit_code == 0
        assert 'scan' in result.output.lower()
    
    def test_list_subscriptions_help(self):
        """List-subscriptions should document filters."""
        runner = CliRunner()
        result = runner.invoke(cli, ['list-subscriptions', '--help'])
        
        assert result.exit_code == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
