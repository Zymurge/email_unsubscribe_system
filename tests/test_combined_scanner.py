"""
Tests for the CombinedEmailScanner hybrid approach.

This module tests the integrated scan+analyze functionality
that performs email scanning, subscription detection, and 
unsubscribe extraction in a single pass.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from src.email_processor.combined_scanner import CombinedEmailScanner
from src.database.models import Account, EmailMessage, Subscription


class TestCombinedEmailScanner:
    """Test the CombinedEmailScanner hybrid approach."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=Session)
        self.scanner = CombinedEmailScanner(self.mock_session, enable_debug_storage=True)

    def test_combined_scanner_initialization(self):
        """Test that the combined scanner initializes correctly."""
        # Test with debug storage enabled
        scanner_debug = CombinedEmailScanner(self.mock_session, enable_debug_storage=True)
        assert scanner_debug.enable_debug_storage is True
        assert scanner_debug.session == self.mock_session
        assert hasattr(scanner_debug, 'unsubscribe_extractor')
        assert hasattr(scanner_debug, 'unsubscribe_classifier')
        assert hasattr(scanner_debug, 'unsubscribe_validator')

        # Test with debug storage disabled
        scanner_no_debug = CombinedEmailScanner(self.mock_session, enable_debug_storage=False)
        assert scanner_no_debug.enable_debug_storage is False

    def test_analyze_single_message_basic(self):
        """Test single message analysis with basic email data."""
        # Mock message data
        msg_data = {
            'message_id': 'test@example.com',
            'sender_email': 'newsletter@company.com',
            'sender_name': 'Company Newsletter',
            'subject': 'Weekly Sale - Don\'t Miss Out!',
            'date_sent': datetime.now(),
            'headers': {
                'List-Unsubscribe': '<https://company.com/unsubscribe?id=123>',
                'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'
            },
            'body_html': '<html><body><p>Great deals!</p><a href="https://company.com/unsubscribe?id=123">Unsubscribe</a></body></html>',
            'body_text': 'Great deals! To unsubscribe visit: https://company.com/unsubscribe?id=123',
            'has_unsubscribe_header': True
        }

        # Mock the extractor to return some links
        self.scanner.unsubscribe_extractor.extract_all_unsubscribe_methods = Mock(
            return_value=['https://company.com/unsubscribe?id=123']
        )

        # Mock the classifier to return a classified method
        self.scanner.unsubscribe_classifier.classify_method = Mock(
            return_value={
                'method': 'http_get',
                'url': 'https://company.com/unsubscribe?id=123',
                'confidence': 0.9
            }
        )

        # Mock the validator to return safe
        self.scanner.unsubscribe_validator.validate_safety = Mock(
            return_value={'is_safe': True, 'warnings': []}
        )

        # Test the analysis
        result = self.scanner._analyze_single_message(msg_data, 1)

        # Verify the result structure
        assert isinstance(result, dict)
        assert 'has_unsubscribe_header' in result
        assert 'has_unsubscribe_link' in result
        assert 'unsubscribe_methods' in result
        assert 'subscription_confidence' in result

        # Verify unsubscribe detection
        assert result['has_unsubscribe_header'] is True
        assert result['has_unsubscribe_link'] is True
        assert len(result['unsubscribe_methods']) == 1
        assert result['unsubscribe_methods'][0]['method'] == 'http_get'

        # Verify confidence calculation
        assert result['subscription_confidence'] > 0

        # Verify debug storage (enabled in setup)
        assert result['debug_headers_json'] is not None
        assert result['debug_links_json'] is not None
        assert result['debug_notes'] is not None

    def test_analyze_single_message_no_unsubscribe(self):
        """Test single message analysis with no unsubscribe methods."""
        # Mock message data without unsubscribe info
        msg_data = {
            'message_id': 'personal@friend.com',
            'sender_email': 'friend@example.com',
            'sender_name': 'John Friend',
            'subject': 'Personal message',
            'date_sent': datetime.now(),
            'headers': {},
            'body_html': '<html><body><p>Hey, how are you?</p></body></html>',
            'body_text': 'Hey, how are you?',
            'has_unsubscribe_header': False
        }

        # Mock the extractor to return no links
        self.scanner.unsubscribe_extractor.extract_all_unsubscribe_methods = Mock(
            return_value=[]
        )

        # Test the analysis
        result = self.scanner._analyze_single_message(msg_data, 1)

        # Verify no unsubscribe methods found
        assert result['has_unsubscribe_header'] is False
        assert result['has_unsubscribe_link'] is False
        assert len(result['unsubscribe_methods']) == 0

        # Should still have some confidence based on sender patterns
        assert result['subscription_confidence'] >= 0

    def test_calculate_subscription_confidence(self):
        """Test subscription confidence calculation logic."""
        # Test high confidence case
        high_conf_msg = {
            'sender_email': 'no-reply@marketing.company.com',
            'subject': 'Exclusive Newsletter Sale - Limited Time Offer!'
        }
        high_conf_analysis = {
            'has_unsubscribe_header': True,
            'unsubscribe_methods': [{'method': 'http_get', 'url': 'test'}]
        }
        
        confidence = self.scanner._calculate_subscription_confidence(high_conf_msg, high_conf_analysis)
        assert confidence >= 70  # Should be high confidence

        # Test low confidence case
        low_conf_msg = {
            'sender_email': 'person@gmail.com',
            'subject': 'Re: Meeting tomorrow'
        }
        low_conf_analysis = {
            'has_unsubscribe_header': False,
            'unsubscribe_methods': []
        }
        
        confidence = self.scanner._calculate_subscription_confidence(low_conf_msg, low_conf_analysis)
        assert confidence <= 30  # Should be low confidence

    def test_has_unsubscribe_link_detection(self):
        """Test enhanced unsubscribe link detection in body text."""
        # Test positive cases
        assert self.scanner._has_unsubscribe_link('Click here to unsubscribe from future emails')
        assert self.scanner._has_unsubscribe_link('To opt out of these messages, visit our website')
        assert self.scanner._has_unsubscribe_link('Manage your email preferences here')
        assert self.scanner._has_unsubscribe_link('STOP EMAILS by clicking unsubscribe')

        # Test negative cases
        assert not self.scanner._has_unsubscribe_link('Thanks for your purchase!')
        assert not self.scanner._has_unsubscribe_link('Meeting scheduled for tomorrow')
        assert not self.scanner._has_unsubscribe_link('')
        assert not self.scanner._has_unsubscribe_link(None)

    def test_debug_storage_enabled(self):
        """Test that debug storage works when enabled."""
        scanner_debug = CombinedEmailScanner(self.mock_session, enable_debug_storage=True)
        
        msg_data = {
            'sender_email': 'test@example.com',
            'subject': 'Test Newsletter',
            'headers': {'List-Unsubscribe': '<https://example.com/unsub>'},
            'body_html': '<a href="https://example.com/unsub">Unsubscribe</a>',
            'body_text': 'Unsubscribe here',
            'has_unsubscribe_header': True
        }

        # Mock dependencies
        scanner_debug.unsubscribe_extractor.extract_all_unsubscribe_methods = Mock(return_value=[])
        
        result = scanner_debug._analyze_single_message(msg_data, 1)
        
        # Should have debug information
        assert result['debug_headers_json'] is not None
        assert result['debug_links_json'] is not None
        assert result['debug_notes'] is not None
        
        # Debug notes should be valid JSON
        debug_info = json.loads(result['debug_notes'])
        assert 'processing_timestamp' in debug_info
        assert 'extraction_methods_found' in debug_info

    def test_debug_storage_disabled(self):
        """Test that debug storage is skipped when disabled."""
        scanner_no_debug = CombinedEmailScanner(self.mock_session, enable_debug_storage=False)
        
        msg_data = {
            'sender_email': 'test@example.com',
            'subject': 'Test Newsletter',
            'headers': {},
            'body_html': '',
            'body_text': '',
            'has_unsubscribe_header': False
        }

        # Mock dependencies
        scanner_no_debug.unsubscribe_extractor.extract_all_unsubscribe_methods = Mock(return_value=[])
        
        result = scanner_no_debug._analyze_single_message(msg_data, 1)
        
        # Should not have debug information
        assert result['debug_headers_json'] is None
        assert result['debug_links_json'] is None
        assert result['debug_notes'] is None

    def test_error_handling_in_analysis(self):
        """Test that errors in message analysis are handled gracefully."""
        msg_data = {
            'sender_email': 'test@example.com',
            'subject': 'Test',
            'headers': {'Some-Header': 'value'},  # Add some content to trigger extraction
            'body_html': '<p>test</p>',  # Add some content to trigger extraction
            'body_text': 'test',  # Add some content to trigger extraction
            'has_unsubscribe_header': False
        }

        # Mock extractor to raise an exception
        self.scanner.unsubscribe_extractor.extract_all_unsubscribe_methods = Mock(
            side_effect=Exception('Test error')
        )
        
        result = self.scanner._analyze_single_message(msg_data, 1)
        
        # Should still return a result with basic structure
        assert isinstance(result, dict)
        assert 'has_unsubscribe_header' in result
        assert 'unsubscribe_methods' in result
        assert len(result['unsubscribe_methods']) == 0

        # Debug info should contain error details if debug storage enabled
        if self.scanner.enable_debug_storage:
            assert result['debug_notes'] is not None
            debug_info = json.loads(result['debug_notes'])
            assert 'error' in debug_info


