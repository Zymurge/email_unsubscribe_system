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
from src.config.credentials import get_credential_store
from src.database import init_database
from src.email_processor.scanner import EmailScanner
from src.email_processor.combined_scanner import CombinedEmailScanner
from src.email_processor.subscription_detector import SubscriptionDetector
from src.email_processor.email_deleter import EmailDeleter
from src.database.violations import ViolationReporter
from src.cli_session import get_cli_session_manager, with_db_session


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
    elif command == 'list-subscriptions':
        list_subscriptions_command()
    elif command == 'unsubscribe':
        unsubscribe_command()
    elif command == 'store-password':
        store_password_command()
    elif command == 'remove-password':
        remove_password_command()
    elif command == 'list-passwords':
        list_passwords_command()
    elif command == 'keep':
        keep_command()
    elif command == 'unkeep':
        unkeep_command()
    elif command == 'delete-emails':
        delete_emails_command()
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
    password = get_password_for_account(email_address)
    
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
            
        password = get_password_for_account(account['email_address'])
        
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
            
        password = get_password_for_account(account['email_address'])
        
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


@with_db_session
def list_subscriptions_command(session):
    """List subscriptions for an account with filtering."""
    if len(sys.argv) < 3:
        print("Usage: python main.py list-subscriptions <account_id> [--keep=yes|no|all]")
        return
    
    try:
        account_id = int(sys.argv[2])
        
        # Parse --keep filter
        keep_filter = None  # None means show all
        for arg in sys.argv[3:]:
            if arg.startswith('--keep='):
                keep_value = arg.split('=')[1].lower()
                if keep_value == 'yes':
                    keep_filter = True
                elif keep_value == 'no':
                    keep_filter = False
                elif keep_value == 'all':
                    keep_filter = None
                else:
                    print(f"Invalid --keep value: {keep_value}. Use yes, no, or all")
                    return
        
        # Get account info
        from src.database.models import Account, Subscription
        account = session.query(Account).filter_by(id=account_id).first()
        if not account:
            print(f"Account {account_id} not found")
            return
        
        # Build query
        query = session.query(Subscription).filter_by(account_id=account_id)
        
        # Apply keep filter if specified
        if keep_filter is not None:
            query = query.filter_by(keep_subscription=keep_filter)
        
        # Order by email count (most emails first)
        subscriptions = query.order_by(Subscription.email_count.desc()).all()
        
        if not subscriptions:
            filter_msg = ""
            if keep_filter is True:
                filter_msg = " (filtered: keep=yes)"
            elif keep_filter is False:
                filter_msg = " (filtered: keep=no)"
            print(f"\nNo subscriptions found for {account.email_address}{filter_msg}")
            return
        
        # Display header
        print(f"\n{'='*90}")
        print(f"Subscriptions for {account.email_address}")
        filter_msg = ""
        if keep_filter is True:
            filter_msg = " (showing only kept subscriptions)"
        elif keep_filter is False:
            filter_msg = " (showing only non-kept subscriptions)"
        if filter_msg:
            print(filter_msg)
        print(f"{'='*90}")
        
        # Column headers
        print(f"\n{'ID':<5} {'Sender':<35} {'Emails':>7} {'Keep':>6} {'Unsub':>7} {'Violations':>11} {'Method':<12}")
        print("-" * 90)
        
        # Count stats
        kept_count = 0
        unsubscribed_count = 0
        ready_count = 0
        
        # Display each subscription
        for sub in subscriptions:
            # Keep indicator
            keep_indicator = "[✓]" if sub.keep_subscription else "[ ]"
            
            # Unsubscribed status
            unsub_status = "Yes" if sub.unsubscribed_at else "No"
            
            # Violation count (only show if unsubscribed)
            violations_display = str(sub.violation_count) if sub.unsubscribed_at else "-"
            
            # Method display
            method = sub.unsubscribe_method or "none"
            
            # Truncate sender if too long
            sender_display = sub.sender_email[:34] if len(sub.sender_email) > 34 else sub.sender_email
            
            print(f"{sub.id:<5} {sender_display:<35} {sub.email_count:>7} {keep_indicator:>6} "
                  f"{unsub_status:>7} {violations_display:>11} {method:<12}")
            
            # Update stats
            if sub.keep_subscription:
                kept_count += 1
            if sub.unsubscribed_at:
                unsubscribed_count += 1
            if not sub.keep_subscription and not sub.unsubscribed_at:
                ready_count += 1
        
        # Summary
        print("-" * 90)
        print(f"Total: {len(subscriptions)} subscription(s)")
        if keep_filter is None:  # Only show breakdown if showing all
            print(f"  Kept: {kept_count} | Already Unsubscribed: {unsubscribed_count} | Ready to Unsubscribe: {ready_count}")
        print()
        
    except ValueError:
        print("Account ID must be a number")
    except Exception as e:
        print(f"Error listing subscriptions: {e}")
        import traceback
        traceback.print_exc()


