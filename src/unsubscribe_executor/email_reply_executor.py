"""
Email Reply Unsubscribe Executor

Handles unsubscribe execution via email reply (mailto: links) with:
- Comprehensive safety validations
- SMTP email sending
- Rate limiting
- Success/failure tracking
- Dry-run mode support
"""

import time
import smtplib
import socket
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, unquote
from email.mime.text import MIMEText
from sqlalchemy.orm import Session

from src.database.models import Subscription, UnsubscribeAttempt


class EmailReplyExecutor:
    """Execute unsubscribe requests via email reply method."""
    
    def __init__(
        self,
        session: Session,
        email_address: Optional[str] = None,
        email_password: Optional[str] = None,
        smtp_host: str = 'smtp.gmail.com',
        smtp_port: int = 587,
        max_attempts: int = 3,
        timeout: int = 30,
        rate_limit_seconds: float = 2.0,
        dry_run: bool = False
    ):
        """
        Initialize Email Reply executor.
        
        Args:
            session: Database session
            email_address: Email address to send from
            email_password: Email password for SMTP authentication
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            max_attempts: Maximum retry attempts before giving up
            timeout: SMTP timeout in seconds
            rate_limit_seconds: Delay in seconds between email sends
            dry_run: If True, simulate without actual execution
        """
        self.session = session
        self.email_address = email_address
        self.email_password = email_password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.rate_limit_seconds = rate_limit_seconds
        self.dry_run = dry_run
        self._last_request_time: Optional[float] = None
    
    def should_execute(self, subscription: Subscription) -> Dict[str, Any]:
        """
        Check if subscription should be processed for unsubscribe.
        
        Args:
            subscription: Subscription to check
            
        Returns:
            Dict with 'should_execute' (bool) and 'reason' (str)
        """
        # Check if marked to keep
        if subscription.keep_subscription:
            return {
                'should_execute': False,
                'reason': 'Subscription marked to keep (skip unsubscribe)'
            }
        
        # Check if already unsubscribed
        if subscription.unsubscribe_status == 'unsubscribed':
            return {
                'should_execute': False,
                'reason': 'Already unsubscribed'
            }
        
        # Check if has unsubscribe link
        if not subscription.unsubscribe_link:
            return {
                'should_execute': False,
                'reason': 'No unsubscribe link available'
            }
        
        # Check if method matches (must be email_reply)
        if subscription.unsubscribe_method != 'email_reply':
            return {
                'should_execute': False,
                'reason': f'Method mismatch: {subscription.unsubscribe_method} (expected email_reply)'
            }
        
        # Check attempt count
        failed_attempts = self.session.query(UnsubscribeAttempt).filter_by(
            subscription_id=subscription.id,
            status='failed'
        ).count()
        
        if failed_attempts >= self.max_attempts:
            return {
                'should_execute': False,
                'reason': f'Max attempts ({self.max_attempts}) reached'
            }
        
        return {
            'should_execute': True,
            'reason': 'All checks passed'
        }
    
    def _parse_mailto(self, mailto_url: str) -> Dict[str, Optional[str]]:
        """
        Parse mailto URL to extract recipient, subject, and body.
        
        Args:
            mailto_url: mailto: URL string
            
        Returns:
            Dict with 'to', 'subject', and 'body' keys
        """
        # Parse the mailto URL
        parsed = urlparse(mailto_url)
        
        # Extract recipient (path after 'mailto:')
        to_addr = parsed.path
        
        # Extract query parameters
        query_params = parse_qs(parsed.query)
        
        # Get subject and body if present (URL decoded)
        subject = None
        if 'subject' in query_params:
            subject = unquote(query_params['subject'][0])
        
        body = None
        if 'body' in query_params:
            body = unquote(query_params['body'][0])
        
        return {
            'to': to_addr,
            'subject': subject,
            'body': body
        }
    
    def _compose_message(
        self,
        from_addr: str,
        to_addr: str,
        subject: Optional[str] = None,
        body: Optional[str] = None
    ) -> MIMEText:
        """
        Compose email message for unsubscribe request.
        
        Args:
            from_addr: Sender email address
            to_addr: Recipient email address
            subject: Email subject (None for default)
            body: Email body (None for default)
            
        Returns:
            MIMEText email message
        """
        # Use defaults if not provided
        if subject is None:
            subject = 'Unsubscribe'
        
        if body is None:
            body = 'Please unsubscribe me from this mailing list.'
        
        # Create message
        msg = MIMEText(body)
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg['Subject'] = subject
        
        return msg
    
    def execute(self, subscription: Subscription) -> Dict[str, Any]:
        """
        Execute unsubscribe via email reply.
        
        Args:
            subscription: Subscription to unsubscribe
            
        Returns:
            Dict with execution result including success status
        """
        # Check for credentials
        if not self.email_address or not self.email_password:
            return {
                'success': False,
                'status': 'failed',
                'message': 'Email credentials not provided'
            }
        
        # Apply rate limiting
        self._apply_rate_limit()
        
        # Parse mailto URL
        mailto_info = self._parse_mailto(subscription.unsubscribe_link)
        
        # Dry-run mode
        if self.dry_run:
            return {
                'success': True,
                'status': 'dry_run',
                'message': f'DRY RUN: Would send email to {mailto_info["to"]}'
            }
        
        # Compose message
        msg = self._compose_message(
            from_addr=self.email_address,
            to_addr=mailto_info['to'],
            subject=mailto_info['subject'],
            body=mailto_info['body']
        )
        
        # Send email via SMTP
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)
            
            # Update subscription status
            subscription.unsubscribed_at = datetime.now()
            subscription.unsubscribe_status = 'unsubscribed'
            
            # Record successful attempt
            self._record_attempt(
                subscription=subscription,
                status='success',
                message='Successfully sent unsubscribe email'
            )
            
            self.session.commit()
            
            return {
                'success': True,
                'status': 'success',
                'message': f'Successfully sent unsubscribe email to {mailto_info["to"]}'
            }
            
        except smtplib.SMTPConnectError as e:
            error_msg = f'SMTP connection error: {str(e)}'
            self._record_attempt(
                subscription=subscription,
                status='failed',
                message=error_msg
            )
            self.session.commit()
            
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg
            }
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f'SMTP authentication error: {str(e)}'
            self._record_attempt(
                subscription=subscription,
                status='failed',
                message=error_msg
            )
            self.session.commit()
            
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg
            }
            
        except smtplib.SMTPException as e:
            error_msg = f'SMTP error: {str(e)}'
            self._record_attempt(
                subscription=subscription,
                status='failed',
                message=error_msg
            )
            self.session.commit()
            
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg
            }
            
        except socket.timeout as e:
            error_msg = f'Connection timeout: {str(e)}'
            self._record_attempt(
                subscription=subscription,
                status='failed',
                message=error_msg
            )
            self.session.commit()
            
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg
            }
            
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            self._record_attempt(
                subscription=subscription,
                status='failed',
                message=error_msg
            )
            self.session.commit()
            
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg
            }
    
    def _record_attempt(
        self,
        subscription: Subscription,
        status: str,
        message: str
    ) -> None:
        """
        Record unsubscribe attempt in database.
        
        Args:
            subscription: Subscription that was processed
            status: Attempt status ('success' or 'failed')
            message: Status message or error details
        """
        attempt = UnsubscribeAttempt(
            subscription_id=subscription.id,
            method_used='email_reply',
            status=status,
            error_message=message if status == 'failed' else None,
            attempted_at=datetime.now()
        )
        self.session.add(attempt)
    
    def _apply_rate_limit(self) -> None:
        """Apply rate limiting delay between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_seconds:
                time.sleep(self.rate_limit_seconds - elapsed)
        
        self._last_request_time = time.time()
