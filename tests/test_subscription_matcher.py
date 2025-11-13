"""
Tests for subscription matching/filtering functionality.

These tests verify the pattern matching, range, domain, and list-based
subscription selection used by keep/unkeep/list commands.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.subscription_matcher import SubscriptionMatcher
from src.database.models import Base, Subscription, Account
from datetime import datetime


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def session(db_session):
    """Database session with test subscriptions."""
    # Create test account
    account = Account(
        email_address='test@example.com',
        provider='gmail',
        imap_server='imap.example.com',
        imap_port=993
    )
    db_session.add(account)
    db_session.flush()
    
    # Create test subscriptions with various patterns
    subs = [
        Subscription(account_id=account.id, sender_email='news@example.com', email_count=5),
        Subscription(account_id=account.id, sender_email='deals@example.com', email_count=10),
        Subscription(account_id=account.id, sender_email='alerts@test.com', email_count=3),
        Subscription(account_id=account.id, sender_email='updates@sutterhealth.org', email_count=8),
        Subscription(account_id=account.id, sender_email='info@sutterhealth.org', email_count=12),
        Subscription(account_id=account.id, sender_email='marketing@shop.com', email_count=15),
        Subscription(account_id=account.id, sender_email='promo@store.com', email_count=7),
        Subscription(account_id=account.id, sender_email='weekly@newsletter.com', email_count=20),
    ]
    for sub in subs:
        db_session.add(sub)
    db_session.commit()
    
    return db_session


class TestMatchByIds:
    """Test matching subscriptions by explicit ID list."""
    
    def test_single_id(self, session):
        """Match single subscription ID."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_ids([1])
        assert ids == [1]
    
    def test_multiple_ids(self, session):
        """Match multiple subscription IDs."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_ids([1, 3, 5])
        assert sorted(ids) == [1, 3, 5]
    
    def test_nonexistent_ids_filtered(self, session):
        """Nonexistent IDs are filtered out."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_ids([1, 999, 2, 888])
        assert sorted(ids) == [1, 2]
    
    def test_all_nonexistent_ids(self, session):
        """All nonexistent IDs returns empty list."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_ids([999, 888])
        assert ids == []
    
    def test_empty_list(self, session):
        """Empty ID list returns empty list."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_ids([])
        assert ids == []
    
    def test_duplicate_ids_deduped(self, session):
        """Duplicate IDs are deduplicated."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_ids([1, 2, 1, 3, 2])
        assert sorted(ids) == [1, 2, 3]


class TestMatchByRange:
    """Test matching subscriptions by ID range."""
    
    def test_simple_range(self, session):
        """Match subscription IDs in range."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_range(2, 5)
        assert sorted(ids) == [2, 3, 4, 5]
    
    def test_single_item_range(self, session):
        """Range with same start and end returns single ID."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_range(3, 3)
        assert ids == [3]
    
    def test_range_beyond_max(self, session):
        """Range extending beyond existing IDs only returns existing."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_range(6, 100)
        assert sorted(ids) == [6, 7, 8]
    
    def test_range_below_min(self, session):
        """Range starting below 1 begins at first existing ID."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_range(-5, 3)
        assert sorted(ids) == [1, 2, 3]
    
    def test_reversed_range_swapped(self, session):
        """Reversed range (end < start) is automatically swapped."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_range(5, 2)
        assert sorted(ids) == [2, 3, 4, 5]
    
    def test_range_with_gaps(self, session):
        """Range with missing IDs only returns existing IDs."""
        # Delete ID 4 to create a gap
        session.query(Subscription).filter_by(id=4).delete()
        session.commit()
        
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_range(2, 6)
        assert sorted(ids) == [2, 3, 5, 6]


