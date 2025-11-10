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
from src.email_processor.scanner import EmailScanner
from src.email_processor.combined_scanner import CombinedEmailScanner
from src.email_processor.subscription_detector import SubscriptionDetector
from src.database.violations import ViolationReporter
from src.cli_session import get_cli_session_manager, with_db_session


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
    elif command == 'scan-analyze':
        combined_scan_command()
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
    scan <account_id>            Scan an account for messages (basic)
    scan-analyze <account_id>    Scan with integrated subscription detection & unsubscribe extraction
    list-accounts                List all accounts
    stats <account_id>           Show account statistics
    detect-subscriptions <id>    Detect subscriptions for account (legacy)
    violations <account_id>      Show violation reports for account

Options:
    --debug-storage              Store detailed extraction info (use with scan-analyze)

Examples:
    python main.py init
    python main.py add-account user@comcast.net
    python main.py scan-analyze 1                    # Combined scan+analyze (recommended)
    python main.py scan-analyze 1 --debug-storage    # With debug info storage
    python main.py scan 1                            # Basic scan only
    python main.py stats 1
    python main.py violations 1
    """)


def init_database_command():
    """Initialize the database."""
    try:
        db_manager = init_database()
        print(f"Database initialized at: {db_manager.database_url}")
    except Exception as e:
        print(f"Error initializing database: {e}")


@with_db_session
def add_account_command(session):
    """Add an email account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py add-account <email>")
        return
        
    email_address = sys.argv[2]
    password = getpass.getpass(f"Password for {email_address}: ")
    
    try:
        scanner = EmailScanner(session)
        account = scanner.add_account(email_address, password)
        if account:
            print(f"Successfully added account: {account.email_address} (ID: {account.id})")
        else:
            print("Failed to add account")
    except Exception as e:
        print(f"Error adding account: {e}")


@with_db_session
def scan_command(session):
    """Scan an account for messages."""
    if len(sys.argv) < 3:
        print("Usage: python main.py scan <account_id> [days_back] [limit]")
        return
        
    try:
        account_id = int(sys.argv[2])
        days_back = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
        
        scanner = EmailScanner(session)
        
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


@with_db_session
def combined_scan_command(session):
    """Scan an account with integrated subscription detection and unsubscribe extraction."""
    if len(sys.argv) < 3:
        print("Usage: python main.py scan-analyze <account_id> [days_back] [limit] [--debug-storage]")
        print("  --debug-storage: Store detailed extraction info for debugging")
        return
        
    try:
        account_id = int(sys.argv[2])
        days_back = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '--debug-storage' else 30
        limit = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != '--debug-storage' else None
        
        # Check for debug storage flag
        enable_debug_storage = '--debug-storage' in sys.argv
        
        scanner = EmailScanner(session)
        
        # Get account info to prompt for password
        accounts = scanner.get_accounts()
        account = next((a for a in accounts if a['id'] == account_id), None)
        if not account:
            print(f"Account {account_id} not found")
            return
            
        password = getpass.getpass(f"Password for {account['email_address']}: ")
        
        # Create combined scanner
        combined_scanner = CombinedEmailScanner(session, enable_debug_storage=enable_debug_storage)
        
        print(f"Starting combined scan+analyze for {account['email_address']} (last {days_back} days)...")
        if enable_debug_storage:
            print("Debug storage enabled - detailed extraction info will be saved")
        
        results = combined_scanner.scan_account_with_analysis(
            account_id, password, days_back=days_back, limit=limit
        )
        
        print(f"\nCombined scan+analyze complete:")
        print(f"  Total found: {results['total_found']}")
        print(f"  Emails processed: {results['processed_emails']}")
        print(f"  Email errors: {results['email_errors']}")
        print(f"  Subscriptions created: {results['subscriptions_created']}")
        print(f"  Subscriptions updated: {results['subscriptions_updated']}")
        print(f"  Unsubscribe methods extracted: {results['unsubscribe_methods_extracted']}")
        
    except ValueError:
        print("Account ID must be a number")
    except Exception as e:
        print(f"Error in combined scan: {e}")


@with_db_session
def list_accounts_command(session):
    """List all accounts."""
    try:
        scanner = EmailScanner(session)
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


@with_db_session
def stats_command(session):
    """Show account statistics."""
    if len(sys.argv) < 3:
        print("Usage: python main.py stats <account_id>")
        return
        
    try:
        account_id = int(sys.argv[2])
        scanner = EmailScanner(session)
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


@with_db_session
def detect_subscriptions_command(session):
    """Detect subscriptions for an account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py detect-subscriptions <account_id>")
        return
        
    try:
        account_id = int(sys.argv[2])
        
        print(f"Detecting subscriptions for account {account_id}...")
        
        detector = SubscriptionDetector()
        result = detector.detect_subscriptions_from_emails(account_id, session)
        
        print(f"\nSubscription Detection Results:")
        print(f"Created: {result['created']} new subscriptions")
        print(f"Updated: {result['updated']} existing subscriptions") 
        print(f"Skipped: {result['skipped']} emails (insufficient data)")
        
        # Show the detected subscriptions
        from src.database.models import Subscription
        subscriptions = session.query(Subscription).filter(
            Subscription.account_id == account_id
        ).all()
        
        if subscriptions:
            print(f"\nTotal Subscriptions for Account {account_id}: {len(subscriptions)}")
            print("-" * 80)
            for sub in subscriptions:
                print(f"From: {sub.sender_email:<40} | Confidence: {sub.confidence_score:3d} | Emails: {sub.email_count}")
                if sub.sender_domain:
                    print(f"      Domain: {sub.sender_domain}")
                # Note: marketing_keywords is not stored in the model currently
                print()
        else:
            print("No subscriptions found in database.")
            
    except ValueError:
        print("Account ID must be a number")
    except Exception as e:
        print(f"Error detecting subscriptions: {e}")


@with_db_session
def violations_command(session):
    """Show violation reports for an account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py violations <account_id>")
        return
        
    try:
        account_id = int(sys.argv[2])
        reporter = ViolationReporter(session)
        
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