"""
Email Reply Unsubscribe Executor

Handles unsubscribe execution via email reply (mailto: links) with:
- Comprehensive safety validations (inherited from base)
- SMTP email sending
- Rate limiting (inherited from base)
- Success/failure tracking (inherited from base)
- Dry-run mode support (inherited from base)
"""

import smtplib
import socket
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs, unquote
from email.mime.text import MIMEText
from sqlalchemy.orm import Session

from src.database.models import Subscription
from .base_executor import BaseUnsubscribeExecutor


class EmailReplyExecutor(BaseUnsubscribeExecutor):
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
        super().__init__(session, max_attempts, timeout, rate_limit_seconds, dry_run)
        self.email_address = email_address
        self.email_password = email_password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
    
    @property
    def method_name(self) -> str:
        """Return the method name for this executor."""
        return 'email_reply'
    
    def should_execute(self, subscription_or_id):
        """
        Check if subscription should be processed for unsubscribe.
        
        Supports both interfaces for backward compatibility:
        - should_execute(subscription_id: int) - standard interface
        - should_execute(subscription: Subscription) - legacy interface
        
        Args:
            subscription_or_id: Either subscription ID (int) or Subscription object
            
        Returns:
            Dict with 'should_execute' (bool) and 'reason' (str)
        """
        # Handle both subscription object and subscription_id
        if isinstance(subscription_or_id, Subscription):
            # Legacy interface - use object's ID
            subscription_id = subscription_or_id.id
        else:
            # Standard interface
            subscription_id = subscription_or_id
        
        # Call base class implementation
        return super().should_execute(subscription_id)
    
    def execute(self, subscription_or_id):
        """
        Execute unsubscribe via email reply.
        
        Supports both interfaces for backward compatibility:
        - execute(subscription_id: int) - standard interface
        - execute(subscription: Subscription) - legacy interface
        
        Args:
            subscription_or_id: Either subscription ID (int) or Subscription object
            
        Returns:
            Dict with execution result
        """
        # Handle both subscription object and subscription_id
        if isinstance(subscription_or_id, Subscription):
            # Legacy interface - subscription object passed directly
            subscription = subscription_or_id
            subscription_id = subscription.id
        else:
            # Standard interface - subscription_id passed
            subscription_id = subscription_or_id
            subscription = self.session.query(Subscription).filter_by(
                id=subscription_id
            ).first()
            
            if not subscription:
                return {
                    'success': False,
                    'error_message': 'Subscription not found'
                }
        
        # Apply rate limiting
        self._apply_rate_limit()
        
        # Perform method-specific execution
        result = self._perform_execution(subscription)
        
        # Record attempt (skip for dry-run) - base class handles this now
        if not result.get('dry_run'):
            self._record_attempt(
                subscription_id=subscription_id,
                success=result.get('success', False),
                response_code=result.get('status_code'),
                error_message=result.get('error_message')
            )
        
        # Update subscription if successful and not dry-run
        if result.get('success') and not result.get('dry_run'):
            from datetime import datetime
            subscription.unsubscribed_at = datetime.now()
            subscription.unsubscribe_status = 'unsubscribed'
            self.session.commit()
        
        return result
    
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
    
    def _perform_execution(self, subscription: Subscription) -> Dict[str, Any]:
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
                'message': 'Email credentials not provided',
                'error_message': 'Email credentials not provided'
            }
        
        # Parse mailto URL
        mailto_info = self._parse_mailto(subscription.unsubscribe_link)
        
        # Dry-run mode
        if self.dry_run:
            return {
                'success': True,
                'dry_run': True,
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
            
            return {
                'success': True,
                'status': 'success',
                'message': f'Successfully sent unsubscribe email to {mailto_info["to"]}'
            }
            
        except smtplib.SMTPConnectError as e:
            error_msg = f'SMTP connection error: {str(e)}'
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg,
                'error_message': error_msg
            }
            
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f'SMTP authentication error: {str(e)}'
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg,
                'error_message': error_msg
            }
            
        except smtplib.SMTPException as e:
            error_msg = f'SMTP error: {str(e)}'
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg,
                'error_message': error_msg
            }
            
        except socket.timeout as e:
            error_msg = f'Connection timeout: {str(e)}'
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg,
                'error_message': error_msg
            }
            
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            return {
                'success': False,
                'status': 'failed',
                'message': error_msg,
                'error_message': error_msg
            }
