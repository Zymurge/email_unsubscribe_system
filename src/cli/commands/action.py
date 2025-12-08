"""
Action commands for Email Subscription Manager.

Handles unsubscribe, keep/unkeep, and email deletion operations.
"""

import click
from src.cli_session import get_cli_session_manager
from src.database.models import Account, Subscription
from src.email_processor.email_deleter import EmailDeleter
from ..utils import get_password_for_account, parse_subscription_ids


def execute_unsubscribe(session, subscription, dry_run=False):
    """Execute unsubscribe for a subscription."""
    from src.unsubscribe_executor.http_executor import HttpGetExecutor
    from src.unsubscribe_executor.http_post_executor import HttpPostExecutor
    from src.unsubscribe_executor.email_reply_executor import EmailReplyExecutor
    
    # Determine executor based on method
    if subscription.unsubscribe_method == 'http_get':
        executor = HttpGetExecutor(session, dry_run=dry_run)
    elif subscription.unsubscribe_method in ['http_post', 'oneclick']:
        executor = HttpPostExecutor(session, dry_run=dry_run)
    elif subscription.unsubscribe_method == 'email_reply':
        executor = EmailReplyExecutor(session, dry_run=dry_run)
    else:
        return False
    
    return executor.execute(subscription)


@click.command('unsubscribe')
@click.option('--id', 'subscription_id', type=int, required=True, help='Subscription ID to unsubscribe from')
@click.option('--dry-run', is_flag=True, help='Show what would happen without executing')
def unsubscribe(subscription_id, dry_run):
    """
    Execute unsubscribe for a subscription.
    
    Performs the actual unsubscribe action using the detected method.
    
    Example:
        python main.py unsubscribe --id 5
        python main.py unsubscribe --id 5 --dry-run
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # Find subscription
        subscription = session.query(Subscription).filter_by(id=subscription_id).first()
        if not subscription:
            click.secho(f"✗ Error: Subscription {subscription_id} not found", fg='red')
            raise click.Abort()
        
        if dry_run:
            click.echo(f"\n[DRY RUN] Would unsubscribe from:")
            click.echo(f"  ID: {subscription.id}")
            click.echo(f"  Sender: {subscription.sender_email}")
            click.echo(f"  Method: {subscription.unsubscribe_method}")
            return
        
        # Execute unsubscribe
        click.echo(f"\nUnsubscribing from {subscription.sender_email}...")
        
        try:
            success = execute_unsubscribe(session, subscription, dry_run=False)
            
            if success:
                click.secho(f"✓ Successfully unsubscribed from {subscription.sender_email}", fg='green')
            else:
                click.secho(f"✗ Unsubscribe failed for {subscription.sender_email}", fg='red')
                raise click.Abort()
                
        except Exception as e:
            click.secho(f"✗ Error during unsubscribe: {e}", fg='red')
            raise click.Abort()


@click.command('keep')
@click.argument('ids')
def keep(ids):
    """
    Mark subscriptions to keep (don't unsubscribe).
    
    Supports multiple ID formats:
        - Single: 5
        - Multiple: 1,2,3
        - Range: 1-10
        - Mixed: 1,3-5,7
    
    Example:
        python main.py keep 5
        python main.py keep 1,2,3
        python main.py keep 1-10
    """
    session_manager = get_cli_session_manager()
    
    try:
        id_list = parse_subscription_ids(ids)
    except ValueError as e:
        click.secho(f"✗ Error parsing IDs: {e}", fg='red')
        raise click.Abort()
    
    with session_manager.get_session() as session:
        # Find subscriptions
        subscriptions = session.query(Subscription).filter(
            Subscription.id.in_(id_list)
        ).all()
        
        if not subscriptions:
            click.secho(f"✗ Error: No subscriptions found with IDs {ids}", fg='red')
            raise click.Abort()
        
        # Mark as keep
        for sub in subscriptions:
            sub.keep_subscription = True
        
        session.commit()
        
        click.secho(f"✓ Marked {len(subscriptions)} subscription(s) to keep", fg='green')
        for sub in subscriptions:
            click.echo(f"  - {sub.id}: {sub.sender_email}")


@click.command('unkeep')
@click.argument('ids')
def unkeep(ids):
    """
    Unmark subscriptions to keep (allow unsubscribe).
    
    Supports same ID formats as keep command.
    
    Example:
        python main.py unkeep 5
        python main.py unkeep 1-10
    """
    session_manager = get_cli_session_manager()
    
    try:
        id_list = parse_subscription_ids(ids)
    except ValueError as e:
        click.secho(f"✗ Error parsing IDs: {e}", fg='red')
        raise click.Abort()
    
    with session_manager.get_session() as session:
        # Find subscriptions
        subscriptions = session.query(Subscription).filter(
            Subscription.id.in_(id_list)
        ).all()
        
        if not subscriptions:
            click.secho(f"✗ Error: No subscriptions found with IDs {ids}", fg='red')
            raise click.Abort()
        
        # Unmark keep
        for sub in subscriptions:
            sub.keep_subscription = False
        
        session.commit()
        
        click.secho(f"✓ Unmarked {len(subscriptions)} subscription(s)", fg='green')
        for sub in subscriptions:
            click.echo(f"  - {sub.id}: {sub.sender_email}")


@click.command('delete-emails')
@click.option('--id', 'subscription_id', type=int, required=True, help='Subscription ID')
@click.option('--dry-run', is_flag=True, help='Preview what would be deleted')
@click.option('--confirm', is_flag=True, help='Confirm deletion (required for actual deletion)')
def delete_emails(subscription_id, dry_run, confirm):
    """
    Delete emails from a subscription.
    
    ⚠️  WARNING: This permanently deletes emails!
    
    Safety checks:
        - Subscription must be unsubscribed
        - Cannot be marked as "keep"
        - No violations detected
        - Waiting period must have elapsed
    
    Example:
        python main.py delete-emails --id 5 --dry-run
        python main.py delete-emails --id 5 --confirm
    """
    session_manager = get_cli_session_manager()
    
    with session_manager.get_session() as session:
        # Find subscription
        subscription = session.query(Subscription).filter_by(id=subscription_id).first()
        if not subscription:
            click.secho(f"✗ Error: Subscription {subscription_id} not found", fg='red')
            raise click.Abort()
        
        # Get account
        account = session.query(Account).filter_by(id=subscription.account_id).first()
        
        if dry_run:
            # Preview deletion
            click.echo(f"\n[DRY RUN] Email deletion preview for:")
            click.echo(f"  Subscription: {subscription.sender_email}")
            
            deleter = EmailDeleter(session)
            preview = deleter.preview_deletion(subscription.id)
            
            click.echo(f"\n  Emails to delete: {preview.emails_to_delete}")
            if preview.emails_to_delete > 0:
                click.echo(f"  Date range: {preview.earliest_date} to {preview.latest_date}")
            
            if not preview.can_delete:
                click.secho(f"\n  ✗ Cannot delete: {preview.reason}", fg='yellow')
            else:
                click.secho(f"\n  ✓ Safe to delete", fg='green')
            
            return
        
        if not confirm:
            click.secho("✗ Error: Email deletion requires --confirm flag", fg='red')
            click.echo("\nThis is a destructive operation. Use --dry-run to preview first.")
            raise click.Abort()
        
        # Get password
        try:
            password = get_password_for_account(account.email_address)
        except Exception as e:
            click.secho(f"✗ Error getting password: {e}", fg='red')
            raise click.Abort()
        
        # Delete emails
        click.echo(f"\nDeleting emails for {subscription.sender_email}...")
        click.echo("This may take a while...")
        
        try:
            deleter = EmailDeleter(session)
            result = deleter.delete_subscription_emails(
                subscription.id,
                account.email_address,
                password
            )
            
            if result.success:
                click.secho(f"\n✓ Deletion complete", fg='green')
                click.echo(f"  Total emails deleted: {result.emails_deleted}")
                click.echo(f"  IMAP deleted: {result.imap_deleted}")
                click.echo(f"  Database deleted: {result.db_deleted}")
            else:
                click.secho(f"\n✗ Deletion failed: {result.error}", fg='red')
                raise click.Abort()
                
        except Exception as e:
            click.secho(f"✗ Error during deletion: {e}", fg='red')
            raise click.Abort()
