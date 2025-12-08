"""
HTTP POST Unsubscribe Executor

Handles unsubscribe requests that require HTTP POST form submissions.
Supports RFC 8058 one-click unsubscribe with List-Unsubscribe=One-Click header.
Inherits common validation, rate limiting, and tracking from BaseUnsubscribeExecutor.
"""

import requests
from typing import Dict
from sqlalchemy.orm import Session

from src.database.models import Subscription
from .base_executor import BaseUnsubscribeExecutor


class HttpPostExecutor(BaseUnsubscribeExecutor):
    """
    Execute HTTP POST unsubscribe requests.
    
    Supports:
    - RFC 8058 one-click unsubscribe (List-Unsubscribe: One-Click header)
    - Form-based POST submissions
    - Safety validations (inherited from base)
    - Rate limiting (inherited from base)
    - Dry-run mode (inherited from base)
    - Attempt tracking (inherited from base)
    """
    
    def __init__(
        self,
        session: Session,
        timeout: int = 30,
        user_agent: str = 'EmailSubscriptionManager/1.0',
        rate_limit_delay: float = 1.0,
        max_attempts: int = 3,
        dry_run: bool = False
    ):
        """
        Initialize HTTP POST executor.
        
        Args:
            session: Database session
            timeout: HTTP request timeout in seconds
            user_agent: User-Agent header value
            rate_limit_delay: Delay between requests in seconds
            max_attempts: Maximum retry attempts per subscription
            dry_run: If True, simulate without making actual requests
        """
        super().__init__(session, max_attempts, timeout, rate_limit_delay, dry_run)
        self.user_agent = user_agent
    
    @property
    def method_name(self) -> str:
        """Return the method name for this executor."""
        return 'http_post'
    
    def _perform_execution(self, subscription: Subscription) -> Dict[str, any]:
        """
        Execute HTTP POST unsubscribe request.
        
        Args:
            subscription: Subscription to unsubscribe
            
        Returns:
            Dict with execution results (success, status_code, error_message, etc.)
        """
        # Dry-run mode
        if self.dry_run:
            return {
                'success': True,
                'dry_run': True,
                'message': f'DRY RUN: Would POST to {subscription.unsubscribe_link}'
            }
        
        # Execute HTTP POST request
        try:
            headers = {
                'User-Agent': self.user_agent,
                'List-Unsubscribe': 'One-Click'  # RFC 8058 compliance
            }
            
            response = requests.post(
                subscription.unsubscribe_link,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            # Consider 2xx status codes as success
            success = 200 <= response.status_code < 300
            
            return {
                'success': success,
                'status_code': response.status_code,
                'message': response.text[:200] if not success else 'Successfully unsubscribed'
            }
            
        except requests.exceptions.Timeout as e:
            return {
                'success': False,
                'error_message': f'Request timed out after {self.timeout} seconds'
            }
            
        except requests.exceptions.ConnectionError as e:
            return {
                'success': False,
                'error_message': f'Connection error: {str(e)}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error_message': f'Unexpected error: {str(e)}'
            }
