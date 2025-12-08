"""
Scan and analysis commands for Email Subscription Manager.

Handles email scanning, combined scanning, and subscription detection.
"""

import click
from src.cli_session import get_cli_session_manager
from src.database.models import Account
from src.email_processor.scanner import EmailScanner
from src.email_processor.combined_scanner import CombinedEmailScanner
from ..utils import get_password_for_account


@click.command('scan')
@click.option('--email', required=True, help='Email address to scan')
@click.option('--limit', type=int, help='Maximum number of messages to scan')
def scan(email, limit):
    """
    Scan email account for new messages.
    
    Downloads message headers and basic information without analysis.
    
    Example:
        python main.py scan --email user@gmail.com
        python main.py scan --email user@gmail.com --limit 100
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # Find account
        account = session.query(Account).filter_by(email_address=email).first()
        if not account:
            click.secho(f"✗ Error: Account {email} not found", fg='red')
            click.echo("Add account with: python main.py account add EMAIL")
            raise click.Abort()
        
        # Get password
        try:
            password = get_password_for_account(email)
        except Exception as e:
            click.secho(f"✗ Error getting password: {e}", fg='red')
            raise click.Abort()
        
        # Scan account
        click.echo(f"\nScanning {email}...")
        scanner = EmailScanner(session)
        
        try:
            if limit:
                count = scanner.scan_account(account.id, password, max_messages=limit)
            else:
                count = scanner.scan_account(account.id, password)
            
            click.secho(f"✓ Scan complete: {count} messages processed", fg='green')
            
        except Exception as e:
            click.secho(f"✗ Scan failed: {e}", fg='red')
            raise click.Abort()


@click.command('scan-analyze')
@click.option('--email', required=True, help='Email address to scan and analyze')
@click.option('--limit', type=int, help='Maximum number of messages to scan')
def scan_analyze(email, limit):
    """
    Scan and analyze email account in one step.
    
    Downloads messages and performs subscription detection analysis.
    
    Example:
        python main.py scan-analyze --email user@gmail.com
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # Find account
        account = session.query(Account).filter_by(email_address=email).first()
        if not account:
            click.secho(f"✗ Error: Account {email} not found", fg='red')
            raise click.Abort()
        
        # Get password
        try:
            password = get_password_for_account(email)
        except Exception as e:
            click.secho(f"✗ Error getting password: {e}", fg='red')
            raise click.Abort()
        
        # Scan and analyze
        click.echo(f"\nScanning and analyzing {email}...")
        scanner = CombinedEmailScanner(session)
        
        try:
            if limit:
                scanned, analyzed = scanner.scan_account_with_analysis(
                    account.id, password, max_messages=limit
                )
            else:
                scanned, analyzed = scanner.scan_account_with_analysis(account.id, password)
            
            click.secho(f"✓ Scan complete", fg='green')
            click.echo(f"  Messages scanned: {scanned}")
            click.echo(f"  Messages analyzed: {analyzed}")
            
        except Exception as e:
            click.secho(f"✗ Scan failed: {e}", fg='red')
            raise click.Abort()