class TestMatchByPattern:
    """Test matching subscriptions by SQL LIKE pattern."""
    
    def test_wildcard_prefix(self, session):
        """Match pattern with wildcard at start."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_pattern('%@example.com')
        # Should match: news@example.com, deals@example.com
        assert len(ids) == 2
    
    def test_wildcard_suffix(self, session):
        """Match pattern with wildcard at end."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_pattern('updates@%')
        # Should match: updates@sutterhealth.org
        assert len(ids) == 1
    
    def test_wildcard_both_sides(self, session):
        """Match pattern with wildcards on both sides."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_pattern('%sutter%')
        # Should match: updates@sutterhealth.org, info@sutterhealth.org
        assert len(ids) == 2
    
    def test_exact_match(self, session):
        """Match exact email address without wildcards."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_pattern('news@example.com')
        assert len(ids) == 1
    
    def test_case_insensitive(self, session):
        """Pattern matching is case-insensitive."""
        matcher = SubscriptionMatcher(session)
        ids1 = matcher.match_by_pattern('%EXAMPLE%')
        ids2 = matcher.match_by_pattern('%example%')
        assert sorted(ids1) == sorted(ids2)
        assert len(ids1) == 2
    
    def test_no_matches(self, session):
        """Pattern with no matches returns empty list."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_pattern('%nonexistent%')
        assert ids == []
    
    def test_pattern_with_underscore_wildcard(self, session):
        """Underscore matches single character."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_pattern('ne_s@example.com')
        # Should match: news@example.com
        assert len(ids) == 1


class TestMatchByDomain:
    """Test matching subscriptions by email domain."""
    
    def test_simple_domain(self, session):
        """Match subscriptions from specific domain."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_domain('example.com')
        # Should match: news@example.com, deals@example.com
        assert len(ids) == 2
    
    def test_subdomain(self, session):
        """Match subscriptions from subdomain."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_domain('sutterhealth.org')
        # Should match: updates@sutterhealth.org, info@sutterhealth.org
        assert len(ids) == 2
    
    def test_case_insensitive_domain(self, session):
        """Domain matching is case-insensitive."""
        matcher = SubscriptionMatcher(session)
        ids1 = matcher.match_by_domain('EXAMPLE.COM')
        ids2 = matcher.match_by_domain('example.com')
        assert sorted(ids1) == sorted(ids2)
    
    def test_domain_with_leading_at_sign(self, session):
        """Domain can be specified with @ prefix (user-friendly)."""
        matcher = SubscriptionMatcher(session)
        ids1 = matcher.match_by_domain('example.com')
        ids2 = matcher.match_by_domain('@example.com')
        assert sorted(ids1) == sorted(ids2)
    
    def test_nonexistent_domain(self, session):
        """Nonexistent domain returns empty list."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_domain('nonexistent.com')
        assert ids == []
    
    def test_partial_domain_no_match(self, session):
        """Partial domain doesn't match (must be exact domain)."""
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_domain('example')  # without .com
        assert ids == []
    
    def test_domain_with_subdomain_no_partial_match(self, session):
        """Domain matching requires exact domain, not substring."""
        # This should NOT match email@test.com from domain "st.com"
        matcher = SubscriptionMatcher(session)
        ids = matcher.match_by_domain('st.com')
        assert ids == []


class TestMatcherEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_database(self, db_session):
        """Matcher works with empty database."""
        matcher = SubscriptionMatcher(db_session)
        assert matcher.match_by_ids([1, 2]) == []
        assert matcher.match_by_range(1, 10) == []
        assert matcher.match_by_pattern('%test%') == []
        assert matcher.match_by_domain('example.com') == []
    
    def test_invalid_range_values(self, session):
        """Invalid range values handled gracefully."""
        matcher = SubscriptionMatcher(session)
        # Negative range
        ids = matcher.match_by_range(-10, -5)
        assert ids == []
    
    def test_none_values(self, session):
        """None values handled with empty results."""
        matcher = SubscriptionMatcher(session)
        
        # None IDs list returns empty
        assert matcher.match_by_ids([None]) == []
        
        # Empty string pattern returns empty
        assert matcher.match_by_pattern('') == []
        
        # Empty string domain returns empty
        assert matcher.match_by_domain('') == []
