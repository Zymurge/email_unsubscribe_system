"""
Hybrid Combined Email Scanner with Integrated Subscription Detection and Unsubscribe Extraction.

This module implements the combined scan+analyze approach where email scanning,
subscription detection, and unsubscribe method extraction happen in a single pass
while the full email content is available.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..database.models import Account, EmailMessage, Subscription
from .imap_client import IMAPConnection, get_imap_settings
from .subscription_detector import SubscriptionDetector
from .unsubscribe import (
    UnsubscribeLinkExtractor, 
    UnsubscribeMethodClassifier,
    UnsubscribeSafetyValidator,
    UnsubscribeProcessor
)
from .unsubscribe.logging import configure_unsubscribe_logging

# Set up logging
logger = logging.getLogger(__name__)


class CombinedEmailScanner:
    """
    Hybrid scanner that performs email scanning, subscription detection, 
    and unsubscribe extraction in a single pass.
    """
    
    def __init__(self, session: Session, enable_debug_storage: bool = False):
        self.session = session
        self.enable_debug_storage = enable_debug_storage
        
        # Initialize components
        self.subscription_detector = SubscriptionDetector()
        self.unsubscribe_extractor = UnsubscribeLinkExtractor()
        self.unsubscribe_classifier = UnsubscribeMethodClassifier()
        self.unsubscribe_validator = UnsubscribeSafetyValidator()
        self.unsubscribe_processor = UnsubscribeProcessor()
        
        # Configure logging
        configure_unsubscribe_logging()
        
        logger.info(f"Initialized CombinedEmailScanner with debug_storage={enable_debug_storage}")
    
    def scan_account_with_analysis(
        self, 
        account_id: int, 
        password: str,
        folder: str = 'INBOX', 
        days_back: Optional[int] = None, 
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scan account emails with integrated subscription detection and unsubscribe extraction.
        
        Args:
            account_id: Account to scan
            password: Account password for IMAP connection
            folder: Email folder to scan
            days_back: Only scan emails from N days back
            limit: Maximum messages to process
            
        Returns:
            Dict with detailed processing results
        """
        account = self.session.query(Account).get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        logger.info(f"Starting combined scan for account {account.email_address}")
        
        # Get IMAP settings
        imap_settings = get_imap_settings(account.provider)
        
        with IMAPConnection(
            imap_settings['server'], 
            imap_settings['port'], 
            imap_settings['use_ssl']
        ) as imap:
            if not imap.connect(account.email_address, password):
                raise ConnectionError(f"Failed to connect to {account.email_address}")
            
            if not imap.select_folder(folder):
                raise ValueError(f"Failed to select folder {folder}")
            
            # Build search criteria
            if days_back:
                since_date = datetime.now() - timedelta(days=days_back)
                date_str = since_date.strftime("%d-%b-%Y")
                search_criteria = f'SINCE {date_str}'
            else:
                search_criteria = 'ALL'
            
            # Search for messages
            message_uids = imap.search_messages(search_criteria, limit)
            logger.info(f"Found {len(message_uids)} messages to process")
            logger.debug(f"Search criteria: {search_criteria}")
            logger.debug(f"Message UIDs: {message_uids[:10] if len(message_uids) > 10 else message_uids}")
            
            # Get existing message UIDs to avoid duplicates
            existing_messages = self.session.query(EmailMessage.uid).filter(
                and_(
                    EmailMessage.account_id == account_id,
                    EmailMessage.folder == folder
                )
            ).all()
            existing_uids = {msg.uid for msg in existing_messages}
            
            # Filter out already processed messages
            new_uids = [uid for uid in message_uids if uid not in existing_uids]
            logger.info(f"Processing {len(new_uids)} new messages")
            logger.debug(f"Found UIDs: {message_uids[:10] if len(message_uids) > 10 else message_uids}")
            logger.debug(f"Existing UIDs: {len(existing_uids)} ({list(existing_uids)[:10] if len(existing_uids) > 10 else list(existing_uids)})")
            logger.debug(f"New UIDs: {new_uids[:10] if len(new_uids) > 10 else new_uids}")
            
            # Process messages with combined analysis
            results = self._process_messages_with_analysis(
                imap, account_id, folder, new_uids
            )
            
            # Update account last scan time
            account.last_scan = datetime.now()
            self.session.commit()
            
            logger.info(f"Completed combined scan: {results}")
            return results
    
    def _process_messages_with_analysis(
        self, 
        imap: IMAPConnection, 
        account_id: int, 
        folder: str, 
        message_uids: List[int]
    ) -> Dict[str, Any]:
        """Process messages with integrated subscription detection and unsubscribe extraction."""
        
        # Results tracking
        results = {
            'processed_emails': 0,
            'email_errors': 0,
            'subscriptions_created': 0,
            'subscriptions_updated': 0,
            'unsubscribe_methods_extracted': 0,
            'total_found': len(message_uids)
        }
        
        # Track subscriptions by sender for aggregation
        subscriptions_by_sender = {}
        processed_emails = []
        
        # Process messages in batches
        batch_size = 50
        for i in range(0, len(message_uids), batch_size):
            batch = message_uids[i:i + batch_size]
            batch_results = self._process_message_batch(
                imap, account_id, folder, batch, subscriptions_by_sender
            )
            
            # Accumulate results
            results['processed_emails'] += batch_results['processed_emails']
            results['email_errors'] += batch_results['email_errors']
            processed_emails.extend(batch_results['email_messages'])
            
            # Save email batch to database
            if batch_results['email_messages']:
                self.session.add_all(batch_results['email_messages'])
                self.session.commit()
            
            logger.info(f"Processed batch: {len(batch_results['email_messages'])} messages")
        
        # Create/update subscription records with aggregated data
        subscription_results = self._create_subscription_records(
            account_id, subscriptions_by_sender
        )
        
        results.update(subscription_results)
        
        return results
    
    def _process_message_batch(
        self, 
        imap: IMAPConnection, 
        account_id: int, 
        folder: str, 
        batch_uids: List[int],
        subscriptions_by_sender: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process a batch of messages with combined analysis."""
        
        email_messages = []
        processed_emails = 0
        email_errors = 0
        
        for uid in batch_uids:
            try:
                # Fetch full message data
                msg_data = imap.fetch_message(uid)
                if not msg_data:
                    email_errors += 1
                    continue
                
                # Perform combined analysis on this message
                analysis_result = self._analyze_single_message(msg_data, account_id)
                
                # Create email record with analysis results
                email_msg = EmailMessage(
                    account_id=account_id,
                    message_id=msg_data['message_id'],
                    uid=uid,
                    folder=folder,
                    sender_email=msg_data['sender_email'],
                    sender_name=msg_data['sender_name'],
                    subject=msg_data['subject'],
                    date_sent=msg_data['date_sent'],
                    has_unsubscribe_header=analysis_result['has_unsubscribe_header'],
                    has_unsubscribe_link=analysis_result['has_unsubscribe_link'],
                    processed_for_subscriptions=True  # Mark as processed since we did combined analysis
                )
                
                # Add debug storage if enabled
                if self.enable_debug_storage:
                    email_msg.unsubscribe_headers_json = analysis_result.get('debug_headers_json')
                    email_msg.unsubscribe_links_found = analysis_result.get('debug_links_json') 
                    email_msg.processing_notes = analysis_result.get('debug_notes')
                
                email_messages.append(email_msg)
                
                # Aggregate subscription data
                sender_email = msg_data['sender_email']
                if sender_email not in subscriptions_by_sender:
                    subscriptions_by_sender[sender_email] = {
                        'emails': [],
                        'unsubscribe_methods': [],
                        'has_unsubscribe_capability': False
                    }
                
                subscriptions_by_sender[sender_email]['emails'].append({
                    'message_data': msg_data,
                    'analysis': analysis_result,
                    'date_sent': msg_data['date_sent']
                })
                
                # Track unsubscribe capability
                if analysis_result.get('unsubscribe_methods'):
                    subscriptions_by_sender[sender_email]['has_unsubscribe_capability'] = True
                    subscriptions_by_sender[sender_email]['unsubscribe_methods'].extend(
                        analysis_result['unsubscribe_methods']
                    )
                
                processed_emails += 1
                
            except Exception as e:
                logger.error(f"Error processing message {uid}: {e}")
                email_errors += 1
        
        return {
            'email_messages': email_messages,
            'processed_emails': processed_emails,
            'email_errors': email_errors
        }
    
    def _analyze_single_message(self, msg_data: Dict[str, Any], account_id: int) -> Dict[str, Any]:
        """Perform combined subscription detection and unsubscribe extraction on a single message."""
        
        analysis = {
            'has_unsubscribe_header': msg_data.get('has_unsubscribe_header', False),
            'has_unsubscribe_link': False,
            'unsubscribe_methods': [],
            'subscription_confidence': 0,
            'debug_headers_json': None,
            'debug_links_json': None,
            'debug_notes': None
        }
        
        try:
            # Extract headers for analysis
            headers = msg_data.get('headers', {})
            html_content = msg_data.get('body_html', '')
            text_content = msg_data.get('body_text', '')
            
            # 1. Basic unsubscribe link detection
            analysis['has_unsubscribe_link'] = self._has_unsubscribe_link(text_content)
            
            # 2. Extract unsubscribe methods using our Phase 3 system
            if headers or html_content or text_content:
                unsubscribe_links = self.unsubscribe_extractor.extract_all_unsubscribe_methods(
                    headers, html_content, text_content
                )
                
                # Classify and validate methods for each link
                classified_methods = []
                for link in unsubscribe_links:
                    # Classify the method using headers for context
                    classified = self.unsubscribe_classifier.classify_method(link, headers, html_content)
                    if classified and classified.get('url'):
                        try:
                            # Validate safety
                            validation = self.unsubscribe_validator.validate_safety(classified['url'])
                            if validation.get('is_safe', False):
                                classified_methods.append(classified)
                        except Exception as e:
                            logger.error(f"Error validating URL {classified.get('url')}: {e}")
                            # Skip this method but continue processing
                
                analysis['unsubscribe_methods'] = classified_methods
                
                # Update flags based on extraction results
                if classified_methods:
                    analysis['has_unsubscribe_link'] = True
            
            # 3. Calculate subscription confidence
            analysis['subscription_confidence'] = self._calculate_subscription_confidence(
                msg_data, analysis
            )
            
            # 4. Store debug information if enabled
            if self.enable_debug_storage:
                debug_info = {
                    'extraction_methods_found': len(analysis['unsubscribe_methods']),
                    'header_analysis': bool(headers.get('List-Unsubscribe')),
                    'body_analysis': analysis['has_unsubscribe_link'],
                    'processing_timestamp': datetime.now().isoformat()
                }
                
                analysis['debug_headers_json'] = json.dumps({
                    k: v for k, v in headers.items() 
                    if 'unsubscribe' in k.lower() or 'list-' in k.lower()
                }) if headers else None
                
                analysis['debug_links_json'] = json.dumps([
                    method.get('url') for method in analysis['unsubscribe_methods']
                    if method.get('url')
                ]) if analysis['unsubscribe_methods'] else json.dumps([])
                
                analysis['debug_notes'] = json.dumps(debug_info)
            
        except Exception as e:
            logger.error(f"Error in message analysis: {e}")
            if self.enable_debug_storage:
                analysis['debug_notes'] = json.dumps({'error': str(e), 'processing_timestamp': datetime.now().isoformat()})
            else:
                analysis['debug_notes'] = None
        
        return analysis
    
    def _calculate_subscription_confidence(self, msg_data: Dict[str, Any], analysis: Dict[str, Any]) -> int:
        """Calculate subscription confidence score based on message content and analysis."""
        confidence = 0
        
        # Base confidence from sender patterns
        sender_email = msg_data.get('sender_email', '').lower()
        if any(keyword in sender_email for keyword in ['no-reply', 'noreply', 'donotreply']):
            confidence += 20
        
        # Marketing keywords in subject
        subject = msg_data.get('subject', '').lower()
        marketing_keywords = {
            'newsletter', 'sale', 'deal', 'offer', 'discount', 'promo', 
            'exclusive', 'limited', 'update', 'news'
        }
        keyword_matches = sum(1 for keyword in marketing_keywords if keyword in subject)
        confidence += min(keyword_matches * 15, 45)
        
        # Unsubscribe capability adds confidence
        if analysis.get('has_unsubscribe_header'):
            confidence += 25
        if analysis.get('unsubscribe_methods'):
            confidence += 20
        
        # Domain patterns
        domain = sender_email.split('@')[-1] if '@' in sender_email else ''
        if any(pattern in domain for pattern in ['mail.', 'email.', 'news.', 'marketing.']):
            confidence += 15
        
        return min(confidence, 100)
    
    def _has_unsubscribe_link(self, body_text: str) -> bool:
        """Enhanced unsubscribe link detection."""
        if not body_text:
            return False
        
        body_lower = body_text.lower()
        unsubscribe_patterns = [
            'unsubscribe',
            'opt out',
            'opt-out', 
            'remove me',
            'stop emails',
            'manage preferences',
            'email preferences',
            'update preferences'
        ]
        
        return any(pattern in body_lower for pattern in unsubscribe_patterns)
    
    def _create_subscription_records(
        self, 
        account_id: int, 
        subscriptions_by_sender: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create or update subscription records with aggregated unsubscribe information."""
        
        created = 0
        updated = 0
        methods_extracted = 0
        
        for sender_email, sender_data in subscriptions_by_sender.items():
            try:
                # Check if subscription exists
                existing_subscription = self.session.query(Subscription).filter(
                    and_(
                        Subscription.account_id == account_id,
                        Subscription.sender_email == sender_email
                    )
                ).first()
                
                # Calculate aggregated subscription data
                emails = sender_data['emails']
                if not emails:
                    continue
                
                # Get the most recent email for primary data
                latest_email = max(emails, key=lambda x: x['date_sent'] or datetime.min)
                msg_data = latest_email['message_data']
                
                # Aggregate unsubscribe methods (use most recent valid method)
                all_methods = sender_data['unsubscribe_methods']
                primary_method = None
                unsubscribe_link = None
                unsubscribe_method = None
                
                if all_methods:
                    # Use the most recent valid method
                    primary_method = all_methods[-1]  # Last method found
                    unsubscribe_link = primary_method.get('url') or primary_method.get('action_url')
                    unsubscribe_method = primary_method.get('method', 'http_get')
                    methods_extracted += 1
                
                # Calculate overall confidence
                confidence_scores = [email['analysis']['subscription_confidence'] for email in emails]
                avg_confidence = int(sum(confidence_scores) / len(confidence_scores))
                
                if existing_subscription:
                    # Update existing subscription
                    existing_subscription.email_count = len(emails)
                    existing_subscription.last_seen = latest_email['date_sent'] or datetime.now()
                    existing_subscription.confidence_score = avg_confidence
                    
                    # Update unsubscribe info with most recent method
                    if unsubscribe_link and unsubscribe_method:
                        existing_subscription.unsubscribe_link = unsubscribe_link
                        existing_subscription.unsubscribe_method = unsubscribe_method
                    
                    existing_subscription.updated_at = datetime.now()
                    updated += 1
                    
                else:
                    # Create new subscription
                    new_subscription = Subscription(
                        account_id=account_id,
                        sender_email=sender_email,
                        sender_name=msg_data.get('sender_name'),
                        sender_domain=sender_email.split('@')[-1] if '@' in sender_email else '',
                        subject_pattern=msg_data.get('subject', '')[:100],  # Truncate for storage
                        unsubscribe_link=unsubscribe_link,
                        unsubscribe_method=unsubscribe_method,
                        confidence_score=avg_confidence,
                        email_count=len(emails),
                        discovered_at=datetime.now(),
                        last_seen=latest_email['date_sent'] or datetime.now()
                    )
                    
                    self.session.add(new_subscription)
                    created += 1
                
            except Exception as e:
                logger.error(f"Error creating subscription record for {sender_email}: {e}")
        
        # Commit all subscription changes
        self.session.commit()
        
        return {
            'subscriptions_created': created,
            'subscriptions_updated': updated,
            'unsubscribe_methods_extracted': methods_extracted
        }