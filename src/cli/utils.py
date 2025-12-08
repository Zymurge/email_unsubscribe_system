"""
Common utilities for CLI commands.

Shared helper functions used across multiple command modules.
"""

import getpass
from src.config.credentials import get_credential_store


def get_password_for_account(email_address: str) -> str:
    """
    Get password for an account, checking credential store first.
    
    Args:
        email_address: Email address to get password for
        
    Returns:
        Password (from store or prompted)
    """
    cred_store = get_credential_store()
    stored_password = cred_store.get_password(email_address)
    
    if stored_password:
        print(f"Using stored credentials for {email_address}")
        return stored_password
    
    return getpass.getpass(f"Password for {email_address}: ")


def parse_subscription_ids(id_string: str) -> list:
    """
    Parse subscription IDs from various formats.
    
    Supports:
        - Single ID: "5"
        - Comma-separated: "1,2,3"
        - Ranges: "1-5"
        - Mixed: "1,3-5,7"
    
    Returns:
        List of integer IDs
    """
    ids = []
    parts = id_string.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range
            start, end = part.split('-')
            ids.extend(range(int(start), int(end) + 1))
        else:
            # Single ID
            ids.append(int(part))
    
    return ids
