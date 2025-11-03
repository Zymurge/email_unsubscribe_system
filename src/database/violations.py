"""
Violation reporting utilities for unsubscribe monitoring.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from .models import Account, Subscription, EmailMessage


class ViolationReporter:
    """Generate reports for unsubscribe violations."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_violations_summary(self, account_id: int = None) -> Dict[str, Any]:
        """Get summary of all unsubscribe violations."""
        query = self.session.query(Subscription).filter(
            Subscription.violation_count > 0
        )
        
        if account_id:
            query = query.filter(Subscription.account_id == account_id)
        
        violations = query.all()
        
        return {
            'total_violations': len(violations),
            'total_violation_emails': sum(sub.emails_after_unsubscribe for sub in violations),
            'violations_by_sender': [
                {
                    'sender_email': sub.sender_email,
                    'sender_name': sub.sender_name,
                    'unsubscribed_at': sub.unsubscribed_at,
                    'violation_count': sub.violation_count,
                    'emails_after_unsubscribe': sub.emails_after_unsubscribe,
                    'last_violation_at': sub.last_violation_at,
                    'days_since_unsubscribe': (
                        (sub.last_violation_at - sub.unsubscribed_at).days
                        if sub.last_violation_at and sub.unsubscribed_at else None
                    )
                }
                for sub in violations
            ]
        }
    
    def get_recent_violations(self, days: int = 7, account_id: int = None) -> List[Dict[str, Any]]:
        """Get violations from the last N days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = self.session.query(Subscription).filter(
            and_(
                Subscription.violation_count > 0,
                Subscription.last_violation_at >= cutoff_date
            )
        ).order_by(desc(Subscription.last_violation_at))
        
        if account_id:
            query = query.filter(Subscription.account_id == account_id)
        
        return [
            {
                'sender_email': sub.sender_email,
                'sender_name': sub.sender_name,
                'account_email': sub.account.email_address,
                'unsubscribed_at': sub.unsubscribed_at,
                'last_violation_at': sub.last_violation_at,
                'emails_after_unsubscribe': sub.emails_after_unsubscribe,
                'violation_count': sub.violation_count
            }
            for sub in query.all()
        ]
    
    def get_worst_offenders(self, limit: int = 10, account_id: int = None) -> List[Dict[str, Any]]:
        """Get the worst unsubscribe violators by email count."""
        query = self.session.query(Subscription).filter(
            Subscription.violation_count > 0
        ).order_by(desc(Subscription.emails_after_unsubscribe))
        
        if account_id:
            query = query.filter(Subscription.account_id == account_id)
        
        if limit:
            query = query.limit(limit)
        
        return [
            {
                'sender_email': sub.sender_email,
                'sender_name': sub.sender_name,
                'account_email': sub.account.email_address,
                'emails_after_unsubscribe': sub.emails_after_unsubscribe,
                'violation_count': sub.violation_count,
                'unsubscribed_at': sub.unsubscribed_at,
                'last_violation_at': sub.last_violation_at,
                'sender_domain': sub.sender_domain
            }
            for sub in query.all()
        ]
    
    def check_for_new_violations(self, account_id: int) -> List[Dict[str, Any]]:
        """Check for new violations by comparing recent emails against unsubscribed subscriptions."""
        # Get all unsubscribed subscriptions for this account
        unsubscribed = self.session.query(Subscription).filter(
            and_(
                Subscription.account_id == account_id,
                Subscription.unsubscribe_status == 'unsubscribed'
            )
        ).all()
        
        new_violations = []
        
        for subscription in unsubscribed:
            # Find emails from this sender that arrived after unsubscribe
            recent_emails = self.session.query(EmailMessage).filter(
                and_(
                    EmailMessage.account_id == account_id,
                    EmailMessage.sender_email == subscription.sender_email,
                    EmailMessage.date_sent > subscription.unsubscribed_at
                )
            ).order_by(desc(EmailMessage.date_sent)).all()
            
            if recent_emails:
                # Record violations
                for email in recent_emails:
                    if subscription.is_violation_email(email.date_sent):
                        subscription.record_violation(email.date_sent)
                
                new_violations.append({
                    'subscription': subscription,
                    'violating_emails': recent_emails,
                    'violation_count': len(recent_emails)
                })
        
        # Commit the violation updates
        self.session.commit()
        
        return new_violations


def generate_violation_report(session: Session, account_id: int = None) -> str:
    """Generate a formatted violation report."""
    reporter = ViolationReporter(session)
    
    summary = reporter.get_violations_summary(account_id)
    recent = reporter.get_recent_violations(7, account_id)
    worst = reporter.get_worst_offenders(10, account_id)
    
    report = []
    report.append("=== UNSUBSCRIBE VIOLATION REPORT ===\n")
    
    report.append(f"Summary:")
    report.append(f"  Total violating subscriptions: {summary['total_violations']}")
    report.append(f"  Total emails after unsubscribe: {summary['total_violation_emails']}")
    
    if recent:
        report.append(f"\nRecent Violations (Last 7 days): {len(recent)}")
        for violation in recent[:5]:  # Show top 5
            report.append(f"  • {violation['sender_email']}")
            report.append(f"    Unsubscribed: {violation['unsubscribed_at']}")
            report.append(f"    Last violation: {violation['last_violation_at']}")
            report.append(f"    Emails since unsubscribe: {violation['emails_after_unsubscribe']}")
    
    if worst:
        report.append(f"\nWorst Offenders:")
        for i, offender in enumerate(worst[:5], 1):
            report.append(f"  {i}. {offender['sender_email']} ({offender['sender_domain']})")
            report.append(f"     {offender['emails_after_unsubscribe']} emails after unsubscribe")
            report.append(f"     Last violation: {offender['last_violation_at']}")
    
    return "\n".join(report)