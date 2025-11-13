"""
Subscription matching/filtering functionality.

Provides flexible matching methods for finding subscriptions by:
- Explicit ID lists
- ID ranges
- SQL patterns (wildcards)
- Email domains

Used by keep/unkeep/list commands for bulk operations.
"""

from typing import List
from sqlalchemy.orm import Session
from .models import Subscription


class SubscriptionMatcher:
    """
    Matches subscriptions based on various criteria.
    
    All match methods return lists of subscription IDs that can be used
    for bulk operations like keep/unkeep or filtering list output.
    """
    
    def __init__(self, session: Session):
        """
        Initialize matcher with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def match_by_ids(self, ids: List[int]) -> List[int]:
        """
        Match subscriptions by explicit ID list.
        
        Validates that IDs exist in database and filters out nonexistent ones.
        Deduplicates any duplicate IDs in the input list.
        
        Args:
            ids: List of subscription IDs to match
            
        Returns:
            List of valid subscription IDs that exist in database
            
        Examples:
            >>> matcher.match_by_ids([1, 3, 5])
            [1, 3, 5]
            >>> matcher.match_by_ids([1, 999, 2])  # 999 doesn't exist
            [1, 2]
        """
        if not ids:
            return []
        
        # Deduplicate input IDs
        unique_ids = list(set(ids))
        
        # Query to find which IDs actually exist
        existing = self.session.query(Subscription.id)\
            .filter(Subscription.id.in_(unique_ids))\
            .all()
        
        return [row[0] for row in existing]
    
    def match_by_range(self, start: int, end: int) -> List[int]:
        """
        Match subscriptions by ID range (inclusive).
        
        Returns all subscription IDs that fall within the range [start, end].
        If end < start, the values are automatically swapped.
        Only returns IDs that actually exist in the database.
        
        Args:
            start: Start of ID range (inclusive)
            end: End of ID range (inclusive)
            
        Returns:
            List of subscription IDs within range that exist in database
            
        Examples:
            >>> matcher.match_by_range(5, 10)
            [5, 6, 7, 8, 9, 10]  # (assuming all exist)
            >>> matcher.match_by_range(10, 5)  # Reversed automatically
            [5, 6, 7, 8, 9, 10]
        """
        # Swap if reversed
        if end < start:
            start, end = end, start
        
        # Handle negative ranges
        if end < 1:
            return []
        
        # Query for IDs in range
        matching = self.session.query(Subscription.id)\
            .filter(Subscription.id >= start)\
            .filter(Subscription.id <= end)\
            .all()
        
        return [row[0] for row in matching]
    
    def match_by_pattern(self, pattern: str) -> List[int]:
        """
        Match subscriptions by SQL LIKE pattern on sender_email.
        
        Uses SQL LIKE syntax:
        - % matches any sequence of characters
        - _ matches any single character
        - Matching is case-insensitive
        
        Args:
            pattern: SQL LIKE pattern to match against sender_email
            
        Returns:
            List of subscription IDs with sender_email matching pattern
            
        Examples:
            >>> matcher.match_by_pattern('%@example.com')  # All from example.com
            [1, 2, 5]
            >>> matcher.match_by_pattern('%sutter%')  # Contains 'sutter'
            [10, 11]
            >>> matcher.match_by_pattern('news@%')  # Starts with 'news@'
            [3]
        """
        # Case-insensitive LIKE matching
        matching = self.session.query(Subscription.id)\
            .filter(Subscription.sender_email.ilike(pattern))\
            .all()
        
        return [row[0] for row in matching]
    
    def match_by_domain(self, domain: str) -> List[int]:
        """
        Match subscriptions by email domain.
        
        Matches all subscriptions where sender_email ends with @domain.
        Matching is case-insensitive. Leading @ is optional and will be stripped.
        
        Args:
            domain: Email domain to match (e.g., 'example.com' or '@example.com')
            
        Returns:
            List of subscription IDs from specified domain
            
        Examples:
            >>> matcher.match_by_domain('example.com')
            [1, 2, 5]  # All from @example.com
            >>> matcher.match_by_domain('@sutterhealth.org')  # @ is optional
            [10, 11]
            >>> matcher.match_by_domain('EXAMPLE.COM')  # Case-insensitive
            [1, 2, 5]
        """
        # Strip leading @ if present
        if domain.startswith('@'):
            domain = domain[1:]
        
        # Match emails ending with @domain
        pattern = f'%@{domain}'
        
        matching = self.session.query(Subscription.id)\
            .filter(Subscription.sender_email.ilike(pattern))\
            .all()
        
        return [row[0] for row in matching]
