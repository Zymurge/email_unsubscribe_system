"""
Email processing modules.
"""

from .scanner import EmailScanner
from .imap_client import IMAPConnection, get_imap_settings

__all__ = ['EmailScanner', 'IMAPConnection', 'get_imap_settings']