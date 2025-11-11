"""
Test that quoted-printable soft line breaks are properly handled in URL extraction.

This addresses the issue where URLs spanning multiple lines in email body
(indicated by = at end of line) were being truncated.
"""

import pytest
from src.email_processor.unsubscribe.extractors import UnsubscribeLinkExtractor


class TestQuotedPrintableUnwrap:
    """Test handling of quoted-printable encoding in URLs."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = UnsubscribeLinkExtractor()
    
    def test_unwrap_soft_line_breaks(self):
        """Test that soft line breaks (=\\n) are removed correctly."""
        text = "Visit https://manage.kmail-lists.com/subscriptions/unsubsc=\nribe?id=123"
        result = self.extractor._unwrap_quoted_printable_lines(text)
        
        assert result == "Visit https://manage.kmail-lists.com/subscriptions/unsubscribe?id=123"
    
    def test_unwrap_with_crlf(self):
        """Test handling of CRLF line endings."""
        text = "Visit https://manage.kmail-lists.com/subscriptio=\r\nns/unsubscribe"
        result = self.extractor._unwrap_quoted_printable_lines(text)
        
        assert result == "Visit https://manage.kmail-lists.com/subscriptions/unsubscribe"
    
    def test_unwrap_with_encoded_equals(self):
        """Test handling of =3D encoding for equals signs."""
        text = "https://example.com/unsub?token=3Dabc123"
        result = self.extractor._unwrap_quoted_printable_lines(text)
        
        assert result == "https://example.com/unsub?token=abc123"
    
    def test_extract_wrapped_url_from_text(self):
        """Test that URLs split across lines are extracted correctly."""
        text = """
        To unsubscribe, click here:
        https://manage.kmail-lists.com/subscriptions/unsubsc=
ribe?a=KwBvWb&c=01GGSKRMQX779SXS7VKT7Y6B0Q
        """
        
        links = self.extractor._extract_from_text(text)
        
        # Should find the complete URL
        assert len(links) > 0
        assert any('kmail-lists.com' in link for link in links)
        
        # Verify the URL is complete (not ending with =)
        kmail_links = [link for link in links if 'kmail-lists.com' in link]
        assert len(kmail_links) == 1
        assert not kmail_links[0].endswith('=')
        assert 'unsubscribe' in kmail_links[0]
    
    def test_extract_multiple_wrapped_urls(self):
        """Test extraction of multiple URLs with wrapped lines."""
        text = """
        Unsubscribe: https://manage.kmail-lists.com/subscriptions/unsubsc=
ribe?id=1
        
        Preferences: https://manage.kmail-lists.com/subscriptio=
ns/manage?id=2
        """
        
        links = self.extractor._extract_from_text(text)
        
        kmail_links = [link for link in links if 'kmail-lists.com' in link]
        assert len(kmail_links) == 2
        
        # Both URLs should be complete
        assert all('unsubscribe' in link or 'manage' in link for link in kmail_links)
        assert all(not link.endswith('=') for link in kmail_links)
    
    def test_no_false_positives_on_normal_text(self):
        """Ensure normal text without soft line breaks is not affected."""
        text = "The price is $50 = great deal!\nVisit https://example.com/sale"
        
        links = self.extractor._extract_from_text(text)
        
        # Should still extract the normal URL
        assert len(links) == 1
        assert links[0] == "https://example.com/sale"
    
    def test_real_world_kmail_example(self):
        """Test with a real-world example from the database."""
        # This simulates the actual text content that would be in an email
        text = """
        UNSUBSCRIBE FROM THIS LIST
        
        To stop receiving emails from us, click below:
        https://manage.kmail-lists.com/subscriptions/unsubsc=
ribe?a=JrLjph&c=01EM30TTSXYQSP8CS2WN0RMDHM&k=091bb3bbb4b3f41d3082d9b6d7=
968128&m=01K9N892TEBYF27D52SDJR4MVE&r=01K9R5Z2J4DKKP8AZ495M20DJZ
        """
        
        links = self.extractor._extract_from_text(text)
        
        # Should extract one complete kmail-lists.com URL
        kmail_links = [link for link in links if 'kmail-lists.com' in link]
        assert len(kmail_links) == 1
        
        url = kmail_links[0]
        # URL should be complete with all parameters
        assert 'unsubscribe' in url
        assert 'a=JrLjph' in url
        assert 'k=091bb3bbb4b3f41d3082d9b6d7968128' in url
        assert not url.endswith('=')


class TestQuotedPrintableInHtml:
    """Test handling of quoted-printable in HTML content."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = UnsubscribeLinkExtractor()
    
    def test_extract_wrapped_url_from_html(self):
        """Test extraction from HTML with wrapped URLs."""
        html = """
        <html>
        <body>
        <a href="https://manage.kmail-lists.com/subscriptions/unsubsc=
ribe?id=123">Unsubscribe</a>
        </body>
        </html>
        """
        
        links = self.extractor._extract_from_html(html)
        
        # Should extract the complete URL
        assert len(links) > 0
        kmail_links = [link for link in links if 'kmail-lists.com' in link]
        assert len(kmail_links) == 1
        assert 'unsubscribe?id=123' in kmail_links[0]
        assert not kmail_links[0].endswith('=')
