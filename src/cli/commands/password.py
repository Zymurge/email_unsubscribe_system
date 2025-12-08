"""
Password management commands for Email Subscription Manager.

Handles storing, removing, and listing email account passwords.
"""

import click
from src.config.credentials import get_credential_store


@click.group()
def password():
    """Password management commands."""
    pass


@password.command('store')
@click.argument('email')
def store_password(email):
    """
    Store password for an email account.
    
    Args:
        email: Email address to store password for
    
    Example:
        python main.py password store user@example.com
    """
    password_value = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    
    store = get_credential_store()
    store.set_password(email, password_value)
    
    click.secho(f"✓ Password stored successfully for {email}", fg='green')
    click.echo(f"Credentials are saved in: {store.store_path}")


@password.command('remove')
@click.argument('email')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation prompt')
def remove_password(email, force):
    """
    Remove stored password for an email account.
    
    Args:
        email: Email address to remove password for
    
    Example:
        python main.py password remove user@example.com
    """
    store = get_credential_store()
    
    # Confirm removal unless forced
    if not force:
        if not click.confirm(f"Remove password for {email}?"):
            click.echo("Cancelled.")
            raise click.Abort()
    
    store.remove_password(email)
    click.secho(f"✓ Password removed successfully for {email}", fg='green')


@password.command('list')
def list_passwords():
    """
    List email accounts with stored passwords.
    
    Example:
        python main.py password list
    """
    store = get_credential_store()
    accounts = sorted(store.list_stored_emails())
    
    if not accounts:
        click.echo("No stored passwords.")
        return
    
    count = len(accounts)
    plural = "account" if count == 1 else "accounts"
    click.echo(f"\nStored passwords for {count} {plural}:")
    for email in accounts:
        click.echo(f"  - {email}")
    click.echo()
