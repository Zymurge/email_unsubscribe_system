"""
Account management commands for Email Subscription Manager.

Handles adding, listing, and viewing account information.
"""

import click
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from src.cli_session import get_cli_session_manager
from src.database.models import Account, EmailMessage, Subscription


# Provider presets for common email providers
PROVIDER_SETTINGS = {
    'gmail': {
        'imap_server': 'imap.gmail.com',
        'imap_port': 993
    },
    'outlook': {
        'imap_server': 'outlook.office365.com',
        'imap_port': 993
    },
    'yahoo': {
        'imap_server': 'imap.mail.yahoo.com',
        'imap_port': 993
    },
    'icloud': {
        'imap_server': 'imap.mail.me.com',
        'imap_port': 993
    },
    'comcast': {
        'imap_server': 'imap.comcast.net',
        'imap_port': 993
    }
}


def detect_provider(email: str) -> str:
    """Detect provider from email domain."""
    domain = email.split('@')[-1].lower()
    
    if 'gmail.com' in domain:
        return 'gmail'
    elif 'outlook.com' in domain or 'hotmail.com' in domain or 'live.com' in domain:
        return 'outlook'
    elif 'yahoo.com' in domain:
        return 'yahoo'
    elif 'icloud.com' in domain or 'me.com' in domain or 'mac.com' in domain:
        return 'icloud'
    elif 'comcast.net' in domain:
        return 'comcast'
    
    return 'custom'


@click.group()
def account():
    """Account management commands."""
    pass


@account.command('add')
@click.argument('email')
@click.option('--provider', help='Email provider (gmail, outlook, yahoo, icloud, custom)')
@click.option('--imap-server', help='IMAP server address')
@click.option('--imap-port', type=int, default=993, help='IMAP port (default: 993)')
def add_account(email, provider, imap_server, imap_port):
    """
    Add a new email account to monitor.
    
    Args:
        email: Email address to add
    
    Example:
        python main.py account add user@gmail.com
        python main.py account add user@example.com --imap-server mail.example.com
    """
    # Validate email format
    if '@' not in email or '.' not in email:
        click.secho(f"✗ Error: Invalid email address format", fg='red')
        raise click.Abort()
    
    # Auto-detect provider if not specified
    if not provider:
        provider = detect_provider(email)
        if provider != 'custom':
            click.echo(f"Auto-detected provider: {provider}")
    
    # Use provider presets if available
    if provider in PROVIDER_SETTINGS and not imap_server:
        settings = PROVIDER_SETTINGS[provider]
        imap_server = settings['imap_server']
        imap_port = settings.get('imap_port', 993)
    
    # Validate that we have IMAP settings
    if not imap_server:
        click.secho("✗ Error: IMAP server required for custom providers", fg='red')
        click.echo("Use --imap-server to specify the IMAP server address")
        raise click.Abort()
    
    # Create account
    session_manager = get_cli_session_manager()
    try:
        with session_manager.get_session() as session:
            new_account = Account(
                email_address=email,
                provider=provider,
                imap_server=imap_server,
                imap_port=imap_port
            )
            session.add(new_account)
            session.commit()
            
            click.secho(f"✓ Account added successfully", fg='green')
            click.echo(f"  Email: {email}")
            click.echo(f"  Provider: {provider}")
            click.echo(f"  IMAP: {imap_server}:{imap_port}")
            
    except IntegrityError:
        click.secho(f"✗ Error: Account {email} already exists", fg='red')
        raise click.Abort()
    except Exception as e:
        click.secho(f"✗ Error adding account: {e}", fg='red')
        raise click.Abort()


@account.command('list')
def list_accounts():
    """
    List all configured email accounts.
    
    Example:
        python main.py account list
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        accounts = session.query(Account).all()
        
        if not accounts:
            click.echo("No accounts configured.")
            click.echo("\nAdd an account with: python main.py account add EMAIL")
            return
        
        click.echo(f"\nConfigured accounts: {len(accounts)}")
        click.echo("=" * 70)
        
        for acc in accounts:
            click.echo(f"\n{acc.email_address}")
            click.echo(f"  Provider: {acc.provider}")
            click.echo(f"  IMAP: {acc.imap_server}:{acc.imap_port}")
            if acc.last_scan:
                click.echo(f"  Last scan: {acc.last_scan}")
            else:
                click.echo(f"  Last scan: Never")
        
        click.echo("\n" + "=" * 70)


@click.command('stats')
@click.option('--email', help='Email address to show stats for')
def stats(email):
    """
    Show statistics for email accounts.
    
    Example:
        python main.py stats --email user@gmail.com
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # If email specified, show stats for that account
        if email:
            account = session.query(Account).filter_by(email_address=email).first()
            
            if not account:
                click.secho(f"✗ Error: Account {email} not found", fg='red')
                raise click.Abort()
            
            # Get counts
            message_count = session.query(EmailMessage).filter_by(account_id=account.id).count()
            subscription_count = session.query(Subscription).filter_by(account_id=account.id).count()
            kept_count = session.query(Subscription).filter_by(
                account_id=account.id,
                keep_subscription=True
            ).count()
            unsubscribed_count = session.query(Subscription).filter(
                Subscription.account_id == account.id,
                Subscription.unsubscribed_at.isnot(None)
            ).count()
            
            click.echo(f"\nStatistics for {email}")
            click.echo("=" * 70)
            click.echo(f"  Total messages: {message_count}")
            click.echo(f"  Subscriptions detected: {subscription_count}")
            click.echo(f"  Subscriptions kept: {kept_count}")
            click.echo(f"  Unsubscribed: {unsubscribed_count}")
            if account.last_scan:
                click.echo(f"  Last scan: {account.last_scan}")
            else:
                click.echo(f"  Last scan: Never")
            click.echo("=" * 70)
        
        else:
            # Show stats for all accounts
            accounts = session.query(Account).all()
            
            if not accounts:
                click.echo("No accounts configured.")
                return
            
            click.echo("\nAccount Statistics")
            click.echo("=" * 70)
            
            for account in accounts:
                message_count = session.query(EmailMessage).filter_by(account_id=account.id).count()
                subscription_count = session.query(Subscription).filter_by(account_id=account.id).count()
                
                click.echo(f"\n{account.email_address}")
                click.echo(f"  Messages: {message_count}")
                click.echo(f"  Subscriptions: {subscription_count}")
            
            click.echo("\n" + "=" * 70)
