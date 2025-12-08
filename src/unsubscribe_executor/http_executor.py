"""
HTTP GET Unsubscribe Executor

Handles unsubscribe execution via HTTP GET requests with:
- Comprehensive safety validations (inherited from base)
- Rate limiting (inherited from base)
- Success/failure tracking (inherited from base)
- Dry-run mode support (inherited from base)
"""

import requests
from typing import Dict, Any
from sqlalchemy.orm import Session

from src.database.models import Subscription
from .base_executor import BaseUnsubscribeExecutor


class HttpGetExecutor(BaseUnsubscribeExecutor):
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
        super().__init__(session, max_attempts, timeout, rate_limit_delay, dry_run)
        self.user_agent = user_agent
    
    @property
    def method_name(self) -> str:
        """Return the method name for this executor."""
        return 'http_get'
    
    def _perform_execution(self, subscription: Subscription) -> Dict[str, Any]:
        """
        Execute unsubscribe via HTTP GET request.
        
        Args:
            subscription: Subscription to unsubscribe
            
        Returns:
            Dict with execution result including success status
        """
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
