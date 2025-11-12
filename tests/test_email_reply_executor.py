"""
Tests for email reply unsubscribe executor.

This module tests the EmailReplyExecutor class which handles unsubscribe
requests that require sending an email to an unsubscribe address (typically
using mailto: links).

Following TDD methodology - tests written before implementation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from email.mime.text import MIMEText
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


class TestEmailReplyExecutorSafetyChecks:
    """Test safety validation before email execution."""
    
    def test_skip_subscription_marked_to_keep(self, session, test_account):
        """Should skip subscriptions marked as 'keep'."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            keep_subscription=True,  # User wants to keep this
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        executor = EmailReplyExecutor(session=session)
        result = executor.should_execute(subscription)
        
        assert result['should_execute'] is False
        assert 'keep' in result['reason'].lower()
    
    def test_skip_already_unsubscribed(self, session, test_account):
        """Should skip subscriptions already unsubscribed."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply',
            unsubscribed_at=datetime.now(),
            unsubscribe_status='unsubscribed'
        )
        session.add(subscription)
        session.commit()
        
        executor = EmailReplyExecutor(session=session)
        result = executor.should_execute(subscription)
        
        assert result['should_execute'] is False
        assert 'already unsubscribed' in result['reason'].lower()
    
    def test_skip_subscription_without_email_link(self, session, test_account):
        """Should skip if no unsubscribe email address."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link=None,  # No email address
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        executor = EmailReplyExecutor(session=session)
        result = executor.should_execute(subscription)
        
        assert result['should_execute'] is False
        assert 'no unsubscribe link' in result['reason'].lower()
    
    def test_skip_wrong_method_type(self, session, test_account):
        """Should skip if subscription method is not email_reply."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='https://company.com/unsubscribe',
            unsubscribe_method='http_get'  # Wrong method
        )
        session.add(subscription)
        session.commit()
        
        executor = EmailReplyExecutor(session=session)
        result = executor.should_execute(subscription)
        
        assert result['should_execute'] is False
        assert 'method mismatch' in result['reason'].lower()
    
    def test_allow_valid_subscription(self, session, test_account):
        """Should allow email for valid subscription."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        executor = EmailReplyExecutor(session=session)
        result = executor.should_execute(subscription)
        
        assert result['should_execute'] is True
        assert result['reason'] == 'All checks passed'
    
    def test_enforce_max_attempts(self, session, test_account):
        """Should skip if max failed attempts reached."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Add 3 failed attempts
        for i in range(3):
            attempt = UnsubscribeAttempt(
                subscription_id=subscription.id,
                method_used='email_reply',
                status='failed',
                attempted_at=datetime.now() - timedelta(days=i)
            )
            session.add(attempt)
        session.commit()
        
        executor = EmailReplyExecutor(session=session, max_attempts=3)
        result = executor.should_execute(subscription)
        
        assert result['should_execute'] is False
        assert 'max attempts' in result['reason'].lower()


class TestEmailReplyExecutorEmailComposition:
    """Test email message composition."""
    
    def test_compose_simple_email(self, session, test_account):
        """Should compose email with basic recipient."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        executor = EmailReplyExecutor(session=session)
        msg = executor._compose_message(
            from_addr='test@example.com',
            to_addr='unsubscribe@company.com',
            subject=None,
            body=None
        )
        
        assert msg['From'] == 'test@example.com'
        assert msg['To'] == 'unsubscribe@company.com'
        assert msg['Subject'] == 'Unsubscribe'
        assert 'unsubscribe' in msg.get_payload().lower()
    
    def test_compose_email_with_subject(self, session, test_account):
        """Should use provided subject if specified."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        executor = EmailReplyExecutor(session=session)
        msg = executor._compose_message(
            from_addr='test@example.com',
            to_addr='unsubscribe@company.com',
            subject='Remove from list',
            body=None
        )
        
        assert msg['Subject'] == 'Remove from list'
    
    def test_compose_email_with_body(self, session, test_account):
        """Should use provided body if specified."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        executor = EmailReplyExecutor(session=session)
        msg = executor._compose_message(
            from_addr='test@example.com',
            to_addr='unsubscribe@company.com',
            subject=None,
            body='Please remove me from your mailing list'
        )
        
        assert msg.get_payload() == 'Please remove me from your mailing list'
    
    def test_parse_mailto_url_simple(self, session, test_account):
        """Should parse simple mailto URL."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        executor = EmailReplyExecutor(session=session)
        result = executor._parse_mailto('mailto:unsubscribe@company.com')
        
        assert result['to'] == 'unsubscribe@company.com'
        assert result['subject'] is None
        assert result['body'] is None
    
    def test_parse_mailto_url_with_subject(self, session, test_account):
        """Should parse mailto URL with subject."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        executor = EmailReplyExecutor(session=session)
        result = executor._parse_mailto('mailto:unsub@company.com?subject=Unsubscribe%20Me')
        
        assert result['to'] == 'unsub@company.com'
        assert result['subject'] == 'Unsubscribe Me'
    
    def test_parse_mailto_url_with_body(self, session, test_account):
        """Should parse mailto URL with body."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        executor = EmailReplyExecutor(session=session)
        result = executor._parse_mailto('mailto:unsub@company.com?body=Remove%20me')
        
        assert result['to'] == 'unsub@company.com'
        assert result['body'] == 'Remove me'
    
    def test_parse_mailto_url_with_subject_and_body(self, session, test_account):
        """Should parse mailto URL with both subject and body."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        executor = EmailReplyExecutor(session=session)
        result = executor._parse_mailto('mailto:unsub@company.com?subject=Unsub&body=Remove')
        
        assert result['to'] == 'unsub@company.com'
        assert result['subject'] == 'Unsub'
        assert result['body'] == 'Remove'


