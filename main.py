#!/usr/bin/env python3
"""
Command-line interface for the email subscription manager.
"""

import sys
import os
import getpass
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.config import Config, load_config_from_env_file
from src.database import init_database
from src.email_processor import EmailScanner


def main():
    """Main CLI entry point."""
    load_config_from_env_file()
    
    if len(sys.argv) < 2:
        print_usage()
        return
        
    command = sys.argv[1]
    
    if command == 'init':
        init_database_command()
    elif command == 'add-account':
        add_account_command()
    elif command == 'scan':
        scan_command()
    elif command == 'list-accounts':
        list_accounts_command()
    elif command == 'stats':
        stats_command()
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
    init                    Initialize the database
    add-account <email>     Add an email account
    scan <account_id>       Scan an account for messages
    list-accounts           List all accounts
    stats <account_id>      Show account statistics

Examples:
    python main.py init
    python main.py add-account user@comcast.net
    python main.py scan 1
    python main.py stats 1
    """)


def init_database_command():
    """Initialize the database."""
    try:
        db_manager = init_database()
        print(f"Database initialized at: {db_manager.database_url}")
    except Exception as e:
        print(f"Error initializing database: {e}")


def add_account_command():
    """Add an email account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py add-account <email>")
        return
        
    email_address = sys.argv[2]
    password = getpass.getpass(f"Password for {email_address}: ")
    
    try:
        scanner = EmailScanner()
        account = scanner.add_account(email_address, password)
        if account:
            print(f"Successfully added account: {account.email_address} (ID: {account.id})")
        else:
            print("Failed to add account")
    except Exception as e:
        print(f"Error adding account: {e}")


def scan_command():
    """Scan an account for messages."""
    if len(sys.argv) < 3:
        print("Usage: python main.py scan <account_id> [days_back] [limit]")
        return
        
    try:
        account_id = int(sys.argv[2])
        days_back = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
        
        scanner = EmailScanner()
        
        # Get account info to prompt for password
        accounts = scanner.get_accounts()
        account = next((a for a in accounts if a['id'] == account_id), None)
        if not account:
            print(f"Account {account_id} not found")
            return
            
        password = getpass.getpass(f"Password for {account['email_address']}: ")
        
        print(f"Scanning account {account['email_address']} (last {days_back} days)...")
        results = scanner.scan_account(account_id, password, days_back=days_back, limit=limit)
        
        print(f"Scan complete:")
        print(f"  Total found: {results['total_found']}")
        print(f"  Already existed: {results['already_existed']}")
        print(f"  Newly processed: {results['processed']}")
        print(f"  Errors: {results['errors']}")
        
    except ValueError:
        print("Account ID must be a number")
    except Exception as e:
        print(f"Error scanning account: {e}")


def list_accounts_command():
    """List all accounts."""
    try:
        scanner = EmailScanner()
        accounts = scanner.get_accounts()
        
        if not accounts:
            print("No accounts found. Use 'add-account' to add one.")
            return
            
        print("\nAccounts:")
        print("-" * 80)
        for account in accounts:
            last_scan = account['last_scan'].strftime('%Y-%m-%d %H:%M') if account['last_scan'] else 'Never'
            print(f"ID: {account['id']:<3} Email: {account['email_address']:<30} "
                  f"Provider: {account['provider']:<10} Messages: {account['message_count']:<6} "
                  f"Last Scan: {last_scan}")
        print("-" * 80)
        
    except Exception as e:
        print(f"Error listing accounts: {e}")


def stats_command():
    """Show account statistics."""
    if len(sys.argv) < 3:
        print("Usage: python main.py stats <account_id>")
        return
        
    try:
        account_id = int(sys.argv[2])
        scanner = EmailScanner()
        stats = scanner.get_account_stats(account_id)
        
        if not stats:
            print(f"Account {account_id} not found")
            return
            
        print(f"\nAccount Statistics: {stats['account']['email']}")
        print("-" * 50)
        print(f"Provider: {stats['account']['provider']}")
        print(f"Last Scan: {stats['account']['last_scan'] or 'Never'}")
        print(f"Total Messages: {stats['total_messages']}")
        print(f"Messages with Unsubscribe Info: {stats['messages_with_unsubscribe']}")
        
        if stats['top_senders']:
            print(f"\nTop Senders:")
            for i, sender in enumerate(stats['top_senders'], 1):
                print(f"  {i:2}. {sender['email']:<40} ({sender['count']} messages)")
        
    except ValueError:
        print("Account ID must be a number")
    except Exception as e:
        print(f"Error getting stats: {e}")


if __name__ == '__main__':
    main()