"""
HTTP GET Unsubscribe Executor

Handles unsubscribe execution via HTTP GET requests with:
- Comprehensive safety validations
- Rate limiting
- Success/failure tracking
- Dry-run mode support
"""

import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.database.models import Subscription, UnsubscribeAttempt


class HttpGetExecutor:
    """Execute unsubscribe requests via HTTP GET method."""
    
    def __init__(
        self,
        session: Session,
        max_attempts: int = 3,
        timeout: int = 30,
        user_agent: str = 'EmailSubscriptionManager/1.0 (+https://github.com/)',
        rate_limit_delay: float = 2.0,
        dry_run: bool = False
    ):
        """
        Initialize HTTP GET executor.
        
        Args:
            session: Database session
            max_attempts: Maximum retry attempts before giving up
            timeout: Request timeout in seconds
            user_agent: User-Agent header for requests
            rate_limit_delay: Delay in seconds between requests
            dry_run: If True, simulate without actual execution
        """
        self.session = session
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay
        self.dry_run = dry_run
        self._last_request_time: Optional[float] = None
    
    def should_execute(self, subscription_id: int) -> Dict[str, Any]:
        """
        Check if subscription should be processed for unsubscribe.
        
        Args:
            subscription_id: ID of subscription to check
            
        Returns:
            Dict with 'should_execute' (bool) and 'reason' (str)
        """
        subscription = self.session.query(Subscription).filter_by(
            id=subscription_id
        ).first()
        
        if not subscription:
            return {
                'should_execute': False,
                'reason': 'Subscription not found'
            }
        
        # Check if marked to keep
        if subscription.keep_subscription:
            return {
                'should_execute': False,
                'reason': 'Subscription marked to keep (skip unsubscribe)'
            }
        
        # Check if already unsubscribed
        if subscription.unsubscribed_at:
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
        
        # Check if method matches (must be http_get)
        if subscription.unsubscribe_method != 'http_get':
            return {
                'should_execute': False,
                'reason': f'Wrong method: {subscription.unsubscribe_method} (expected http_get)'
            }
        
        # Check attempt count
        attempt_count = self.session.query(UnsubscribeAttempt).filter_by(
            subscription_id=subscription_id
        ).count()
        
        if attempt_count >= self.max_attempts:
            return {
                'should_execute': False,
                'reason': f'Max attempts ({self.max_attempts}) reached'
            }
        
        return {
            'should_execute': True,
            'reason': 'Valid for execution'
        }
    
    def execute(self, subscription_id: int) -> Dict[str, Any]:
        """
        Execute unsubscribe via HTTP GET request.
        
        Args:
            subscription_id: ID of subscription to unsubscribe
            
        Returns:
            Dict with execution result including success status
        """
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
        
        # Dry-run mode
        if self.dry_run:
            return {
                'success': True,
                'dry_run': True,
                'message': f'DRY RUN: Would request {subscription.unsubscribe_link}'
            }
        
        # Execute HTTP GET request
        try:
            headers = {
                'User-Agent': self.user_agent
            }
            
            response = requests.get(
                subscription.unsubscribe_link,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            # Consider 2xx status codes as success
            success = 200 <= response.status_code < 300
            
            # Record attempt
            self._record_attempt(
                subscription_id=subscription_id,
                success=success,
                response_code=response.status_code,
                error_message=None if success else f'HTTP {response.status_code}: {response.text[:200]}'
            )
            
            # Update subscription if successful
            if success:
                subscription.unsubscribed_at = datetime.now()
                subscription.unsubscribe_status = 'unsubscribed'
                self.session.commit()
            
            return {
                'success': success,
                'status_code': response.status_code,
                'message': response.text[:200] if not success else 'Successfully unsubscribed'
            }
            
        except requests.exceptions.Timeout as e:
            error_msg = f'Request timed out after {self.timeout} seconds'
            self._record_attempt(
                subscription_id=subscription_id,
                success=False,
                response_code=None,
                error_message=error_msg
            )
            return {
                'success': False,
                'error_message': error_msg
            }
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f'Connection error: {str(e)}'
            self._record_attempt(
                subscription_id=subscription_id,
                success=False,
                response_code=None,
                error_message=error_msg
            )
            return {
                'success': False,
                'error_message': error_msg
            }
            
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            self._record_attempt(
                subscription_id=subscription_id,
                success=False,
                response_code=None,
                error_message=error_msg
            )
            return {
                'success': False,
                'error_message': error_msg
            }
    
    def _apply_rate_limit(self):
        """Apply rate limiting delay between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
        
        self._last_request_time = time.time()
    
    def _record_attempt(
        self,
        subscription_id: int,
        success: bool,
        response_code: Optional[int],
        error_message: Optional[str]
    ):
        """
        Record unsubscribe attempt in database.
        
        Args:
            subscription_id: ID of subscription
            success: Whether attempt succeeded
            response_code: HTTP response code (if applicable)
            error_message: Error message (if failed)
        """
        attempt = UnsubscribeAttempt(
            subscription_id=subscription_id,
            attempted_at=datetime.now(),
            method_used='http_get',
            status='success' if success else 'failed',
            response_code=response_code,
            error_message=error_message
        )
        self.session.add(attempt)
        self.session.commit()
