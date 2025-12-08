"""
Admin commands for Email Subscription Manager.

Handles database initialization and system setup.
"""

import click
from src.database import init_database


@click.command('init')
def init():
    """
    Initialize the database.
    
    Creates the database schema and required tables.
    
    Example:
        python main.py init
    """
    try:
        db_path = init_database()
        click.secho("✓ Database initialized successfully", fg='green')
        click.echo(f"Database location: {db_path}")
    except Exception as e:
        click.secho(f"✗ Error initializing database: {e}", fg='red')
        raise click.Abort()
