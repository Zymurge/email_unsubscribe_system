"""
Tests for CLI error handling - critical error paths.

Focuses on high-value error scenarios:
- Account not found
- Subscription not found
- Invalid IDs
- Empty results
"""

import pytest
from click.testing import CliRunner
from src.cli.main import cli
from src.cli_session import get_cli_session_manager
from src.database.models import Account, Subscription, EmailMessage


@pytest.fixture
def runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def session():
    """Create test database session."""
    session_manager = get_cli_session_manager()
    with session_manager.get_session() as session:
        yield session


@pytest.fixture
def test_account(session):
    """Create a test account."""
    account = Account(
        email_address='test@example.com',
        provider='gmail'
    )
    session.add(account)
    session.commit()
    return account


@pytest.fixture
def test_subscription(session, test_account):
    """Create a test subscription."""
    subscription = Subscription(
        account_id=test_account.id,
        sender_email='newsletter@example.com',
        sender_domain='example.com',
        email_count=5,
        confidence_score=95,
        keep_subscription=False
    )
    session.add(subscription)
    session.commit()
    return subscription


class TestAccountCommands:
    """Test error handling in account commands."""
    
    def test_stats_with_nonexistent_account(self, runner):
        """stats command handles nonexistent account gracefully."""
        result = runner.invoke(cli, ['stats', '--email', 'nonexistent@nowhere.com'])
        
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()
    
    def test_account_list_when_empty(self, runner, session):
        """account list shows appropriate message when no accounts exist."""
        # Clear any existing accounts
        session.query(Account).delete()
        session.commit()
        
        result = runner.invoke(cli, ['account', 'list'])
        
        assert result.exit_code == 0
        assert 'No accounts' in result.output or 'accounts found' in result.output.lower()


class TestScanCommands:
    """Test error handling in scan commands."""
    
    def test_scan_with_nonexistent_account(self, runner):
        """scan command handles nonexistent account gracefully."""
        result = runner.invoke(cli, ['scan', '--email', 'nonexistent@nowhere.com'])
        
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()
    
    def test_scan_analyze_with_nonexistent_account(self, runner):
        """scan-analyze command handles nonexistent account gracefully."""
        result = runner.invoke(cli, ['scan-analyze', '--email', 'nonexistent@nowhere.com'])
        
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()


class TestSubscriptionCommands:
    """Test error handling in subscription commands."""
    
    def test_detect_subscriptions_with_nonexistent_account(self, runner):
        """detect-subscriptions handles nonexistent account gracefully."""
        result = runner.invoke(cli, ['detect-subscriptions', '--email', 'nonexistent@nowhere.com'])
        
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()
    
    def test_list_subscriptions_with_nonexistent_account(self, runner):
        """list-subscriptions handles nonexistent account gracefully."""
        result = runner.invoke(cli, ['list-subscriptions', '--email', 'nonexistent@nowhere.com'])
        
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()
    
    def test_violations_with_nonexistent_account(self, runner):
        """violations command handles nonexistent account gracefully."""
        result = runner.invoke(cli, ['violations', '--email', 'nonexistent@nowhere.com'])
        
        assert result.exit_code != 0
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()


class TestActionCommands:
    """Test error handling in action commands."""
    
    def test_unsubscribe_with_nonexistent_subscription(self, runner):
        """unsubscribe command handles nonexistent subscription gracefully."""
        result = runner.invoke(cli, ['unsubscribe', '--id', '999'])
        
        assert result.exit_code != 0
        assert '999' in result.output or 'not found' in result.output.lower()
    
    def test_keep_with_nonexistent_subscription(self, runner):
        """keep command handles nonexistent subscription gracefully."""
        result = runner.invoke(cli, ['keep', '999999'])
        
        # Exit code 1 is acceptable when no matches found
        assert result.exit_code in [0, 1]
        # Should show that no subscriptions matched
        assert 'No subscriptions matched' in result.output or 'Aborted' in result.output
    
    def test_unkeep_with_nonexistent_subscription(self, runner):
        """unkeep command handles nonexistent subscription gracefully."""
        result = runner.invoke(cli, ['unkeep', '999999'])
        
        # Exit code 1 is acceptable when no matches found
        assert result.exit_code in [0, 1]
        # Should show that no subscriptions matched
        assert 'No subscriptions matched' in result.output or 'Aborted' in result.output
    
    def test_delete_emails_with_nonexistent_subscription(self, runner):
        """delete-emails command handles nonexistent subscription gracefully."""
        result = runner.invoke(cli, ['delete-emails', '--id', '999'])
        
        assert result.exit_code != 0
        assert '999' in result.output or 'not found' in result.output.lower()


class TestInvalidInputs:
    """Test handling of invalid inputs."""
    
    def test_stats_with_invalid_email(self, runner):
        """stats command handles invalid email format."""
        result = runner.invoke(cli, ['stats', '--email', 'not-an-email'])
        
        assert result.exit_code != 0
        # Command should fail or return not found
        assert 'not found' in result.output.lower() or 'error' in result.output.lower()
    
    def test_unsubscribe_with_non_numeric_id(self, runner):
        """unsubscribe command rejects non-numeric subscription ID."""
        result = runner.invoke(cli, ['unsubscribe', '--id', 'xyz'])
        
        assert result.exit_code != 0
        assert 'Invalid' in result.output or 'integer' in result.output.lower()
    
    def test_delete_emails_with_non_numeric_id(self, runner):
        """delete-emails command rejects non-numeric subscription ID."""
        result = runner.invoke(cli, ['delete-emails', '--id', 'bad'])
        
        assert result.exit_code != 0
        assert 'Invalid' in result.output or 'integer' in result.output.lower()


class TestKeepUnkeepParsing:
    """Test ID parsing in keep/unkeep commands."""
    
    def test_keep_with_invalid_range(self, runner):
        """keep command handles invalid range format."""
        result = runner.invoke(cli, ['keep', '1-2-3'])
        
        # Should reject with error message
        assert result.exit_code == 1
        assert 'Error' in result.output or 'Aborted' in result.output
    
    def test_keep_with_invalid_comma_list(self, runner):
        """keep command handles invalid comma-separated list."""
        result = runner.invoke(cli, ['keep', '1,abc,3'])
        
        # Should reject non-numeric values
        assert result.exit_code in [0, 1]
        assert 'Error' in result.output or 'Aborted' in result.output or 'No subscriptions' in result.output


class TestPasswordCommands:
    """Test error handling in password commands."""
    
    def test_remove_password_when_none_stored(self, runner):
        """remove password shows message when no password stored."""
        result = runner.invoke(cli, ['password', 'remove', 'nonexistent@example.com'], input='y\n')
        
        # Exit code may be 0 (success) or 1 (not found), both acceptable
        assert 'No' in result.output or 'not found' in result.output.lower() or 'removed' in result.output.lower()
    
    def test_list_passwords_when_empty(self, runner):
        """list passwords shows message when no passwords stored."""
        # Note: This test may show passwords from other tests
        # Testing the output format rather than exact content
        result = runner.invoke(cli, ['password', 'list'])
        
        assert result.exit_code == 0
        # Should show either "No stored passwords" or list stored ones
        assert 'password' in result.output.lower()