@with_db_session
def unsubscribe_command(session):
    """Execute unsubscribe for a subscription."""
    if len(sys.argv) < 3:
        print("Usage: python main.py unsubscribe <subscription_id> [--dry-run] [--yes]")
        return
    
    try:
        subscription_id = int(sys.argv[2])
        
        # Parse flags
        dry_run = '--dry-run' in sys.argv
        skip_confirm = '--yes' in sys.argv
        
        # Get subscription
        from src.database.models import Subscription, UnsubscribeAttempt, Account
        subscription = session.query(Subscription).filter_by(id=subscription_id).first()
        
        if not subscription:
            print(f"Subscription {subscription_id} not found")
            return
        
        # Display subscription info
        print(f"\n{'='*80}")
        print(f"Unsubscribe Request")
        print(f"{'='*80}")
        print(f"Subscription ID: {subscription.id}")
        print(f"Sender:          {subscription.sender_email}")
        print(f"Email Count:     {subscription.email_count}")
        print(f"Keep Status:     {'YES (protected)' if subscription.keep_subscription else 'No'}")
        print(f"Already Unsub:   {'Yes' if subscription.unsubscribed_at else 'No'}")
        print(f"Unsub Link:      {subscription.unsubscribe_link or 'Not available'}")
        print(f"Unsub Method:    {subscription.unsubscribe_method or 'Unknown'}")
        
        # Check for previous attempts
        attempts = session.query(UnsubscribeAttempt).filter_by(
            subscription_id=subscription_id
        ).order_by(UnsubscribeAttempt.attempted_at.desc()).all()
        
        if attempts:
            print(f"\nPrevious Attempts: {len(attempts)}")
            for i, attempt in enumerate(attempts[:3], 1):  # Show last 3
                print(f"  {i}. {attempt.attempted_at.strftime('%Y-%m-%d %H:%M')} - "
                      f"{attempt.status} - {attempt.method_used}")
                if attempt.error_message:
                    print(f"     Error: {attempt.error_message[:60]}")
        
        print(f"{'='*80}")
        
        if dry_run:
            print("\n[DRY RUN MODE] - No actual unsubscribe will be performed")
        
        # Import appropriate executor based on method
        if subscription.unsubscribe_method == 'http_get':
            from src.unsubscribe_executor.http_executor import HttpGetExecutor
            executor = HttpGetExecutor(session, dry_run=dry_run)
            method_display = "HTTP GET"
            # HTTP executors use subscription_id
            should_execute_result = executor.should_execute(subscription_id)
            execute_param = subscription_id
        elif subscription.unsubscribe_method == 'http_post':
            from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
            executor = HttpPostExecutor(session, dry_run=dry_run)
            method_display = "HTTP POST"
            # HTTP executors use subscription_id
            should_execute_result = executor.should_execute(subscription_id)
            execute_param = subscription_id
        elif subscription.unsubscribe_method == 'email_reply':
            from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
            from src.config.credentials import CredentialStore
            
            # Get email credentials
            credential_store = CredentialStore()
            account = session.query(Account).filter_by(id=subscription.account_id).first()
            if not account:
                print(f"\n❌ Account not found for subscription")
                return
            
            email_password = credential_store.get_password(account.email_address)
            if not email_password:
                print(f"\n❌ No stored credentials for {account.email_address}")
                print(f"   Run: python main.py store-password {account.email_address}")
                return
            
            executor = EmailReplyExecutor(
                session=session,
                email_address=account.email_address,
                email_password=email_password,
                dry_run=dry_run
            )
            method_display = "Email Reply"
            # Email executor uses subscription object
            should_execute_result = executor.should_execute(subscription)
            execute_param = subscription
        else:
            print(f"\n❌ Unsupported unsubscribe method: {subscription.unsubscribe_method}")
            print(f"   Currently supported: http_get, http_post, email_reply")
            return
        
        # Check if should execute
        if not should_execute_result['should_execute']:
            print(f"\n❌ Cannot execute unsubscribe:")
            print(f"   {should_execute_result['reason']}")
            return
        
        # Confirmation prompt (unless --yes flag or dry-run)
        if not skip_confirm and not dry_run:
            print(f"\n⚠️  Are you sure you want to unsubscribe from '{subscription.sender_email}'?")
            print(f"   Method: {method_display}")
            confirmation = input("Type 'yes' to confirm: ")
            if confirmation.lower() != 'yes':
                print("Unsubscribe cancelled")
                return
        
        # Execute unsubscribe
        print(f"\n{'Simulating' if dry_run else 'Executing'} unsubscribe via {method_display}...")
        result = executor.execute(execute_param)
        
        # Display results
        print(f"\n{'='*80}")
        if result['success']:
            print(f"✅ Unsubscribe {'simulation' if dry_run else 'request'} successful!")
            if result.get('status_code'):
                print(f"   HTTP Status: {result['status_code']}")
            if dry_run:
                print(f"   Would have sent GET request to: {subscription.unsubscribe_link}")
            else:
                print(f"   Subscription marked as unsubscribed")
                print(f"   Attempt recorded in database")
        else:
            print(f"❌ Unsubscribe {'simulation' if dry_run else 'request'} failed")
            if result.get('error_message'):
                print(f"   Error: {result['error_message']}")
            if result.get('status_code'):
                print(f"   HTTP Status: {result['status_code']}")
        print(f"{'='*80}\n")
        
    except ValueError:
        print("Subscription ID must be a number")
    except Exception as e:
        print(f"Error executing unsubscribe: {e}")
        import traceback
        traceback.print_exc()


