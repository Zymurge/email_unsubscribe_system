"""
Subscription management commands for Email Subscription Manager.

Handles subscription detection, listing, and violation reporting.
"""

import click
from src.cli_session import get_cli_session_manager
from src.database.models import Account, Subscription
from src.email_processor.subscription_detector import SubscriptionDetector
from src.database.violations import ViolationReporter


@click.command('detect-subscriptions')
@click.option('--email', required=True, help='Email address to detect subscriptions for')
def detect_subscriptions(email):
    """
    Detect subscriptions from scanned emails.
    
    Analyzes email messages and groups them into subscriptions.
    
    Example:
        python main.py detect-subscriptions --email user@gmail.com
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # Find account
        account = session.query(Account).filter_by(email_address=email).first()
        if not account:
            click.secho(f"✗ Error: Account {email} not found", fg='red')
            raise click.Abort()
        
        # Detect subscriptions
        click.echo(f"\nDetecting subscriptions for {email}...")
        detector = SubscriptionDetector(session)
        
        try:
            count = detector.detect_subscriptions(account.id)
            click.secho(f"✓ Detection complete: {count} subscriptions found", fg='green')
            
        except Exception as e:
            click.secho(f"✗ Detection failed: {e}", fg='red')
            raise click.Abort()


@click.command('list-subscriptions')
@click.option('--email', required=True, help='Email address to list subscriptions for')
@click.option('--filter', 'filter_type', type=click.Choice(['all', 'keep', 'ready', 'unsubscribed']),
              default='all', help='Filter subscriptions by status')
def list_subscriptions(email, filter_type):
    """
    List subscriptions for an account.
    
    Options:
        all: Show all subscriptions
        keep: Show only kept subscriptions
        ready: Show subscriptions ready to unsubscribe
        unsubscribed: Show already unsubscribed
    
    Example:
        python main.py list-subscriptions --email user@gmail.com
        python main.py list-subscriptions --email user@gmail.com --filter keep
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # Find account
        account = session.query(Account).filter_by(email_address=email).first()
        if not account:
            click.secho(f"✗ Error: Account {email} not found", fg='red')
            raise click.Abort()
        
        # Build query based on filter
        query = session.query(Subscription).filter_by(account_id=account.id)
        
        if filter_type == 'keep':
            query = query.filter_by(keep_subscription=True)
        elif filter_type == 'ready':
            query = query.filter_by(keep_subscription=False, unsubscribed_at=None)
        elif filter_type == 'unsubscribed':
            query = query.filter(Subscription.unsubscribed_at.isnot(None))
        
        subscriptions = query.all()
        
        if not subscriptions:
            click.echo(f"\nNo subscriptions found ({filter_type})")
            return
        
        # Display subscriptions
        click.echo(f"\nSubscriptions for {email} ({filter_type}): {len(subscriptions)}")
        click.echo("=" * 80)
        
        for sub in subscriptions:
            status_markers = []
            if sub.keep_subscription:
                status_markers.append("KEEP")
            if sub.unsubscribed_at:
                status_markers.append("UNSUBSCRIBED")
            
            status = f" [{', '.join(status_markers)}]" if status_markers else ""
            
            click.echo(f"\n  ID: {sub.id}{status}")
            click.echo(f"  From: {sub.sender_email}")
            click.echo(f"  Emails: {sub.email_count}")
            if sub.unsubscribe_method:
                click.echo(f"  Method: {sub.unsubscribe_method}")
        
        click.echo("\n" + "=" * 80)


@click.command('violations')
@click.option('--email', required=True, help='Email address to check violations for')
def violations(email):
    """
    Show violation reports for subscriptions.
    
    Displays subscriptions that continue sending emails after unsubscribe.
    
    Example:
        python main.py violations --email user@gmail.com
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # Find account
        account = session.query(Account).filter_by(email_address=email).first()
        if not account:
            click.secho(f"✗ Error: Account {email} not found", fg='red')
            raise click.Abort()
        
        # Generate violation report
        reporter = ViolationReporter(session)
        report = reporter.generate_report(account.id)
        
        click.echo(f"\n{report}")
