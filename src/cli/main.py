"""
Main CLI group for Email Subscription Manager.

Integrates all command groups into a single CLI application.
"""

import click
from .commands.password import password
from .commands.account import account, stats
from .commands.admin import init
from .commands.scan import scan, scan_analyze
from .commands.subscription import detect_subscriptions, list_subscriptions, violations
from .commands.action import unsubscribe, keep, unkeep, delete_emails


@click.group()
@click.version_option(version='0.6.0', prog_name='Email Subscription Manager')
def cli():
    """
    Email Subscription Manager - Scan, detect, and manage email subscriptions.
    
    A Python tool to scan email accounts, detect subscriptions, and manage 
    unsubscribe operations with comprehensive safety checks.
    """
    pass


# Register command groups
cli.add_command(password, name='password')
cli.add_command(account, name='account')

# Register standalone commands
cli.add_command(init, name='init')
cli.add_command(stats, name='stats')
cli.add_command(scan, name='scan')
cli.add_command(scan_analyze, name='scan-analyze')
cli.add_command(detect_subscriptions, name='detect-subscriptions')
cli.add_command(list_subscriptions, name='list-subscriptions')
cli.add_command(violations, name='violations')
cli.add_command(unsubscribe, name='unsubscribe')
cli.add_command(keep, name='keep')
cli.add_command(unkeep, name='unkeep')
cli.add_command(delete_emails, name='delete-emails')


if __name__ == '__main__':
    cli()
