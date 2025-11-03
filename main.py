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
from src.email_processor.subscription_detector import SubscriptionDetector
from src.database.violations import ViolationReporter


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
    elif command == 'detect-subscriptions':
        detect_subscriptions_command()
    elif command == 'violations':
        violations_command()
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
    scan <account_id>            Scan an account for messages
    list-accounts                List all accounts
    stats <account_id>           Show account statistics
    detect-subscriptions <id>    Detect subscriptions for account
    violations <account_id>      Show violation reports for account

Examples:
    python main.py init
    python main.py add-account user@comcast.net
    python main.py scan 1
    python main.py stats 1
    python main.py detect-subscriptions 1
    python main.py violations 1
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


def detect_subscriptions_command():
    """Detect subscriptions for an account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py detect-subscriptions <account_id>")
        return
        
    try:
        account_id = int(sys.argv[2])
        detector = SubscriptionDetector()
        
        print(f"Detecting subscriptions for account {account_id}...")
        subscriptions = detector.detect_subscriptions_from_emails(account_id)
        
        if not subscriptions:
            print("No subscriptions detected.")
            return
            
        print(f"\nDetected {len(subscriptions)} subscriptions:")
        print("-" * 80)
        for sub in subscriptions:
            print(f"From: {sub.sender_email:<40} | Confidence: {sub.confidence:3d} | Emails: {sub.email_count}")
            if sub.domain:
                print(f"      Domain: {sub.domain}")
            if sub.marketing_keywords:
                print(f"      Keywords: {', '.join(sub.marketing_keywords)}")
            print()
            
    except ValueError:
        print("Account ID must be a number")
    except Exception as e:
        print(f"Error detecting subscriptions: {e}")


def violations_command():
    """Show violation reports for an account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py violations <account_id>")
        return
        
    try:
        account_id = int(sys.argv[2])
        reporter = ViolationReporter()
        
        # Get violation summary
        summary = reporter.get_violation_summary(account_id)
        if not summary:
            print(f"No violation data found for account {account_id}")
            return
            
        print(f"\nViolation Summary for Account {account_id}")
        print("=" * 50)
        print(f"Total Subscriptions: {summary['total_subscriptions']}")
        print(f"Subscriptions with Violations: {summary['subscriptions_with_violations']}")
        print(f"Total Violation Emails: {summary['total_violation_emails']}")
        
        # Get recent violations
        recent = reporter.get_recent_violations(account_id, limit=5)
        if recent:
            print(f"\nRecent Violations (Last 5):")
            print("-" * 80)
            for violation in recent:
                print(f"{violation['sender_email']:<40} | "
                      f"Violations: {violation['violation_count']:3d} | "
                      f"Last: {violation['last_violation']}")
        
        # Get worst offenders
        worst = reporter.get_worst_offenders(account_id, limit=5)
        if worst:
            print(f"\nWorst Offenders (Top 5):")
            print("-" * 80)
            for offender in worst:
                print(f"{offender['sender_email']:<40} | "
                      f"Violations: {offender['violation_count']:3d} | "
                      f"Last: {offender['last_violation']}")
                
    except ValueError:
        print("Account ID must be a number")
    except Exception as e:
        print(f"Error getting violations: {e}")


if __name__ == '__main__':
    main()