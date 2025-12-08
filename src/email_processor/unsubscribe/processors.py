"""
Unsubscribe processing pipeline and method management.

This module handles the complete unsubscribe processing workflow:
- Processing emails for unsubscribe methods
- Managing method conflicts and updates
- Subscription database integration
- Method priority and selection logic
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from .extractors import UnsubscribeLinkExtractor
from .classifiers import UnsubscribeMethodClassifier
from .validators import UnsubscribeSafetyValidator
from .logging import UnsubscribeLogger
from ...database.models import Subscription


class UnsubscribeProcessor:
    """Main processor for handling complete unsubscribe extraction pipeline."""
    
    def __init__(self):
        self.extractor = UnsubscribeLinkExtractor()
        self.classifier = UnsubscribeMethodClassifier()
        self.validator = UnsubscribeSafetyValidator()
        self.logger = UnsubscribeLogger("unsubscribe_processor")
        
        # Method priority for single email (higher number = higher priority)
        self.method_priority = {
            'one_click': 4,
            'http_post': 3,
            'http_get': 2,
            'email_reply': 1,
            'manual_intervention': 0,  # Lowest priority - requires human action
            'invalid': 0
        }
    
    def process_email_for_unsubscribe_methods(self, headers: Dict[str, str], 
                                            html_content: Optional[str], 
                                            text_content: Optional[str]) -> Dict[str, Any]:
        """Process an email to extract and classify all unsubscribe methods."""
        
        # Extract all unsubscribe links from headers and body
        all_links = self.extractor.extract_all_unsubscribe_methods(headers, html_content, text_content)
        
        # Also look for form-based unsubscribe methods in HTML
        if html_content:
            form_methods = self._extract_form_methods(html_content)
            all_links.extend(form_methods)
        
        # Remove duplicates while preserving order
        all_links = list(dict.fromkeys(all_links))
        
        if not all_links:
            return {
                'methods': [],
                'primary_method': None,
                'total_methods': 0
            }
        
        # Remove duplicates while preserving order
        all_links = list(dict.fromkeys(all_links))
        
        # Classify each method and validate safety
        methods = []
        for link in all_links:
            # Classify the method
            method_info = self.classifier.classify_method(link, headers, html_content)
            
            # Check for form complexity requiring manual intervention
            if (method_info.get('method') == 'http_post' and 
                method_info.get('form_complexity', {}).get('requires_manual_intervention', False)):
                
                # Reclassify as manual intervention
                method_info = {
                    'method': 'manual_intervention',
                    'url': link,
                    'original_method': 'http_post',
                    'complexity_reason': method_info['form_complexity']['complexity_reason'],
                    'confidence': 'manual_required',
                    'requires_manual_intervention': True
                }
                
                self.logger.info("Reclassified method as manual intervention due to form complexity", {
                    'url': link,
                    'complexity_reason': method_info['complexity_reason'],
                    'original_method': 'http_post'
                })
            
            # Validate safety
            safety_check = self.validator.validate_safety(link)
            method_info['safety_check'] = safety_check
            
            methods.append(method_info)
        
        # Determine primary method based on priority
        primary_method = self._get_primary_method(methods)
        
        return {
            'methods': methods,
            'primary_method': primary_method,
            'total_methods': len(methods)
        }
    
    def _get_primary_method(self, methods: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get the primary (highest priority) method from a list."""
        if not methods:
            return None
        
        # Sort by priority (highest first)
        sorted_methods = sorted(
            methods, 
            key=lambda m: self.method_priority.get(m['method'], 0),
            reverse=True
        )
        
        return sorted_methods[0]
    
    def _extract_form_methods(self, html_content: str) -> List[str]:
        """Extract form action URLs that might be unsubscribe methods."""
        form_urls = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            forms = soup.find_all('form')
            
            for form in forms:
                action = form.get('action', '')
                if action:
                    # Extract ALL form action URLs, not just those with unsubscribe keywords
                    # The classifier will determine if they're actually unsubscribe-related
                    form_urls.append(action)
                    
        except Exception:
            pass
            
        return form_urls
    
    def get_unsubscribe_candidates(self, account_id: int, session: Session) -> List[Subscription]:
        """Get subscriptions eligible for unsubscribe processing."""
        return session.query(Subscription).filter(
            Subscription.account_id == account_id,
            Subscription.keep_subscription == False,  # Not marked to keep
            Subscription.unsubscribe_status != 'unsubscribed'  # Not already unsubscribed
        ).all()
    
    def update_subscription_unsubscribe_info(self, subscription_id: int, 
                                           headers: Dict[str, str],
                                           html_content: Optional[str], 
                                           text_content: Optional[str],
                                           session: Session,
                                           email_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Update subscription with unsubscribe information from email."""
        
        subscription = session.get(Subscription, subscription_id)
        if not subscription:
            return {'error': 'Subscription not found'}
        
        # Skip if marked to keep
        if subscription.should_skip_unsubscribe():
            return {'skipped': True, 'reason': 'subscription_marked_to_keep_or_already_unsubscribed'}
        
        # Process email for unsubscribe methods
        result = self.process_email_for_unsubscribe_methods(headers, html_content, text_content)
        
        if not result['methods']:
            return {'updated': False, 'reason': 'no_unsubscribe_methods_found'}
        
        # Use primary method to update subscription
        primary_method = result['primary_method']
        if primary_method and primary_method['safety_check']['is_safe']:
            # Update subscription with most recent method (most recent email wins rule)
            subscription.unsubscribe_link = primary_method.get('url', primary_method.get('action_url'))
            subscription.unsubscribe_method = primary_method['method']
            
            # Store complexity information for manual intervention methods
            if primary_method['method'] == 'manual_intervention':
                subscription.unsubscribe_complexity = primary_method.get('complexity_reason', 'unknown')
            
            subscription.updated_at = datetime.now()
            
            session.commit()
            
            return {
                'updated': True,
                'method': primary_method['method'],
                'link': subscription.unsubscribe_link,
                'email_date': email_date
            }
        
        return {'updated': False, 'reason': 'unsafe_or_invalid_method'}


class UnsubscribeMethodConflictResolver:
    """Handle conflicts when multiple emails have different unsubscribe methods."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def update_subscription_methods(self, subscription_id: int, 
                                  methods: List[Dict[str, Any]], 
                                  email_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Update subscription methods following 'most recent email wins' rule."""
        
        subscription = self.session.get(Subscription, subscription_id)
        if not subscription:
            return {'error': 'Subscription not found'}
        
        if not methods:
            return {'updated': False, 'reason': 'no_methods_provided'}
        
        # Get the primary method (highest priority within this email)
        processor = UnsubscribeProcessor()
        primary_method = processor._get_primary_method(methods)
        
        if primary_method:
            # Update with most recent method (this email's method wins)
            subscription.unsubscribe_link = primary_method.get('url', primary_method.get('action_url'))
            subscription.unsubscribe_method = primary_method['method']
            subscription.updated_at = email_date or datetime.now()
            
            self.session.commit()
            
            return {
                'updated': True,
                'method': primary_method['method'],
                'email_date': email_date
            }
        
        return {'updated': False, 'reason': 'no_valid_methods'}
    
    def get_method_history(self, subscription_id: int) -> List[Dict[str, Any]]:
        """Get method change history for a subscription (placeholder for future implementation)."""
        # This would require a separate history table in a full implementation
        # For now, return current method only
        subscription = self.session.get(Subscription, subscription_id)
        if subscription:
            return [{
                'method': subscription.unsubscribe_method,
                'link': subscription.unsubscribe_link,
                'updated_at': subscription.updated_at
            }]
        return []


class UnsubscribeMethodUpdater:
    """Update subscription methods when better methods are found."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def update_if_better(self, subscription_id: int, new_method: Dict[str, Any]) -> Dict[str, Any]:
        """Update subscription if new method is from more recent email (most recent wins rule)."""
        
        subscription = self.session.get(Subscription, subscription_id)
        if not subscription:
            return {'error': 'Subscription not found'}
        
        # In "most recent email wins" rule, we always update with the new method
        # since it represents a more recent email
        subscription.unsubscribe_link = new_method.get('url', new_method.get('action_url'))
        subscription.unsubscribe_method = new_method['method']
        subscription.updated_at = datetime.now()
        
        self.session.commit()
        
        return {
            'updated': True,
            'reason': 'most_recent_email_wins',
            'new_method': new_method['method']
        }