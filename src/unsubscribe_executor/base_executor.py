"""
Base Unsubscribe Executor

Provides common functionality for all unsubscribe execution methods:
- Common validation logic (keep status, unsubscribe status, link existence)
- Rate limiting enforcement
- Attempt tracking and recording
- Template method pattern for execution workflow
- Dry-run mode support

This eliminates code duplication across HTTP GET, HTTP POST, and Email Reply executors.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.database.models import Subscription, UnsubscribeAttempt


class BaseUnsubscribeExecutor(ABC):
    """
    Abstract base class for all unsubscribe executors.
    
    Implements common validation, rate limiting, and attempt tracking.
    Subclasses override method-specific validation and execution logic.
    """
    
    def __init__(
        self,
        session: Session,
        max_attempts: int = 3,
        timeout: int = 30,
        rate_limit_delay: float = 2.0,
        dry_run: bool = False
    ):
        """
        Initialize base executor.
        
        Args:
            session: Database session
            max_attempts: Maximum retry attempts before giving up
            timeout: Request timeout in seconds
            rate_limit_delay: Delay in seconds between requests
            dry_run: If True, simulate without actual execution
        """
        self.session = session
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self.dry_run = dry_run
        self._last_request_time: Optional[float] = None
    
    @property
    @abstractmethod
    def method_name(self) -> str:
        """Return the method name (http_get, http_post, email_reply)."""
        pass
    
    def should_execute(self, subscription_id: int) -> Dict[str, Any]:
        """
        Check if subscription should be processed for unsubscribe.
        
        Performs common validation checks:
        - Subscription exists
        - Not marked to keep
        - Not already unsubscribed
        - Has unsubscribe link
        - Correct method type (delegated to subclass)
        - Under max attempts limit
        
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
        
        # Validate method type (subclass-specific)
        method_check = self._validate_method(subscription)
        if not method_check['should_execute']:
            return method_check
        
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
            'reason': 'All checks passed'
        }
    
    def _validate_method(self, subscription: Subscription) -> Dict[str, Any]:
        """
        Validate that subscription has correct unsubscribe method.
        
        Override in subclass to check method type.
        
        Args:
            subscription: Subscription to validate
            
        Returns:
            Dict with 'should_execute' (bool) and 'reason' (str)
        """
        if subscription.unsubscribe_method != self.method_name:
            return {
                'should_execute': False,
                'reason': f'Method mismatch: {subscription.unsubscribe_method} (expected {self.method_name})'
            }
        
        return {
            'should_execute': True,
            'reason': 'Method matches'
        }
    
    def execute(self, subscription_id: int) -> Dict[str, Any]:
        """
        Execute unsubscribe request (template method).
        
        Workflow:
        1. Validate subscription (should_execute checks)
        2. Apply rate limiting
        3. Perform method-specific execution (dry-run or real)
        4. Record attempt in database
        5. Update subscription if successful
        
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
        
        # Perform method-specific execution
        result = self._perform_execution(subscription)
        
        # Record attempt (skip for dry-run)
        if not result.get('dry_run'):
            self._record_attempt(
                subscription_id=subscription_id,
                success=result.get('success', False),
                response_code=result.get('status_code'),
                error_message=result.get('error_message')
            )
        
        # Update subscription if successful and not dry-run
        if result.get('success') and not result.get('dry_run'):
            subscription.unsubscribed_at = datetime.now()
            subscription.unsubscribe_status = 'unsubscribed'
            self.session.commit()
        
        return result
    
    @abstractmethod
    def _perform_execution(self, subscription: Subscription) -> Dict[str, Any]:
        """
        Perform method-specific unsubscribe execution.
        
        Override in subclass to implement HTTP GET, HTTP POST, or Email Reply logic.
        
        Args:
            subscription: Subscription to unsubscribe
            
        Returns:
            Dict with at minimum:
            - success (bool): Whether execution succeeded
            - dry_run (bool, optional): If this was a dry-run
            - status_code (int, optional): HTTP status or similar
            - error_message (str, optional): Error details if failed
            - message (str, optional): Success/status message
        """
        pass
    
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
            method_used=self.method_name,
            status='success' if success else 'failed',
            response_code=response_code,
            error_message=error_message
        )
        self.session.add(attempt)
        self.session.commit()
