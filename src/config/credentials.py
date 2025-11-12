"""
Credential storage and retrieval for email accounts.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple


class CredentialStore:
    """Manages stored email account credentials."""
    
    def __init__(self, store_path: Optional[Path] = None):
        """
        Initialize credential store.
        
        Args:
            store_path: Path to the JSON file storing credentials.
                       If None, uses EMAIL_PSWD_STORE_PATH from config.
        """
        self.store_path = store_path
        self._credentials: Dict[str, str] = {}
        self._load_credentials()
    
    def _load_credentials(self):
        """Load credentials from disk if the file exists."""
        if self.store_path and self.store_path.exists():
            try:
                with open(self.store_path, 'r') as f:
                    data = json.load(f)
                    # Validate structure
                    if isinstance(data, dict):
                        self._credentials = data
                    else:
                        self._credentials = {}
            except (json.JSONDecodeError, IOError) as e:
                # If file is corrupted or unreadable, start fresh
                self._credentials = {}
    
    def _save_credentials(self):
        """Save credentials to disk."""
        if not self.store_path:
            return
        
        # Ensure parent directory exists
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write with proper permissions (owner read/write only)
        with open(self.store_path, 'w') as f:
            json.dump(self._credentials, f, indent=2)
        
        # Set restrictive file permissions (600 = owner read/write only)
        os.chmod(self.store_path, 0o600)
    
    def get_password(self, email_address: str) -> Optional[str]:
        """
        Get password for an email address.
        
        Args:
            email_address: Email address to look up
            
        Returns:
            Password if found, None otherwise
        """
        return self._credentials.get(email_address.lower())
    
    def set_password(self, email_address: str, password: str):
        """
        Store password for an email address.
        
        Args:
            email_address: Email address
            password: Password to store
        """
        self._credentials[email_address.lower()] = password
        self._save_credentials()
    
    def remove_password(self, email_address: str) -> bool:
        """
        Remove stored password for an email address.
        
        Args:
            email_address: Email address
            
        Returns:
            True if password was removed, False if it didn't exist
        """
        email_lower = email_address.lower()
        if email_lower in self._credentials:
            del self._credentials[email_lower]
            self._save_credentials()
            return True
        return False
    
    def list_stored_emails(self) -> List[str]:
        """
        Get list of email addresses with stored credentials.
        
        Returns:
            List of email addresses
        """
        return sorted(self._credentials.keys())
    
    def has_password(self, email_address: str) -> bool:
        """
        Check if password is stored for an email address.
        
        Args:
            email_address: Email address to check
            
        Returns:
            True if password is stored, False otherwise
        """
        return email_address.lower() in self._credentials
    
    def clear_all(self):
        """Clear all stored credentials."""
        self._credentials = {}
        self._save_credentials()


# Global credential store instance
_credential_store = None


def get_credential_store(store_path: Optional[Path] = None) -> CredentialStore:
    """
    Get the global credential store instance.
    
    Args:
        store_path: Path to credential file. If None and instance doesn't exist,
                   will use default from config.
    
    Returns:
        CredentialStore instance
    """
    global _credential_store
    
    if _credential_store is None:
        if store_path is None:
            # Import here to avoid circular dependency
            from .settings import Config
            store_path = Config.get_credential_store_path()
        
        _credential_store = CredentialStore(store_path)
    
    return _credential_store
