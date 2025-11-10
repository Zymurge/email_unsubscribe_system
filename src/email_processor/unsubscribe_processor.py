"""
Unsubscribe attempt tracking and processing.

This module handles:
- Creating and tracking unsubscribe attempts
- Respecting keep_subscription flags
- Recording success/failure results
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from ..database.models import Subscription, UnsubscribeAttempt


class UnsubscribeAttemptTracker:
    """Track unsubscribe attempts and their results."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_attempt(self, subscription_id: int, method_used: str, 
                      status: str = "pending") -> UnsubscribeAttempt:
        """Create a new unsubscribe attempt record."""
        
        attempt = UnsubscribeAttempt(
            subscription_id=subscription_id,
            method_used=method_used,
            status=status,
            attempted_at=datetime.now()
        )
        
        self.session.add(attempt)
        self.session.commit()
        self.session.refresh(attempt)
        
        return attempt
    
    def create_attempt_if_eligible(self, subscription_id: int) -> Dict[str, Any]:
        """Create unsubscribe attempt only if subscription is eligible."""
        
        subscription = self.session.query(Subscription).get(subscription_id)
        if not subscription:
            return {
                'created': False,
                'reason': 'subscription_not_found',
                'attempt': None
            }
        
        # Check if subscription should be skipped
        if subscription.should_skip_unsubscribe():
            if subscription.keep_subscription:
                reason = 'subscription_marked_to_keep'
            else:
                reason = 'already_unsubscribed'
                
            return {
                'created': False,
                'reason': reason,
                'attempt': None
            }
        
        # Check if subscription has unsubscribe method
        if not subscription.unsubscribe_method or not subscription.unsubscribe_link:
            return {
                'created': False,
                'reason': 'no_unsubscribe_method_available',
                'attempt': None
            }
        
        # Create the attempt
        attempt = self.create_attempt(
            subscription_id=subscription_id,
            method_used=subscription.unsubscribe_method,
            status="pending"
        )
        
        return {
            'created': True,
            'reason': 'eligible_for_unsubscribe',
            'attempt': attempt
        }
    
    def update_attempt_success(self, attempt_id: int, response_code: Optional[int] = None, 
                             response_headers: Optional[str] = None, 
                             notes: Optional[str] = None) -> Dict[str, Any]:
        """Update attempt record with success results."""
        
        attempt = self.session.query(UnsubscribeAttempt).get(attempt_id)
        if not attempt:
            return {'error': 'Attempt not found'}
        
        # Update attempt record
        attempt.status = "success"
        attempt.response_code = response_code
        attempt.response_headers = response_headers
        attempt.notes = notes
        
        # Update parent subscription
        subscription = attempt.subscription
        subscription.unsubscribe_status = "unsubscribed"
        subscription.unsubscribed_at = datetime.now()
        subscription.is_active = False
        
        self.session.commit()
        
        return {
            'updated': True,
            'attempt_status': 'success',
            'subscription_status': 'unsubscribed'
        }
    
    def update_attempt_failure(self, attempt_id: int, error_message: str, 
                             response_code: Optional[int] = None,
                             response_headers: Optional[str] = None) -> Dict[str, Any]:
        """Update attempt record with failure results."""
        
        attempt = self.session.query(UnsubscribeAttempt).get(attempt_id)
        if not attempt:
            return {'error': 'Attempt not found'}
        
        # Update attempt record
        attempt.status = "failed"
        attempt.error_message = error_message
        attempt.response_code = response_code
        attempt.response_headers = response_headers
        
        # Update parent subscription status
        subscription = attempt.subscription
        subscription.unsubscribe_status = "failed"
        
        self.session.commit()
        
        return {
            'updated': True,
            'attempt_status': 'failed',
            'subscription_status': 'failed',
            'error_message': error_message
        }