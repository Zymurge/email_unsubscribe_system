"""
TDD Tests for Simple CLI Commands (Phase 2)

Commands covered:
- init: Initialize the database
- add-account: Add a new email account
- list-accounts: List all configured accounts
- stats: Show account statistics

Following TDD Red-Green-Refactor cycle.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path

from src.cli.main import cli


class TestInitCommand:
    """Test 'init' command - initialize database."""
    
    def test_init_creates_database(self):
        """Init should create database file."""
        runner = CliRunner()
        
        with patch('src.cli.commands.admin.init_database') as mock_init:
            result = runner.invoke(cli, ['init'])
            
            assert result.exit_code == 0
            mock_init.assert_called_once()
            assert 'Database initialized successfully' in result.output
    
    def test_init_shows_database_location(self, tmp_path):
        """Init should display where database was created."""
        runner = CliRunner()
        db_path = tmp_path / "emails.db"
        
        with patch('src.cli.commands.admin.init_database') as mock_init:
            mock_init.return_value = str(db_path)
            
            result = runner.invoke(cli, ['init'])
            
            assert result.exit_code == 0
            assert str(db_path) in result.output
    
    def test_init_handles_errors(self):
        """Init should handle database creation errors gracefully."""
        runner = CliRunner()
        
        with patch('src.cli.commands.admin.init_database') as mock_init:
            mock_init.side_effect = Exception("Permission denied")
            
            result = runner.invoke(cli, ['init'])
            
            assert result.exit_code != 0
            assert 'Error' in result.output or 'Failed' in result.output


class TestAddAccountCommand:
    """Test 'add-account' command - add new email account."""
    
    def test_add_account_minimal_args(self):
        """Add account with just email and provider."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, [
                'account', 'add',
                'test@gmail.com',
                '--provider', 'gmail'
            ])
            
            assert result.exit_code == 0
            assert 'Account added successfully' in result.output
            assert mock_session.add.called
            assert mock_session.commit.called
    
    def test_add_account_all_args(self):
        """Add account with all optional arguments."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, [
                'account', 'add',
                'test@example.com',
                '--provider', 'custom',
                '--imap-server', 'mail.example.com',
                '--imap-port', '993'
            ])
            
            assert result.exit_code == 0
            assert 'Account added successfully' in result.output
    
    def test_add_account_duplicate_email(self):
        """Adding duplicate account should fail or warn."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            # Simulate IntegrityError for duplicate
            from sqlalchemy.exc import IntegrityError
            mock_session.commit.side_effect = IntegrityError("UNIQUE constraint", None, None)
            
            result = runner.invoke(cli, [
                'account', 'add',
                'test@gmail.com',
                '--provider', 'gmail'
            ])
            
            assert result.exit_code != 0
            assert 'already exists' in result.output.lower() or 'duplicate' in result.output.lower()
    
    def test_add_account_validates_email(self):
        """Should validate email address format."""
        runner = CliRunner()
        
        result = runner.invoke(cli, [
            'account', 'add',
            'not-an-email',
            '--provider', 'gmail'
        ])
        
        # Either click validates it or our code does
        assert result.exit_code != 0 or 'invalid' in result.output.lower()
    
    def test_add_account_auto_detects_provider(self):
        """Should auto-detect provider settings from email domain."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            # Gmail should be auto-detected
            result = runner.invoke(cli, [
                'account', 'add',
                'test@gmail.com'  # No --provider specified
            ])
            
            assert result.exit_code == 0
            # Check that Account was created with gmail settings
            call_args = mock_session.add.call_args
            account = call_args[0][0]
            assert account.provider == 'gmail'
            assert account.imap_server == 'imap.gmail.com'


class TestListAccountsCommand:
    """Test 'account list' command - list all accounts."""
    
    def test_list_no_accounts(self):
        """Display message when no accounts configured."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.query.return_value.all.return_value = []
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['account', 'list'])
            
            assert result.exit_code == 0
            assert 'No accounts' in result.output or 'no accounts' in result.output
    
    def test_list_single_account(self):
        """Display single account with details."""
        runner = CliRunner()
        
        mock_account = Mock()
        mock_account.id = 1
        mock_account.email_address = 'test@gmail.com'
        mock_account.provider = 'gmail'
        mock_account.imap_server = 'imap.gmail.com'
        mock_account.imap_port = 993
        mock_account.last_scan = None
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.query.return_value.all.return_value = [mock_account]
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['account', 'list'])
            
            assert result.exit_code == 0
            assert 'test@gmail.com' in result.output
            assert 'gmail' in result.output
    
    def test_list_multiple_accounts(self):
        """Display multiple accounts."""
        runner = CliRunner()
        
        mock_accounts = [
            Mock(id=1, email_address='a@gmail.com', provider='gmail', 
                 imap_server='imap.gmail.com', imap_port=993, last_scan=None),
            Mock(id=2, email_address='b@outlook.com', provider='outlook',
                 imap_server='outlook.office365.com', imap_port=993, last_scan=None),
        ]
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.query.return_value.all.return_value = mock_accounts
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['account', 'list'])
            
            assert result.exit_code == 0
            assert 'a@gmail.com' in result.output
            assert 'b@outlook.com' in result.output
            assert '2' in result.output  # Account count