class TestCombinedScannerIntegration:
    """Integration tests for CombinedEmailScanner."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock(spec=Session)
        self.scanner = CombinedEmailScanner(self.mock_session)

    @patch('src.email_processor.combined_scanner.get_imap_settings')
    @patch('src.email_processor.combined_scanner.IMAPConnection')
    def test_scan_account_with_analysis_account_not_found(self, mock_imap_conn, mock_get_settings):
        """Test scan when account doesn't exist."""
        # Mock account query to return None
        self.mock_session.query.return_value.get.return_value = None
        
        with pytest.raises(ValueError, match="Account 999 not found"):
            self.scanner.scan_account_with_analysis(999, "password")

    @patch('src.email_processor.combined_scanner.get_imap_settings')
    @patch('src.email_processor.combined_scanner.IMAPConnection')
    def test_scan_account_connection_failure(self, mock_imap_conn, mock_get_settings):
        """Test scan when IMAP connection fails."""
        # Mock account exists
        mock_account = Mock()
        mock_account.email_address = 'test@example.com'
        mock_account.provider = 'gmail'
        self.mock_session.query.return_value.get.return_value = mock_account
        
        # Mock IMAP settings
        mock_get_settings.return_value = {
            'server': 'imap.gmail.com',
            'port': 993,
            'use_ssl': True
        }
        
        # Mock IMAP connection to fail
        mock_imap = Mock()
        mock_imap.connect.return_value = False
        mock_imap_conn.return_value.__enter__.return_value = mock_imap
        
        with pytest.raises(ConnectionError, match="Failed to connect to test@example.com"):
            self.scanner.scan_account_with_analysis(1, "wrong_password")