def store_password_command():
    """Store password for an email account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py store-password <email>")
        return
    
    email_address = sys.argv[2]
    password = getpass.getpass(f"Password for {email_address}: ")
    confirm_password = getpass.getpass(f"Confirm password: ")
    
    if password != confirm_password:
        print("Passwords do not match")
        return
    
    try:
        cred_store = get_credential_store()
        cred_store.set_password(email_address, password)
        print(f"Password stored for {email_address}")
        print(f"Credentials are saved in: {cred_store.store_path}")
    except Exception as e:
        print(f"Error storing password: {e}")


def remove_password_command():
    """Remove stored password for an email account."""
    if len(sys.argv) < 3:
        print("Usage: python main.py remove-password <email>")
        return
    
    email_address = sys.argv[2]
    
    try:
        cred_store = get_credential_store()
        if cred_store.remove_password(email_address):
            print(f"Password removed for {email_address}")
        else:
            print(f"No stored password found for {email_address}")
    except Exception as e:
        print(f"Error removing password: {e}")


def list_passwords_command():
    """List email accounts with stored passwords."""
    try:
        cred_store = get_credential_store()
        stored_emails = cred_store.list_stored_emails()
        
        if not stored_emails:
            print("No stored passwords found")
            print(f"Use 'store-password' command to save credentials")
            return
        
        print(f"\nEmail accounts with stored passwords:")
        print(f"Credentials stored in: {cred_store.store_path}")
        print("-" * 50)
        for email in stored_emails:
            print(f"  {email}")
        print("-" * 50)
        print(f"Total: {len(stored_emails)} account(s)")
    except Exception as e:
        print(f"Error listing passwords: {e}")


@with_db_session
def keep_command(session):
    """
    Mark subscriptions to keep (skip unsubscribe).
    
    Usage:
        python main.py keep 1 2 3              # Mark IDs 1, 2, 3
        python main.py keep 1,2,3              # Comma-separated
        python main.py keep 1-10               # Range
        python main.py keep --pattern %sutter% # Pattern matching
        python main.py keep --domain example.com # Domain matching
        python main.py keep 1 2 3 --yes        # Skip confirmation
    """
    from src.database.subscription_matcher import SubscriptionMatcher
    from src.database.models import Subscription
    
    # Parse arguments
    args = sys.argv[2:]
    
    # Extract flags
    pattern = None
    domain = None
    yes_flag = False
    ids_input = []
    
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
            
        if arg == '--pattern':
            if i + 1 < len(args):
                pattern = args[i + 1]
                skip_next = True
        elif arg == '--domain':
            if i + 1 < len(args):
                domain = args[i + 1]
                skip_next = True
        elif arg == '--yes':
            yes_flag = True
        elif not arg.startswith('--'):
            ids_input.append(arg)
    
    try:
        # Parse input to determine matching mode
        match_type, value = parse_keep_input(ids_input, pattern, domain)
        
        # Use matcher to get subscription IDs
        matcher = SubscriptionMatcher(session)
        
        if match_type == 'ids':
            subscription_ids = matcher.match_by_ids(value)
        elif match_type == 'range':
            subscription_ids = matcher.match_by_range(value[0], value[1])
        elif match_type == 'pattern':
            subscription_ids = matcher.match_by_pattern(value)
        elif match_type == 'domain':
            subscription_ids = matcher.match_by_domain(value)
        else:
            print(f"Error: Unknown match type: {match_type}")
            return
        
        if not subscription_ids:
            print("No subscriptions matched the criteria")
            return
        
        # Fetch subscriptions for display
        subscriptions = session.query(Subscription).filter(
            Subscription.id.in_(subscription_ids)
        ).all()
        
        print(f"\nFound {len(subscriptions)} subscription(s) to mark as keep:")
        print("-" * 80)
        for sub in subscriptions:
            status = "ALREADY KEPT" if sub.keep_subscription else "will mark"
            print(f"  ID {sub.id}: {sub.sender_email} ({sub.email_count} emails) [{status}]")
        print("-" * 80)
        
        # Confirmation
        if not yes_flag:
            response = input("\nContinue and mark these subscriptions? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Cancelled")
                return
        
        # Mark subscriptions
        result = mark_subscriptions_keep(session, subscription_ids)
        
        print(f"\n✓ Marked {result['marked']} subscription(s) to keep")
        if result['already_kept'] > 0:
            print(f"  ({result['already_kept']} already marked)")
        
    except ValueError as e:
        print(f"Error: {e}")
        print("\nUsage:")
        print("  python main.py keep 1 2 3              # Mark specific IDs")
        print("  python main.py keep 1-10               # Mark range")
        print("  python main.py keep --pattern %sutter% # Pattern matching")
        print("  python main.py keep --domain example.com # Domain matching")
    except Exception as e:
        print(f"Error: {e}")


@with_db_session
def unkeep_command(session):
    """
    Unmark subscriptions (make eligible for unsubscribe).
    
    Usage:
        python main.py unkeep 1 2 3              # Unmark IDs 1, 2, 3
        python main.py unkeep 1,2,3              # Comma-separated
        python main.py unkeep 1-10               # Range
        python main.py unkeep --pattern %sutter% # Pattern matching
        python main.py unkeep --domain example.com # Domain matching
        python main.py unkeep 1 2 3 --yes        # Skip confirmation
    """
    from src.database.subscription_matcher import SubscriptionMatcher
    from src.database.models import Subscription
    
    # Parse arguments
    args = sys.argv[2:]
    
    # Extract flags
    pattern = None
    domain = None
    yes_flag = False
    ids_input = []
    
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
            
        if arg == '--pattern':
            if i + 1 < len(args):
                pattern = args[i + 1]
                skip_next = True
        elif arg == '--domain':
            if i + 1 < len(args):
                domain = args[i + 1]
                skip_next = True
        elif arg == '--yes':
            yes_flag = True
        elif not arg.startswith('--'):
            ids_input.append(arg)
    
    try:
        # Parse input to determine matching mode
        match_type, value = parse_keep_input(ids_input, pattern, domain)
        
        # Use matcher to get subscription IDs
        matcher = SubscriptionMatcher(session)
        
        if match_type == 'ids':
            subscription_ids = matcher.match_by_ids(value)
        elif match_type == 'range':
            subscription_ids = matcher.match_by_range(value[0], value[1])
        elif match_type == 'pattern':
            subscription_ids = matcher.match_by_pattern(value)
        elif match_type == 'domain':
            subscription_ids = matcher.match_by_domain(value)
        else:
            print(f"Error: Unknown match type: {match_type}")
            return
        
        if not subscription_ids:
            print("No subscriptions matched the criteria")
            return
        
        # Fetch subscriptions for display
        subscriptions = session.query(Subscription).filter(
            Subscription.id.in_(subscription_ids)
        ).all()
        
        print(f"\nFound {len(subscriptions)} subscription(s) to unmark (make eligible for unsubscribe):")
        print("-" * 80)
        for sub in subscriptions:
            status = "will unmark" if sub.keep_subscription else "already not kept"
            print(f"  ID {sub.id}: {sub.sender_email} ({sub.email_count} emails) [{status}]")
        print("-" * 80)
        
        # Confirmation
        if not yes_flag:
            response = input("\nContinue and unmark these subscriptions? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Cancelled")
                return
        
        # Unmark subscriptions
        result = mark_subscriptions_unkeep(session, subscription_ids)
        
        print(f"\n✓ Unmarked {result['unmarked']} subscription(s)")
        if result['already_not_kept'] > 0:
            print(f"  ({result['already_not_kept']} already not kept)")
        
    except ValueError as e:
        print(f"Error: {e}")
        print("\nUsage:")
        print("  python main.py unkeep 1 2 3              # Unmark specific IDs")
        print("  python main.py unkeep 1-10               # Unmark range")
        print("  python main.py unkeep --pattern %sutter% # Pattern matching")
        print("  python main.py unkeep --domain example.com # Domain matching")
    except Exception as e:
        print(f"Error: {e}")


def parse_keep_input(ids_input, pattern, domain):
    """
    Parse keep/unkeep command input to determine matching mode.
    
    Args:
        ids_input: List of ID strings (e.g., ['1', '2', '3'] or ['1-10'] or ['1,2,3'])
        pattern: SQL LIKE pattern (from --pattern flag)
        domain: Domain name (from --domain flag)
        
    Returns:
        Tuple of (match_type, value) where:
            match_type is 'ids', 'range', 'pattern', or 'domain'
            value is the parsed value for that type
            
    Raises:
        ValueError: If input is invalid or conflicting
    """
    # Count how many input types provided
    has_ids = bool(ids_input)
    has_pattern = pattern is not None
    has_domain = domain is not None
    
    input_count = sum([has_ids, has_pattern, has_domain])
    
    if input_count == 0:
        raise ValueError("No input provided. Specify IDs, range, --pattern, or --domain")
    
    if input_count > 1:
        raise ValueError("Cannot mix IDs/ranges with --pattern or --domain flags")
    
    # Pattern flag
    if has_pattern:
        return ('pattern', pattern)
    
    # Domain flag
    if has_domain:
        return ('domain', domain)
    
    # IDs or range
    if has_ids:
        # Single arg - could be comma-separated or range
        if len(ids_input) == 1:
            arg = ids_input[0]
            
            # Check for range format (1-10)
            if '-' in arg and not arg.startswith('-'):
                parts = arg.split('-')
                if len(parts) == 2:
                    try:
                        start = int(parts[0])
                        end = int(parts[1])
                        return ('range', (start, end))
                    except ValueError:
                        pass  # Fall through to ID parsing
                else:
                    raise ValueError(f"Invalid range format: {arg}")
            
            # Check for comma-separated IDs
            if ',' in arg:
                try:
                    id_list = [int(x.strip()) for x in arg.split(',')]
                    return ('ids', id_list)
                except ValueError:
                    raise ValueError(f"Invalid ID list: {arg}")
        
        # Space-separated or single ID
        try:
            id_list = [int(x) for x in ids_input]
            return ('ids', id_list)
        except ValueError:
            raise ValueError(f"Invalid ID values: {ids_input}")
    
    raise ValueError("Unable to parse input")


def mark_subscriptions_keep(session, subscription_ids):
    """
    Mark subscriptions as keep (keep_subscription=True).
    
    Args:
        session: Database session
        subscription_ids: List of subscription IDs to mark
        
    Returns:
        Dict with 'marked' and 'already_kept' counts
    """
    from src.database.models import Subscription
    
    if not subscription_ids:
        return {'marked': 0, 'already_kept': 0}
    
    # Fetch subscriptions
    subscriptions = session.query(Subscription).filter(
        Subscription.id.in_(subscription_ids)
    ).all()
    
    marked = 0
    already_kept = 0
    
    for sub in subscriptions:
        if sub.keep_subscription:
            already_kept += 1
        else:
            sub.keep_subscription = True
            marked += 1
    
    session.commit()
    
    return {'marked': marked, 'already_kept': already_kept}


def mark_subscriptions_unkeep(session, subscription_ids):
    """
    Unmark subscriptions (keep_subscription=False).
    
    Args:
        session: Database session
        subscription_ids: List of subscription IDs to unmark
        
    Returns:
        Dict with 'unmarked' and 'already_not_kept' counts
    """
    from src.database.models import Subscription
    
    if not subscription_ids:
        return {'unmarked': 0, 'already_not_kept': 0}
    
    # Fetch subscriptions
    subscriptions = session.query(Subscription).filter(
        Subscription.id.in_(subscription_ids)
    ).all()
    
    unmarked = 0
    already_not_kept = 0
    
    for sub in subscriptions:
        if not sub.keep_subscription:
            already_not_kept += 1
        else:
            sub.keep_subscription = False
            unmarked += 1
    
    session.commit()
    
    return {'unmarked': unmarked, 'already_not_kept': already_not_kept}


@with_db_session
def delete_emails_command(session):
    """
    Delete emails from a successfully unsubscribed subscription.
    
    Safety features:
    - Only deletes from unsubscribed subscriptions
    - Requires waiting period (default 7 days)
    - Preserves post-unsubscribe emails (violation evidence)
    - Never deletes if marked "keep" or has violations
    - Strong confirmation required (no --yes bypass)
    - Dry-run mode for safe preview
    """
    from src.database.models import Subscription
    
    if len(sys.argv) < 3:
        print("Usage: python main.py delete-emails <subscription_id> [--dry-run] [--waiting-days N]")
        return
    
    try:
        subscription_id = int(sys.argv[2])
    except ValueError:
        print("Error: subscription_id must be an integer")
        return
    
    # Parse options
    dry_run = '--dry-run' in sys.argv
    waiting_days = 7  # Default
    
    for i, arg in enumerate(sys.argv):
        if arg == '--waiting-days' and i + 1 < len(sys.argv):
            try:
                waiting_days = int(sys.argv[i + 1])
                if waiting_days < 0:
                    print("Error: waiting-days must be non-negative")
                    return
            except ValueError:
                print("Error: waiting-days must be an integer")
                return
    
    # --yes flag is NOT allowed for delete operations (safety requirement)
    if '--yes' in sys.argv:
        print("Error: --yes flag not allowed for delete-emails (safety requirement)")
        print("You must manually confirm deletion operations.")
        return
    
    # Get subscription
    subscription = session.query(Subscription).filter_by(id=subscription_id).first()
    
    if not subscription:
        print(f"Error: Subscription {subscription_id} not found")
        return
    
    # Create deleter
    deleter = EmailDeleter(session, waiting_days=waiting_days)
    
    # Check eligibility
    eligible, reason = deleter.is_eligible_for_deletion(subscription)
    
    print("="*90)
    print(f"Email Deletion {'Preview' if dry_run else 'Operation'}")
    print("="*90)
    print()
    print(f"Subscription ID: {subscription.id}")
    print(f"Sender: {subscription.sender_email}")
    print(f"Total Emails: {subscription.email_count}")
    print(f"Keep Status: {'✓ MARKED TO KEEP' if subscription.keep_subscription else 'not kept'}")
    print(f"Unsubscribe Status: {subscription.unsubscribe_status or 'not unsubscribed'}")
    
    if subscription.unsubscribed_at:
        from datetime import datetime
        days_since = (datetime.now() - subscription.unsubscribed_at).days
        print(f"Unsubscribed: {subscription.unsubscribed_at.strftime('%Y-%m-%d')} ({days_since} days ago)")
    else:
        print("Unsubscribed: never")
    
    print(f"Violations: {subscription.violation_count}")
    print(f"Waiting Period: {waiting_days} days")
    print()
    
    # Display eligibility check
    print("Eligibility Check:")
    print("-" * 90)
    
    if eligible:
        print(f"✓ {reason}")
    else:
        print(f"✗ {reason}")
        print()
        print("Cannot delete emails. Address the issues above.")
        return
    
    print()
    
    # Execute deletion (dry-run or real)
    result = deleter.delete_subscription_emails(subscription, dry_run=dry_run)
    
    # Display results
    print("Deletion Summary:")
    print("-" * 90)
    
    if result.dry_run:
        print("[DRY RUN MODE - No actual changes made]")
        print()
    
    print(f"Emails to DELETE: {result.emails_to_delete}")
    if result.oldest_email_date and result.newest_email_date:
        print(f"  Date range: {result.oldest_email_date.strftime('%Y-%m-%d')} to {result.newest_email_date.strftime('%Y-%m-%d')}")
        print(f"  (All emails received BEFORE unsubscribe date)")
    
    print(f"Emails to PRESERVE: {result.emails_to_preserve}")
    if subscription.unsubscribed_at:
        print(f"  (All emails on or after {subscription.unsubscribed_at.strftime('%Y-%m-%d')})")
    
    print()
    
    if result.emails_to_delete == 0:
        print("No emails to delete.")
        return
    
    # Confirmation required for non-dry-run
    if not dry_run:
        print("⚠️  WARNING: This will PERMANENTLY delete emails from your mailbox!")
        print("⚠️  This operation CANNOT be undone!")
        print()
        print(f"Type the subscription ID ({subscription_id}) to confirm deletion: ", end='')
        
        confirmation = input().strip()
        
        if confirmation != str(subscription_id):
            print()
            print("Deletion cancelled (confirmation did not match).")
            return
        
        print()
        print("Deleting emails...")
        
        # Actually perform deletion
        result = deleter.delete_subscription_emails(subscription, dry_run=False)
        
        print()
        
        if result.success:
            print("✓ Deletion completed successfully")
            print(f"  Deleted: {result.emails_deleted} emails")
            print(f"  Preserved: {result.emails_to_preserve} emails")
            print(f"  Updated subscription email count: {subscription.email_count} → {result.emails_to_preserve}")
        else:
            print("✗ Deletion failed")
            print(f"  Error: {result.message}")
    else:
        print("Dry-run complete. Use without --dry-run to actually delete emails.")
        print(f"Remember: You must type the subscription ID ({subscription_id}) to confirm.")


if __name__ == '__main__':
    main()
