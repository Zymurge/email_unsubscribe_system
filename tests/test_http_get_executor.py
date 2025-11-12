"""
TDD Test Specification for HTTP GET Unsubscribe Execution (Phase 4)

This test suite follows Test-Driven Development principles:
1. Write tests that define expected behavior
2. Run tests (they will fail - RED)
3. Implement minimal code to pass tests (GREEN)
4. Refactor while keeping tests passing (REFACTOR)

Test Coverage Areas:
- HTTP GET request execution
- Safety validations (keep_subscription flag, already unsubscribed, etc.)
- Success/failure tracking in database
- Rate limiting and delays
- Error handling and retry logic
- User-agent and headers
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Account, Subscription, UnsubscribeAttempt


class TestHttpGetExecutorSafetyChecks:
    """Test safety validations before executing unsubscribe."""
    
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
    
    def test_skip_subscription_marked_to_keep(self, session, test_account):
        """Should skip subscriptions marked with keep_subscription=True."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='keep@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=True,  # Should skip this
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_get'
        )
        session.add(subscription)
        session.commit()
        
        # Import will be created after implementation
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'keep' in result['reason'].lower() or 'skip' in result['reason'].lower()
    
    def test_skip_already_unsubscribed(self, session, test_account):
        """Should skip subscriptions that are already unsubscribed."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='already@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribed_at=datetime.now(),  # Already unsubscribed
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_get'
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'already' in result['reason'].lower()
    
    def test_skip_subscription_without_link(self, session, test_account):
        """Should skip subscriptions without an unsubscribe link."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='nolink@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link=None,  # No link available
            unsubscribe_method=None
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'link' in result['reason'].lower() or 'url' in result['reason'].lower()
    
    def test_skip_wrong_method(self, session, test_account):
        """Should skip if subscription requires different method (not http_get)."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='post@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_post'  # Wrong method for GET executor
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'method' in result['reason'].lower()
    
    def test_allow_valid_subscription(self, session, test_account):
        """Should allow execution for valid subscription."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='valid@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribed_at=None,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_get'
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is True
    
    def test_skip_after_max_attempts(self, session, test_account):
        """Should skip if max retry attempts reached."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='maxretry@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_get'
        )
        session.add(subscription)
        session.commit()
        
        # Create 3 failed attempts
        for i in range(3):
            attempt = UnsubscribeAttempt(
                subscription_id=subscription.id,
                attempted_at=datetime.now() - timedelta(days=i),
                method_used='http_get',
                status='failed',
                error_message='Test error'
            )
            session.add(attempt)
        session.commit()
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session, max_attempts=3)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'attempt' in result['reason'].lower() or 'retry' in result['reason'].lower()


class TestHttpGetExecutorExecution:
    """Test actual HTTP GET request execution."""
    
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
    
    @pytest.fixture
    def valid_subscription(self, session, test_account):
        """Create a valid subscription for testing."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe?token=abc123',
            unsubscribe_method='http_get'
        )
        session.add(subscription)
        session.commit()
        return subscription
    
    @patch('requests.get')
    def test_successful_http_get_request(self, mock_get, session, valid_subscription):
        """Should successfully execute HTTP GET request and record success."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Successfully unsubscribed'
        mock_get.return_value = mock_response
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is True
        assert result['status_code'] == 200
        
        # Verify request was made with correct URL
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert 'example.com/unsubscribe' in call_args[0][0]
        
        # Verify database was updated
        session.refresh(valid_subscription)
        assert valid_subscription.unsubscribed_at is not None
        assert valid_subscription.unsubscribe_status == 'unsubscribed'
        
        # Verify attempt was recorded
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=valid_subscription.id
        ).all()
        assert len(attempts) == 1
        assert attempts[0].status == 'success'
        assert attempts[0].method_used == 'http_get'
        assert attempts[0].response_code == 200
    
    @patch('requests.get')
    def test_http_get_with_custom_user_agent(self, mock_get, session, valid_subscription):
        """Should send requests with proper User-Agent header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session, user_agent='EmailSubscriptionManager/1.0')
        executor.execute(valid_subscription.id)
        
        # Verify User-Agent header was set
        call_kwargs = mock_get.call_args[1]
        assert 'headers' in call_kwargs
        assert 'User-Agent' in call_kwargs['headers']
        assert 'EmailSubscriptionManager' in call_kwargs['headers']['User-Agent']
    
    @patch('requests.get')
    def test_handle_http_error_response(self, mock_get, session, valid_subscription):
        """Should handle HTTP error responses (4xx, 5xx) gracefully."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        mock_get.return_value = mock_response
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is False
        assert result['status_code'] == 404
        
        # Verify subscription was NOT marked as unsubscribed
        session.refresh(valid_subscription)
        assert valid_subscription.unsubscribed_at is None
        
        # Verify attempt was recorded with failure
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=valid_subscription.id
        ).all()
        assert len(attempts) == 1
        assert attempts[0].status == 'failed'
        assert attempts[0].response_code == 404
    
    @patch('requests.get')
    def test_handle_network_exception(self, mock_get, session, valid_subscription):
        """Should handle network exceptions (timeout, connection error)."""
        # Mock network exception
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError('Connection refused')
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is False
        assert 'error_message' in result
        assert 'connection' in result['error_message'].lower() or 'refused' in result['error_message'].lower()
        
        # Verify attempt was recorded with error
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=valid_subscription.id
        ).all()
        assert len(attempts) == 1
        assert attempts[0].status == 'failed'
        assert attempts[0].error_message is not None
    
    @patch('requests.get')
    def test_timeout_handling(self, mock_get, session, valid_subscription):
        """Should handle request timeouts."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout('Request timed out')
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session, timeout=10)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is False
        assert 'timed out' in result['error_message'].lower()
    
    @patch('requests.get')
    def test_redirect_following(self, mock_get, session, valid_subscription):
        """Should follow redirects properly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = 'https://example.com/unsubscribe/confirmed'  # Final URL after redirect
        mock_get.return_value = mock_response
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is True
        
        # Verify redirects were allowed
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get('allow_redirects', True) is True


class TestHttpGetExecutorRateLimiting:
    """Test rate limiting and delays between requests."""
    
    @pytest.fixture
    def session(self):
        """Create an in-memory database session for testing."""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    @patch('time.sleep')
    @patch('requests.get')
    def test_rate_limiting_delay(self, mock_get, mock_sleep, session):
        """Should apply delay between requests for rate limiting."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Create account and subscriptions
        account = Account(email_address='test@example.com', provider='gmail')
        session.add(account)
        session.commit()
        
        subs = []
        for i in range(3):
            sub = Subscription(
                account_id=account.id,
                sender_email=f'sub{i}@example.com',
                sender_domain='example.com',
                email_count=10,
                keep_subscription=False,
                unsubscribe_link=f'https://example.com/unsub{i}',
                unsubscribe_method='http_get'
            )
            session.add(sub)
            subs.append(sub)
        session.commit()
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        # Execute multiple unsubscribes with rate limiting
        executor = HttpGetExecutor(session, rate_limit_delay=2.0)
        
        for sub in subs:
            executor.execute(sub.id)
        
        # Verify sleep was called with correct delay
        # First request: no delay, subsequent requests: delay
        assert mock_sleep.call_count == 2  # Called for 2nd and 3rd requests
        # Check that sleep was called with approximately the right delay
        for call in mock_sleep.call_args_list:
            delay = call[0][0]
            assert abs(delay - 2.0) < 0.1  # Allow 100ms tolerance


class TestHttpGetExecutorDryRun:
    """Test dry-run mode (simulate without actually executing)."""
    
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
            provider='gmail'
        )
        session.add(account)
        session.commit()
        return account
    
    @patch('requests.get')
    def test_dry_run_mode(self, mock_get, session, test_account):
        """Should simulate execution without making actual HTTP requests in dry-run mode."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='test@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_get'
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_executor import HttpGetExecutor
        
        executor = HttpGetExecutor(session, dry_run=True)
        result = executor.execute(subscription.id)
        
        # Should not make actual HTTP request
        mock_get.assert_not_called()
        
        # Should indicate dry-run in result
        assert result.get('dry_run') is True
        
        # Should NOT update database
        session.refresh(subscription)
        assert subscription.unsubscribed_at is None
        
        # Should NOT create attempt record
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=subscription.id
        ).all()
        assert len(attempts) == 0
