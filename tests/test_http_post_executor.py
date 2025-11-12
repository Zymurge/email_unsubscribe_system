"""
Tests for HTTP POST unsubscribe executor.

This module tests the HttpPostExecutor class which handles unsubscribe
requests that require HTTP POST form submissions (typically with one-click
unsubscribe or form-based unsubscribe pages).

Following TDD methodology - tests written before implementation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.database.models import Account, Subscription, UnsubscribeAttempt, create_database_engine, create_tables, get_session_maker


@pytest.fixture
def test_db():
    """Create in-memory test database."""
    engine = create_database_engine("sqlite:///:memory:")
    create_tables(engine)
    SessionMaker = get_session_maker(engine)
    return SessionMaker


@pytest.fixture
def session(test_db):
    """Create database session."""
    session = test_db()
    yield session
    session.close()


@pytest.fixture
def test_account(session):
    """Create test account."""
    account = Account(
        email_address='test@example.com',
        provider='gmail'
    )
    session.add(account)
    session.commit()
    return account


class TestHttpPostExecutorSafetyChecks:
    """Test safety validation before POST execution."""
    
    def test_skip_subscription_marked_to_keep(self, session, test_account):
        """Should skip subscriptions marked as 'keep'."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=True,  # Marked to keep
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_post'
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'keep' in result['reason'].lower()
    
    def test_skip_already_unsubscribed(self, session, test_account):
        """Should skip subscriptions already unsubscribed."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_post',
            unsubscribed_at=datetime.now()  # Already unsubscribed
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'already' in result['reason'].lower()
    
    def test_skip_subscription_without_link(self, session, test_account):
        """Should skip subscriptions without unsubscribe link."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link=None,  # No link
            unsubscribe_method='http_post'
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'link' in result['reason'].lower()
    
    def test_skip_wrong_method(self, session, test_account):
        """Should skip if unsubscribe method is not http_post."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_get'  # Wrong method
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'method' in result['reason'].lower()
    
    def test_allow_valid_subscription(self, session, test_account):
        """Should allow valid subscription to be processed."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_post'
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
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
            unsubscribe_method='http_post'
        )
        session.add(subscription)
        session.commit()
        
        # Create 3 failed attempts
        for i in range(3):
            attempt = UnsubscribeAttempt(
                subscription_id=subscription.id,
                attempted_at=datetime.now() - timedelta(days=i),
                method_used='http_post',
                status='failed',
                error_message='Test error'
            )
            session.add(attempt)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session, max_attempts=3)
        result = executor.should_execute(subscription.id)
        
        assert result['should_execute'] is False
        assert 'max' in result['reason'].lower() or 'attempts' in result['reason'].lower()


