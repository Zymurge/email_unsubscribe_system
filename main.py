#!/usr/bin/env python3
"""
Command-line interface for the email subscription manager.

Supports both legacy commands (for backward compatibility) and new click-based commands.
"""

import sys
import os
import getpass
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config import Config, load_config_from_env_file
from src.config.credentials import get_credential_store
from src.database import init_database
from src.email_processor.scanner import EmailScanner
from src.email_processor.combined_scanner import CombinedEmailScanner
from src.email_processor.subscription_detector import SubscriptionDetector
from src.email_processor.email_deleter import EmailDeleter
from src.database.violations import ViolationReporter
from src.cli_session import get_cli_session_manager, with_db_session

# Import new click-based CLI
from src.cli import cli as click_cli
from src.cli.utils import get_password_for_account


def main():
    """Main CLI entry point."""
    load_config_from_env_file()
    
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1]
    
    # Route password commands to new click-based CLI
    if command == 'password':
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        click_cli()
        return
    
    # Route account commands to new click-based CLI
    if command == 'account':
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        click_cli()
        return
    
    # Route stats to new click-based CLI
    if command == 'stats':
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        click_cli()
        return
    
    # All legacy commands - redirect to new click-based CLI
    legacy_redirects = {
        'init': ['init'],
        'add-account': ['account', 'add'],
        'list-accounts': ['account', 'list'],
        'scan': ['scan'],
        'scan-analyze': ['scan-analyze'],
        'detect-subscriptions': ['detect-subscriptions'],
        'list-subscriptions': ['list-subscriptions'],
        'violations': ['violations'],
        'unsubscribe': ['unsubscribe'],
        'store-password': ['password', 'store'],
        'remove-password': ['password', 'remove'],
        'list-passwords': ['password', 'list'],
        'keep': ['keep'],
        'unkeep': ['unkeep'],
        'delete-emails': ['delete-emails']
    }
    
    if command in legacy_redirects:
        new_command = legacy_redirects[command]
        sys.argv = ['main.py'] + new_command + sys.argv[2:]
        click_cli()
    else:
        print(f"Unknown command: {command}")
        print_usage()


def print_usage():
    """Print usage information."""
    print("""
Email Subscription Manager

Usage:
    python main.py <command> [options]

Commands:
    init                         Initialize the database
    add-account <email>          Add an email account
    scan <account_id>            Scan an account for messages (basic)
    scan-analyze <account_id>    Scan with integrated subscription detection & unsubscribe extraction
    list-accounts                List all accounts
    stats <account_id>           Show account statistics
    detect-subscriptions <id>    Detect subscriptions for account (legacy)
    violations <account_id>      Show violation reports for account
    list-subscriptions <id>      List subscriptions for account [--keep=yes|no|all]
    unsubscribe <sub_id>         Execute unsubscribe for a subscription [--dry-run] [--yes]
    delete-emails <sub_id>       Delete emails from successfully unsubscribed subscription [--dry-run] [--waiting-days N]
    keep <criteria>              Mark subscriptions to keep (skip unsubscribe) [--yes]
    unkeep <criteria>            Unmark subscriptions (make eligible for unsubscribe) [--yes]
    
    store-password <email>       Store password for an email account
    remove-password <email>      Remove stored password for an email account
    list-passwords               List email accounts with stored passwords

Options:
    --debug-storage              Store detailed extraction info (use with scan-analyze)
    --keep=yes|no|all            Filter subscriptions by keep status (default: all)
    --dry-run                    Simulate operation without making actual changes
    --yes                        Skip confirmation prompt (not allowed for delete-emails)
    --waiting-days N             Days to wait after unsubscribe before deletion (default: 7)
    --pattern <pattern>          SQL LIKE pattern for matching (use with keep/unkeep)
    --domain <domain>            Domain name for matching (use with keep/unkeep)

Examples:
    python main.py init
    python main.py add-account user@comcast.net
    python main.py store-password user@comcast.net
    python main.py scan-analyze 1                    # Combined scan+analyze (recommended)
    python main.py scan-analyze 1 --debug-storage    # With debug info storage
    python main.py scan 1                            # Basic scan only
    python main.py stats 1
    python main.py violations 1
    python main.py list-subscriptions 1              # List all subscriptions
    python main.py list-subscriptions 1 --keep=yes   # Only kept subscriptions
    python main.py list-subscriptions 1 --keep=no    # Only non-kept subscriptions
    python main.py keep 1 2 3                        # Mark specific IDs as keep
    python main.py keep 1-10                         # Mark range as keep
    python main.py keep --pattern %sutter%           # Mark by pattern
    python main.py keep --domain example.com --yes   # Mark by domain, skip confirm
    python main.py unkeep 4 5 6                      # Unmark specific IDs
    python main.py unkeep --pattern %newsletter%     # Unmark by pattern
    python main.py unsubscribe 42 --dry-run          # Test unsubscribe without executing
    python main.py unsubscribe 42                    # Execute unsubscribe (with confirmation)
    python main.py unsubscribe 42 --yes              # Execute without confirmation
    python main.py delete-emails 42 --dry-run        # Preview what would be deleted
    python main.py delete-emails 42                  # Delete old emails (requires confirmation)
    python main.py delete-emails 42 --waiting-days 14 # Custom waiting period
    """)


if __name__ == '__main__':
    main()
