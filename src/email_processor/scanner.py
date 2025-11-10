"""
Email scanner that processes messages and stores them in the database.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..database.models import Account, EmailMessage
from ..database import get_db_manager
from .imap_client import IMAPConnection, get_imap_settings


class EmailScanner:
    """Scans email accounts and stores messages in the database."""
    
    def __init__(self, session: Session):
        self.session = session
        
    def add_account(self, email_address: str, password: str, provider: str = None) -> Optional[Account]:
        """Add a new email account to the database."""
        if not provider:
            # Try to guess provider from email domain
            domain = email_address.split('@')[1].lower()
            if 'gmail' in domain:
                provider = 'gmail'
            elif 'comcast' in domain:
                provider = 'comcast'
            elif 'outlook' in domain or 'hotmail' in domain:
                provider = 'outlook'
            elif 'yahoo' in domain:
                provider = 'yahoo'
            else:
                provider = domain.split('.')[0]
                
        # Get IMAP settings
        imap_settings = get_imap_settings(provider)
        
        # Test connection
        with IMAPConnection(
            imap_settings['server'], 
            imap_settings['port'], 
            imap_settings['use_ssl']
        ) as imap:
            if not imap.connect(email_address, password):
                print(f"Failed to connect to {email_address}")
                return None
                
        # Store account in database
        # Check if account already exists
        existing = self.session.query(Account).filter(
            Account.email_address == email_address.lower()
        ).first()
        
        if existing:
            print(f"Account {email_address} already exists")
            return existing
            
        account = Account(
            email_address=email_address.lower(),
            provider=provider,
            imap_server=imap_settings['server'],
            imap_port=imap_settings['port'],
            use_ssl=imap_settings['use_ssl']
        )
        
        self.session.add(account)
        self.session.commit()
        self.session.refresh(account)
        
        print(f"Added account: {email_address}")
        return account
            
    def scan_account(
        self, 
        account_id: int, 
        password: str, 
        folder: str = 'INBOX',
        days_back: int = 30,
        limit: Optional[int] = None
    ) -> Dict[str, int]:
        """Scan an email account for new messages."""
        
        account = self.session.query(Account).get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
            
        # Connect to IMAP
        with IMAPConnection(
            account.imap_server, 
            account.imap_port, 
            account.use_ssl
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
                print(f"Found {len(message_uids)} messages to process")
                
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
                print(f"Processing {len(new_uids)} new messages")
                
                processed = 0
                errors = 0
                
                # Process messages in batches
                batch_size = 50
                for i in range(0, len(new_uids), batch_size):
                    batch = new_uids[i:i + batch_size]
                    batch_messages = []
                    
                    for uid in batch:
                        try:
                            msg_data = imap.fetch_message(uid)
                            if msg_data:
                                # Check for unsubscribe links in body (basic check)
                                has_unsubscribe_link = self._has_unsubscribe_link(msg_data.get('body_text', ''))
                                
                                email_msg = EmailMessage(
                                    account_id=account_id,
                                    message_id=msg_data['message_id'],
                                    uid=uid,
                                    folder=folder,
                                    sender_email=msg_data['sender_email'],
                                    sender_name=msg_data['sender_name'],
                                    subject=msg_data['subject'],
                                    date_sent=msg_data['date_sent'],
                                    has_unsubscribe_header=msg_data['has_unsubscribe_header'],
                                    has_unsubscribe_link=has_unsubscribe_link
                                )
                                batch_messages.append(email_msg)
                                processed += 1
                            else:
                                errors += 1
                                
                        except Exception as e:
                            print(f"Error processing message {uid}: {e}")
                            errors += 1
                            
                    # Save batch to database
                    if batch_messages:
                        self.session.add_all(batch_messages)
                        self.session.commit()
                        
                    print(f"Processed batch: {len(batch_messages)} messages")
                    
                # Update account last scan time
                account.last_scan = datetime.now()
                self.session.commit()
                
                return {
                    'processed': processed,
                    'errors': errors,
                    'total_found': len(message_uids),
                    'already_existed': len(message_uids) - len(new_uids)
                }
                
    def _has_unsubscribe_link(self, body_text: str) -> bool:
        """Basic check for unsubscribe links in email body."""
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
            'email preferences'
        ]
        
        return any(pattern in body_lower for pattern in unsubscribe_patterns)
        
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Get all accounts from the database."""
        accounts = self.session.query(Account).all()
        return [
            {
                'id': acc.id,
                'email_address': acc.email_address,
                'provider': acc.provider,
                'last_scan': acc.last_scan,
                'message_count': len(acc.email_messages)
            }
                for acc in accounts
            ]
            
    def get_account_stats(self, account_id: int) -> Dict[str, Any]:
        """Get statistics for an account."""
        account = self.session.query(Account).get(account_id)
        if not account:
            return {}
            
        total_messages = self.session.query(EmailMessage).filter(
            EmailMessage.account_id == account_id
        ).count()
        
        messages_with_unsubscribe = self.session.query(EmailMessage).filter(
            and_(
                EmailMessage.account_id == account_id,
                or_(
                    EmailMessage.has_unsubscribe_header == True,
                    EmailMessage.has_unsubscribe_link == True
                )
                )
        ).count()
        
        # Get top senders
        from sqlalchemy import func
        top_senders = self.session.query(
                EmailMessage.sender_email,
                func.count(EmailMessage.id).label('count')
            ).filter(
                EmailMessage.account_id == account_id
            ).group_by(
                EmailMessage.sender_email
            ).order_by(
                func.count(EmailMessage.id).desc()
        ).limit(10).all()
        
        return {
            'account': {
                'email': account.email_address,
                'provider': account.provider,
                'last_scan': account.last_scan
            },
            'total_messages': total_messages,
            'messages_with_unsubscribe': messages_with_unsubscribe,
            'top_senders': [
                {'email': sender, 'count': count} 
                for sender, count in top_senders
            ]
        }