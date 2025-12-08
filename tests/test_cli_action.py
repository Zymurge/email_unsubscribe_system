"""
TDD Tests for Action CLI Commands (Phase 4)

Commands covered:
- unsubscribe: Execute unsubscribe operations
- keep: Mark subscriptions to keep
- unkeep: Unmark subscriptions to keep
- delete-emails: Delete emails from unsubscribed subscriptions

Following TDD Red-Green-Refactor cycle.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, Mock

from src.cli.main import cli


class TestUnsubscribeCommand:
    """Test 'unsubscribe' command."""
    
    def test_unsubscribe_with_id(self):
        """Unsubscribe using subscription ID."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.action.execute_unsubscribe') as mock_execute:
            
            mock_session = MagicMock()
            mock_subscription = Mock(id=1, sender_email='news@example.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_subscription
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_execute.return_value = True
            
            result = runner.invoke(cli, ['unsubscribe', '--id', '1'])
            
            assert result.exit_code == 0
            assert 'success' in result.output.lower() or 'unsubscribe' in result.output.lower()
    
    def test_unsubscribe_dry_run(self):
        """Unsubscribe with dry-run flag."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.action.execute_unsubscribe') as mock_execute:
            
            mock_session = MagicMock()
            mock_subscription = Mock(id=1, sender_email='news@example.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_subscription
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['unsubscribe', '--id', '1', '--dry-run'])
            
            assert result.exit_code == 0
            assert 'dry' in result.output.lower() or 'would' in result.output.lower()
            mock_execute.assert_not_called()
    
    def test_unsubscribe_nonexistent_id(self):
        """Unsubscribe with invalid ID should fail."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['unsubscribe', '--id', '999'])
            
            assert result.exit_code != 0
            assert 'not found' in result.output.lower()


class TestKeepCommand:
    """Test 'keep' command - mark subscriptions to keep."""
    
    def test_keep_single_id(self):
        """Keep a single subscription."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_subscription = Mock(id=1, sender_email='news@example.com', keep_subscription=False)
            mock_session.query.return_value.filter.return_value.all.return_value = [mock_subscription]
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['keep', '1'])
            
            assert result.exit_code == 0
            assert mock_subscription.keep_subscription is True
            assert 'marked' in result.output.lower() or 'keep' in result.output.lower()
    
    def test_keep_multiple_ids(self):
        """Keep multiple subscriptions."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_subs = [
                Mock(id=1, sender_email='news@example.com', keep_subscription=False),
                Mock(id=2, sender_email='alerts@site.com', keep_subscription=False)
            ]
            mock_session.query.return_value.filter.return_value.all.return_value = mock_subs
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['keep', '1,2'])
            
            assert result.exit_code == 0
            assert all(s.keep_subscription for s in mock_subs)
    
    def test_keep_range(self):
        """Keep range of subscriptions."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_subs = [Mock(id=i, keep_subscription=False) for i in range(1, 4)]
            mock_session.query.return_value.filter.return_value.all.return_value = mock_subs
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['keep', '1-3'])
            
            assert result.exit_code == 0


class TestUnkeepCommand:
    """Test 'unkeep' command - unmark subscriptions to keep."""
    
    def test_unkeep_single_id(self):
        """Unkeep a single subscription."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_subscription = Mock(id=1, sender_email='news@example.com', keep_subscription=True)
            mock_session.query.return_value.filter.return_value.all.return_value = [mock_subscription]
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['unkeep', '1'])
            
            assert result.exit_code == 0
            assert mock_subscription.keep_subscription is False
    
    def test_unkeep_multiple_ids(self):
        """Unkeep multiple subscriptions."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_subs = [
                Mock(id=1, keep_subscription=True),
                Mock(id=2, keep_subscription=True)
            ]
            mock_session.query.return_value.filter.return_value.all.return_value = mock_subs
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['unkeep', '1,2'])
            
            assert result.exit_code == 0
            assert all(not s.keep_subscription for s in mock_subs)


class TestDeleteEmailsCommand:
    """Test 'delete-emails' command."""
    
    def test_delete_emails_with_id(self):
        """Delete emails for subscription."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.action.EmailDeleter') as mock_deleter, \
             patch('src.cli.commands.action.get_password_for_account') as mock_pwd:
            
            mock_session = MagicMock()
            mock_subscription = Mock(id=1, sender_email='news@example.com', account_id=1)
            mock_account = Mock(id=1, email_address='test@gmail.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_subscription
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_pwd.return_value = 'password123'
            mock_deleter_instance = MagicMock()
            mock_deleter_instance.delete_subscription_emails.return_value = Mock(
                success=True, emails_deleted=10, imap_deleted=10, db_deleted=10
            )
            mock_deleter.return_value = mock_deleter_instance
            
            result = runner.invoke(cli, ['delete-emails', '--id', '1', '--confirm'])
            
            assert result.exit_code == 0
            assert 'deleted' in result.output.lower() or '10' in result.output
    
    def test_delete_emails_dry_run(self):
        """Delete emails with dry-run."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager, \
             patch('src.cli.commands.action.EmailDeleter') as mock_deleter:
            
            mock_session = MagicMock()
            mock_subscription = Mock(id=1, sender_email='news@example.com', account_id=1)
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_subscription
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            mock_deleter_instance = MagicMock()
            mock_deleter_instance.preview_deletion.return_value = Mock(
                emails_to_delete=10, earliest_date='2024-01-01', latest_date='2024-12-01'
            )
            mock_deleter.return_value = mock_deleter_instance
            
            result = runner.invoke(cli, ['delete-emails', '--id', '1', '--dry-run'])
            
            assert result.exit_code == 0
            assert 'would' in result.output.lower() or 'dry' in result.output.lower()
    
    def test_delete_emails_requires_confirmation(self):
        """Delete emails should require confirmation."""
        runner = CliRunner()
        
        with patch('src.cli.commands.action.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_subscription = Mock(id=1, sender_email='news@example.com')
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_subscription
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            # No --confirm flag
            result = runner.invoke(cli, ['delete-emails', '--id', '1'])
            
            # Should require confirmation
            assert 'confirm' in result.output.lower() or result.exit_code != 0


class TestActionCommandHelp:
    """Test help text for action commands."""
    
    def test_unsubscribe_help(self):
        """Unsubscribe should have helpful documentation."""
        runner = CliRunner()
        result = runner.invoke(cli, ['unsubscribe', '--help'])
        
        assert result.exit_code == 0
        assert '--id' in result.output or 'subscription' in result.output.lower()
    
    def test_keep_help(self):
        """Keep command should document ID formats."""
        runner = CliRunner()
        result = runner.invoke(cli, ['keep', '--help'])
        
        assert result.exit_code == 0
    
    def test_delete_emails_help(self):
        """Delete-emails should warn about danger."""
        runner = CliRunner()
        result = runner.invoke(cli, ['delete-emails', '--help'])
        
        assert result.exit_code == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
