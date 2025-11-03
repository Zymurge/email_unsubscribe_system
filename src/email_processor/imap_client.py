"""
IMAP email connection and message retrieval.
"""

import imaplib
import email
import ssl
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from email.message import EmailMessage
from email.utils import parsedate_to_datetime, parseaddr


class IMAPConnection:
    """Manages IMAP connection to email servers."""
    
    def __init__(self, server: str, port: int = 993, use_ssl: bool = True):
        self.server = server
        self.port = port
        self.use_ssl = use_ssl
        self.connection = None
        
    def connect(self, username: str, password: str) -> bool:
        """Connect to the IMAP server and authenticate."""
        try:
            if self.use_ssl:
                self.connection = imaplib.IMAP4_SSL(self.server, self.port)
            else:
                self.connection = imaplib.IMAP4(self.server, self.port)
                
            self.connection.login(username, password)
            return True
            
        except Exception as e:
            print(f"Failed to connect to IMAP server: {e}")
            return False
            
    def disconnect(self):
        """Close the IMAP connection."""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None
            
    def list_folders(self) -> List[str]:
        """List all available folders."""
        if not self.connection:
            return []
            
        try:
            status, folders = self.connection.list()
            if status != 'OK':
                return []
                
            folder_names = []
            for folder in folders:
                # Parse folder name from IMAP response
                folder_str = folder.decode('utf-8')
                # Extract folder name (basic parsing)
                parts = folder_str.split('"')
                if len(parts) >= 3:
                    folder_names.append(parts[-2])
                    
            return folder_names
            
        except Exception as e:
            print(f"Error listing folders: {e}")
            return []
            
    def select_folder(self, folder: str = 'INBOX') -> bool:
        """Select a folder for operations."""
        if not self.connection:
            return False
            
        try:
            status, _ = self.connection.select(folder)
            return status == 'OK'
        except Exception as e:
            print(f"Error selecting folder {folder}: {e}")
            return False
            
    def search_messages(self, criteria: str = 'ALL', limit: Optional[int] = None) -> List[int]:
        """Search for messages matching criteria."""
        if not self.connection:
            return []
            
        try:
            status, message_ids = self.connection.search(None, criteria)
            if status != 'OK':
                return []
                
            ids = message_ids[0].split()
            # Convert to integers and optionally limit
            uid_list = [int(uid) for uid in ids]
            
            if limit:
                # Return the most recent messages
                uid_list = uid_list[-limit:]
                
            return uid_list
            
        except Exception as e:
            print(f"Error searching messages: {e}")
            return []
            
    def fetch_message(self, uid: int) -> Optional[Dict[str, Any]]:
        """Fetch a single message by UID."""
        if not self.connection:
            return None
            
        try:
            status, msg_data = self.connection.fetch(str(uid), '(RFC822)')
            if status != 'OK':
                return None
                
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            return self._parse_email_message(email_message, uid)
            
        except Exception as e:
            print(f"Error fetching message {uid}: {e}")
            return None
            
    def fetch_messages(self, uids: List[int]) -> List[Dict[str, Any]]:
        """Fetch multiple messages by UID."""
        messages = []
        for uid in uids:
            msg = self.fetch_message(uid)
            if msg:
                messages.append(msg)
        return messages
        
    def _parse_email_message(self, email_msg: EmailMessage, uid: int) -> Dict[str, Any]:
        """Parse an email message into a dictionary."""
        # Extract basic headers
        subject = email_msg.get('Subject', '')
        from_header = email_msg.get('From', '')
        date_header = email_msg.get('Date', '')
        message_id = email_msg.get('Message-ID', '')
        
        # Parse sender information
        sender_name, sender_email = parseaddr(from_header)
        sender_name = sender_name.strip('"') if sender_name else ''
        
        # Parse date
        date_sent = None
        if date_header:
            try:
                date_sent = parsedate_to_datetime(date_header)
                # Convert to UTC if timezone aware
                if date_sent.tzinfo is not None:
                    date_sent = date_sent.astimezone(timezone.utc).replace(tzinfo=None)
            except:
                pass
                
        # Check for unsubscribe headers
        list_unsubscribe = email_msg.get('List-Unsubscribe', '')
        list_unsubscribe_post = email_msg.get('List-Unsubscribe-Post', '')
        list_id = email_msg.get('List-ID', '')
        
        has_unsubscribe_header = bool(list_unsubscribe or list_unsubscribe_post)
        
        # Extract email body for link detection
        body_text = self._extract_email_body(email_msg)
        
        return {
            'uid': uid,
            'message_id': message_id,
            'sender_email': sender_email.lower() if sender_email else '',
            'sender_name': sender_name,
            'subject': subject,
            'date_sent': date_sent,
            'has_unsubscribe_header': has_unsubscribe_header,
            'list_unsubscribe': list_unsubscribe,
            'list_unsubscribe_post': list_unsubscribe_post,
            'list_id': list_id,
            'body_text': body_text,
        }
        
    def _extract_email_body(self, email_msg: EmailMessage) -> str:
        """Extract text content from email message."""
        body_text = ""
        
        try:
            if email_msg.is_multipart():
                for part in email_msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        charset = part.get_content_charset() or 'utf-8'
                        body_text += part.get_payload(decode=True).decode(charset, errors='ignore')
                    elif content_type == "text/html" and not body_text:
                        # Use HTML as fallback if no plain text
                        charset = part.get_content_charset() or 'utf-8'
                        body_text = part.get_payload(decode=True).decode(charset, errors='ignore')
            else:
                charset = email_msg.get_content_charset() or 'utf-8'
                body_text = email_msg.get_payload(decode=True).decode(charset, errors='ignore')
                
        except Exception as e:
            print(f"Error extracting email body: {e}")
            
        return body_text[:10000]  # Limit body text to prevent huge storage
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


def get_imap_settings(provider: str) -> Dict[str, Any]:
    """Get IMAP settings for common email providers."""
    settings = {
        'gmail': {
            'server': 'imap.gmail.com',
            'port': 993,
            'use_ssl': True,
        },
        'comcast': {
            'server': 'imap.comcast.net',
            'port': 993,
            'use_ssl': True,
        },
        'outlook': {
            'server': 'outlook.office365.com',
            'port': 993,
            'use_ssl': True,
        },
        'yahoo': {
            'server': 'imap.mail.yahoo.com',
            'port': 993,
            'use_ssl': True,
        },
    }
    
    return settings.get(provider.lower(), {
        'server': f'imap.{provider.lower()}.com',
        'port': 993,
        'use_ssl': True,
    })