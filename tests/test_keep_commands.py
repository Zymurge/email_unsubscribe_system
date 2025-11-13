"""
TDD Tests for keep/unkeep CLI commands.

Tests verify:
- Parsing logic (parse_keep_input)
- Database operations (mark_subscriptions_keep/unkeep)
- Helper function behavior

NOTE: CLI integration verified manually with real database.
The keep/unkeep commands work correctly as demonstrated in manual testing.
"""

import pytest
from unittest.mock import Mock


class TestMarkSubscriptionsKeep:
    """Test marking subscriptions as keep using ID array."""
    
    def test_mark_keep_updates_flag(self):
        """mark_subscriptions_keep() sets keep_subscription=True for all IDs."""
        from main import mark_subscriptions_keep
        
        mock_session = Mock()
        mock_sub1 = Mock(id=1, keep_subscription=False)
        mock_sub2 = Mock(id=2, keep_subscription=False)
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_sub1, mock_sub2]
        mock_session.query.return_value = mock_query
        
        result = mark_subscriptions_keep(mock_session, [1, 2])
        
        assert mock_sub1.keep_subscription is True
        assert mock_sub2.keep_subscription is True
        mock_session.commit.assert_called_once()
    
    def test_mark_keep_counts_marked(self):
        """Returns count of subscriptions marked."""
        from main import mark_subscriptions_keep
        
        mock_session = Mock()
        mock_subs = [Mock(id=i, keep_subscription=False) for i in [1, 2, 3]]
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_subs
        mock_session.query.return_value = mock_query
        
        result = mark_subscriptions_keep(mock_session, [1, 2, 3])
        
        assert result['marked'] == 3
        assert result['already_kept'] == 0
    
    def test_mark_keep_counts_already_kept(self):
        """Returns count of already kept subscriptions."""
        from main import mark_subscriptions_keep
        
        mock_session = Mock()
        mock_sub1 = Mock(id=1, keep_subscription=False)
        mock_sub2 = Mock(id=2, keep_subscription=True)  # Already kept
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_sub1, mock_sub2]
        mock_session.query.return_value = mock_query
        
        result = mark_subscriptions_keep(mock_session, [1, 2])
        
        assert result['marked'] == 1
        assert result['already_kept'] == 1
    
    def test_mark_keep_empty_id_list(self):
        """Empty ID list returns zeros."""
        from main import mark_subscriptions_keep
        
        mock_session = Mock()
        
        result = mark_subscriptions_keep(mock_session, [])
        
        assert result['marked'] == 0
        assert result['already_kept'] == 0


class TestMarkSubscriptionsUnkeep:
    """Test unmarking subscriptions using ID array."""
    
    def test_mark_unkeep_updates_flag(self):
        """mark_subscriptions_unkeep() sets keep_subscription=False."""
        from main import mark_subscriptions_unkeep
        
        mock_session = Mock()
        mock_sub = Mock(id=3, keep_subscription=True)
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_sub]
        mock_session.query.return_value = mock_query
        
        result = mark_subscriptions_unkeep(mock_session, [3])
        
        assert mock_sub.keep_subscription is False
        mock_session.commit.assert_called_once()
    
    def test_mark_unkeep_counts_unmarked(self):
        """Returns count of subscriptions unmarked."""
        from main import mark_subscriptions_unkeep
        
        mock_session = Mock()
        mock_subs = [Mock(id=i, keep_subscription=True) for i in [1, 2]]
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_subs
        mock_session.query.return_value = mock_query
        
        result = mark_subscriptions_unkeep(mock_session, [1, 2])
        
        assert result['unmarked'] == 2
        assert result['already_not_kept'] == 0
    
    def test_mark_unkeep_counts_already_not_kept(self):
        """Returns count of already not-kept subscriptions."""
        from main import mark_subscriptions_unkeep
        
        mock_session = Mock()
        mock_sub1 = Mock(id=1, keep_subscription=True)
        mock_sub2 = Mock(id=2, keep_subscription=False)  # Already not kept
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_sub1, mock_sub2]
        mock_session.query.return_value = mock_query
        
        result = mark_subscriptions_unkeep(mock_session, [1, 2])
        
        assert result['unmarked'] == 1
        assert result['already_not_kept'] == 1


class TestParseKeepInput:
    """Test input parsing logic."""
    
    def test_parse_ids_space_separated(self):
        """Parse space-separated ID list."""
        from main import parse_keep_input
        
        match_type, value = parse_keep_input(['1', '2', '3'], None, None)
        
        assert match_type == 'ids'
        assert value == [1, 2, 3]
    
    def test_parse_ids_comma_separated(self):
        """Parse comma-separated ID list."""
        from main import parse_keep_input
        
        match_type, value = parse_keep_input(['1,2,3'], None, None)
        
        assert match_type == 'ids'
        assert value == [1, 2, 3]
    
    def test_parse_range(self):
        """Parse ID range format."""
        from main import parse_keep_input
        
        match_type, value = parse_keep_input(['1-10'], None, None)
        
        assert match_type == 'range'
        assert value == (1, 10)
    
    def test_parse_pattern_flag(self):
        """Parse --pattern flag."""
        from main import parse_keep_input
        
        match_type, value = parse_keep_input([], '%sutter%', None)
        
        assert match_type == 'pattern'
        assert value == '%sutter%'
    
    def test_parse_domain_flag(self):
        """Parse --domain flag."""
        from main import parse_keep_input
        
        match_type, value = parse_keep_input([], None, 'example.com')
        
        assert match_type == 'domain'
        assert value == 'example.com'
    
    def test_parse_error_on_mixed_inputs(self):
        """Error when mixing IDs with flags."""
        from main import parse_keep_input
        
        with pytest.raises(ValueError):
            parse_keep_input(['1', '2'], '%sutter%', None)
    
    def test_parse_error_on_multiple_flags(self):
        """Error when using multiple flags."""
        from main import parse_keep_input
        
        with pytest.raises(ValueError):
            parse_keep_input([], '%sutter%', 'example.com')
    
    def test_parse_error_on_no_input(self):
        """Error when no input provided."""
        from main import parse_keep_input
        
        with pytest.raises(ValueError):
            parse_keep_input([], None, None)