class TestStatsCommand:
    """Test 'stats' command - show account statistics."""
    
    def test_stats_no_account_specified(self):
        """Stats without account should show all accounts or error."""
        runner = CliRunner()
        
        # If no account specified, should either show all or prompt
        result = runner.invoke(cli, ['stats'])
        
        # Acceptable outcomes: error asking for account, or showing all accounts
        assert result.exit_code == 0 or 'account' in result.output.lower()
    
    def test_stats_for_specific_account(self):
        """Stats should show message counts for account."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            
            # Mock account
            mock_account = Mock()
            mock_account.email_address = 'test@gmail.com'
            mock_account.last_scan = None
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_account
            
            # Mock stats
            mock_session.query.return_value.filter_by.return_value.count.return_value = 100
            
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['stats', '--email', 'test@gmail.com'])
            
            assert result.exit_code == 0
            assert 'test@gmail.com' in result.output
            assert '100' in result.output or 'messages' in result.output.lower()
    
    def test_stats_shows_subscription_count(self):
        """Stats should show subscription statistics."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            
            mock_account = Mock()
            mock_account.email_address = 'test@gmail.com'
            mock_account.last_scan = None
            
            # Create a query mock that can handle different model queries
            def query_side_effect(model):
                query_mock = MagicMock()
                if 'EmailMessage' in str(model):
                    query_mock.filter_by.return_value.count.return_value = 100
                elif 'Subscription' in str(model):
                    query_mock.filter_by.return_value.count.return_value = 5
                query_mock.filter_by.return_value.first.return_value = mock_account
                return query_mock
            
            mock_session.query.side_effect = query_side_effect
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['stats', '--email', 'test@gmail.com'])
            
            assert result.exit_code == 0
            # Should show subscriptions somewhere
            assert 'subscription' in result.output.lower() or '5' in result.output
    
    def test_stats_nonexistent_account(self):
        """Stats for non-existent account should error."""
        runner = CliRunner()
        
        with patch('src.cli.commands.account.get_cli_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            mock_manager.return_value.get_session.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ['stats', '--email', 'nonexistent@example.com'])
            
            assert result.exit_code != 0
            assert 'not found' in result.output.lower() or 'does not exist' in result.output.lower()


class TestAccountCommandHelp:
    """Test help text for account commands."""
    
    def test_account_group_help(self):
        """Account group should show all subcommands."""
        runner = CliRunner()
        result = runner.invoke(cli, ['account', '--help'])
        
        assert result.exit_code == 0
        assert 'add' in result.output
        assert 'list' in result.output
    
    def test_init_help(self):
        """Init command should have helpful description."""
        runner = CliRunner()
        result = runner.invoke(cli, ['init', '--help'])
        
        assert result.exit_code == 0
        assert 'database' in result.output.lower()
    
    def test_stats_help(self):
        """Stats command should document options."""
        runner = CliRunner()
        result = runner.invoke(cli, ['stats', '--help'])
        
        assert result.exit_code == 0
        # Should explain what stats shows


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