class TestHttpPostExecutorExecution:
    """Test actual HTTP POST request execution."""
    
    @pytest.fixture
    def valid_subscription(self, session, test_account):
        """Create valid subscription for testing."""
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_post'
        )
        session.add(subscription)
        session.commit()
        return subscription
    
    @patch('requests.post')
    def test_successful_http_post_request(self, mock_post, session, valid_subscription):
        """Should successfully execute HTTP POST request and record success."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Successfully unsubscribed'
        mock_post.return_value = mock_response
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is True
        assert result['status_code'] == 200
        
        # Verify request was made with correct URL
        mock_post.assert_called_once()
        call_args = mock_post.call_args
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
        assert attempts[0].method_used == 'http_post'
        assert attempts[0].response_code == 200
    
    @patch('requests.post')
    def test_http_post_with_custom_user_agent(self, mock_post, session, valid_subscription):
        """Should include custom User-Agent header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session, user_agent='CustomAgent/2.0')
        executor.execute(valid_subscription.id)
        
        # Verify User-Agent header
        call_kwargs = mock_post.call_args[1]
        assert 'headers' in call_kwargs
        assert 'User-Agent' in call_kwargs['headers']
        assert call_kwargs['headers']['User-Agent'] == 'CustomAgent/2.0'
    
    @patch('requests.post')
    def test_http_post_with_list_unsubscribe_post_header(self, mock_post, session, valid_subscription):
        """Should send List-Unsubscribe=One-Click header for RFC 8058 compliance."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
        executor.execute(valid_subscription.id)
        
        # Verify List-Unsubscribe=One-Click header
        call_kwargs = mock_post.call_args[1]
        assert 'headers' in call_kwargs
        assert 'List-Unsubscribe' in call_kwargs['headers']
        assert call_kwargs['headers']['List-Unsubscribe'] == 'One-Click'
    
    @patch('requests.post')
    def test_handle_http_error_response(self, mock_post, session, valid_subscription):
        """Should handle HTTP error responses (4xx, 5xx) gracefully."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        mock_post.return_value = mock_response
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
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
    
    @patch('requests.post')
    def test_handle_network_exception(self, mock_post, session, valid_subscription):
        """Should handle network exceptions (timeout, connection error)."""
        # Mock network exception
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError('Connection refused')
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
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
    
    @patch('requests.post')
    def test_timeout_handling(self, mock_post, session, valid_subscription):
        """Should handle request timeouts."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout('Request timed out')
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session, timeout=10)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is False
        assert 'timed out' in result['error_message'].lower()
    
    @patch('requests.post')
    def test_redirect_following(self, mock_post, session, valid_subscription):
        """Should follow redirects properly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = 'https://example.com/unsubscribe/confirmed'  # Final URL after redirect
        mock_post.return_value = mock_response
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session)
        result = executor.execute(valid_subscription.id)
        
        assert result['success'] is True
        # Verify allow_redirects was set
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs.get('allow_redirects', True) is True
        
        session.close()


class TestHttpPostExecutorRateLimiting:
    """Test rate limiting between requests."""
    
    @patch('time.sleep')
    @patch('requests.post')
    def test_rate_limiting_delay(self, mock_post, mock_sleep, session):
        """Should apply delay between requests for rate limiting."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
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
                unsubscribe_method='http_post'
            )
            session.add(sub)
            subs.append(sub)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        # Execute multiple unsubscribes with rate limiting
        executor = HttpPostExecutor(session, rate_limit_delay=2.0)
        
        for sub in subs:
            executor.execute(sub.id)
        
        # Verify sleep was called with correct delay
        # First request: no delay, subsequent requests: delay
        assert mock_sleep.call_count == 2  # Called for 2nd and 3rd requests
        # Check that sleep was called with approximately the right delay
        for call in mock_sleep.call_args_list:
            delay = call[0][0]
            assert abs(delay - 2.0) < 0.1  # Allow 100ms tolerance


class TestHttpPostExecutorDryRun:
    """Test dry-run mode (no actual requests)."""
    
    @patch('requests.post')
    def test_dry_run_mode(self, mock_post, session):
        """Should simulate POST without making actual request in dry-run mode."""
        account = Account(email_address='test@example.com', provider='gmail')
        session.add(account)
        session.commit()
        
        subscription = Subscription(
            account_id=account.id,
            sender_email='newsletter@example.com',
            sender_domain='example.com',
            email_count=10,
            keep_subscription=False,
            unsubscribe_link='https://example.com/unsubscribe',
            unsubscribe_method='http_post'
        )
        session.add(subscription)
        session.commit()
        
        from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
        
        executor = HttpPostExecutor(session, dry_run=True)
        result = executor.execute(subscription.id)
        
        # Verify dry-run success
        assert result['success'] is True
        assert result['dry_run'] is True
        
        # Verify NO actual POST request was made
        mock_post.assert_not_called()
        
        # Verify subscription was NOT updated
        session.refresh(subscription)
        assert subscription.unsubscribed_at is None
        
        # Verify NO attempt was recorded
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=subscription.id
        ).all()
        assert len(attempts) == 0