class TestEmailReplyExecutorExecution:
    """Test email sending execution."""
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    def test_successful_email_send(self, mock_smtp, session, test_account):
        """Should successfully send unsubscribe email."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123',
            smtp_host='smtp.gmail.com',
            smtp_port=587
        )
        result = executor.execute(subscription)
        
        assert result['success'] is True
        assert result['status'] == 'success'
        assert 'unsubscribe email' in result['message'].lower()
        
        # Verify SMTP calls
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587, timeout=30)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@example.com', 'secret123')
        mock_server.send_message.assert_called_once()
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    def test_smtp_connection_failure(self, mock_smtp, session, test_account):
        """Should handle SMTP connection errors."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        import smtplib
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Mock connection failure
        mock_smtp.side_effect = smtplib.SMTPConnectError(421, 'Cannot connect')
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123'
        )
        result = executor.execute(subscription)
        
        assert result['success'] is False
        assert result['status'] == 'failed'
        assert 'connection' in result['message'].lower()
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    def test_smtp_authentication_failure(self, mock_smtp, session, test_account):
        """Should handle SMTP authentication errors."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        import smtplib
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Mock auth failure
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, 'Auth failed')
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123'
        )
        result = executor.execute(subscription)
        
        assert result['success'] is False
        assert result['status'] == 'failed'
        assert 'authentication' in result['message'].lower()
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    def test_smtp_send_failure(self, mock_smtp, session, test_account):
        """Should handle email send failures."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        import smtplib
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Mock send failure
        mock_server = MagicMock()
        mock_server.send_message.side_effect = smtplib.SMTPException('Send failed')
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123'
        )
        result = executor.execute(subscription)
        
        assert result['success'] is False
        assert result['status'] == 'failed'
        assert 'smtp' in result['message'].lower()
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    def test_network_timeout(self, mock_smtp, session, test_account):
        """Should handle network timeouts."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        import socket
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Mock timeout
        mock_smtp.side_effect = socket.timeout('Connection timed out')
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123',
            timeout=30
        )
        result = executor.execute(subscription)
        
        assert result['success'] is False
        assert result['status'] == 'failed'
        assert 'timeout' in result['message'].lower()
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    def test_updates_database_on_success(self, mock_smtp, session, test_account):
        """Should update subscription and record attempt on success."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Mock successful send
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123'
        )
        result = executor.execute(subscription)
        
        # Refresh from DB
        session.refresh(subscription)
        
        assert subscription.unsubscribed_at is not None
        assert subscription.unsubscribe_status == 'unsubscribed'
        
        # Check attempt recorded
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=subscription.id
        ).all()
        assert len(attempts) == 1
        assert attempts[0].status == 'success'
        assert attempts[0].method_used == 'email_reply'


class TestEmailReplyExecutorRateLimiting:
    """Test rate limiting between email sends."""
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    @patch('src.unsubscribe_executor.email_reply_executor.time.sleep')
    def test_rate_limiting_with_delay(self, mock_sleep, mock_smtp, session, test_account):
        """Should apply rate limiting between sends."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription1 = Subscription(
            account_id=test_account.id,
            sender_email='news1@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsub1@company.com',
            unsubscribe_method='email_reply'
        )
        subscription2 = Subscription(
            account_id=test_account.id,
            sender_email='news2@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsub2@company.com',
            unsubscribe_method='email_reply'
        )
        session.add_all([subscription1, subscription2])
        session.commit()
        
        # Mock successful sends
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123',
            rate_limit_seconds=2.0
        )
        
        # First send - no delay
        executor.execute(subscription1)
        mock_sleep.assert_not_called()
        
        # Second send - should delay
        executor.execute(subscription2)
        mock_sleep.assert_called_once()
        # Allow some tolerance for execution time
        assert mock_sleep.call_args[0][0] >= 1.5


class TestEmailReplyExecutorDryRun:
    """Test dry-run mode (simulation without actual email)."""
    
    @patch('src.unsubscribe_executor.email_reply_executor.smtplib.SMTP')
    def test_dry_run_mode(self, mock_smtp, session, test_account):
        """Should simulate email without actually sending in dry-run mode."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123',
            dry_run=True
        )
        result = executor.execute(subscription)
        
        assert result['success'] is True
        assert result['status'] == 'dry_run'
        assert 'would send' in result['message'].lower()
        
        # Verify no SMTP connection made
        mock_smtp.assert_not_called()
        
        # Verify database NOT updated in dry-run
        session.refresh(subscription)
        assert subscription.unsubscribed_at is None
        
        # Verify no attempt recorded
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=subscription.id
        ).all()
        assert len(attempts) == 0


class TestEmailReplyExecutorCredentials:
    """Test credential management."""
    
    def test_requires_credentials(self, session, test_account):
        """Should require email credentials for authentication."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        subscription = Subscription(
            account_id=test_account.id,
            sender_email='newsletter@company.com',
            email_count=5,
            confidence_score=80,
            unsubscribe_link='mailto:unsubscribe@company.com',
            unsubscribe_method='email_reply'
        )
        session.add(subscription)
        session.commit()
        
        # Should raise error without credentials
        executor = EmailReplyExecutor(
            session=session,
            email_address=None,
            email_password=None
        )
        
        result = executor.execute(subscription)
        assert result['success'] is False
        assert 'credentials' in result['message'].lower()
    
    def test_uses_provided_credentials(self, session, test_account):
        """Should use provided email credentials."""
        from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
        
        executor = EmailReplyExecutor(
            session=session,
            email_address='test@example.com',
            email_password='secret123'
        )
        
        assert executor.email_address == 'test@example.com'
        assert executor.email_password == 'secret123'
