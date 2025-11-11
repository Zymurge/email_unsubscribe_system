"""
Unsubscribe link extraction from email headers and body content.

This module handles extracting unsubscribe links from various email sources:
- Email headers (List-Unsubscribe, List-Unsubscribe-Post)
- HTML body content
- Plain text body content
"""

import re
import urllib.parse
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from .constants import (
    UNSUBSCRIBE_KEYWORDS, URL_PATTERN, HEADER_URL_PATTERN, EMAIL_PATTERN
)
from .logging import UnsubscribeLogger


class UnsubscribeLinkExtractor:
    """Extract unsubscribe links from email headers and body content."""
    
    def __init__(self):
        # Use shared constants instead of instance variables
        self.unsubscribe_keywords = UNSUBSCRIBE_KEYWORDS
        self.url_pattern = URL_PATTERN
        self.header_url_pattern = HEADER_URL_PATTERN
        self.logger = UnsubscribeLogger("link_extractor")
    
    def _unwrap_quoted_printable_lines(self, text: str) -> str:
        """
        Handle quoted-printable soft line breaks in text content.
        
        In quoted-printable encoding, a line ending with '=' is a soft line break
        that indicates the line continues on the next line without a space.
        This is critical for reconstructing URLs that span multiple lines.
        
        Example:
            "https://example.com/unsubscribe?id=3D\nabc123"
            becomes "https://example.com/unsubscribe?id=3Dabc123"
        """
        # Remove soft line breaks (= followed by newline)
        # This handles both \n and \r\n line endings
        text = re.sub(r'=\r?\n', '', text)
        
        # Also handle the case where quoted-printable encoding uses =3D for '='
        # This ensures URLs with encoded characters are properly reconstructed
        text = text.replace('=3D', '=')
        
        return text
    
    def extract_from_headers(self, headers: Dict[str, str]) -> List[str]:
        """Extract unsubscribe links from email headers.
        
        Supports:
        - List-Unsubscribe header (RFC 2369)
        - List-Unsubscribe-Post header (RFC 8058)
        """
        links = []
        
        # Extract from List-Unsubscribe header
        list_unsubscribe = headers.get('List-Unsubscribe', '')
        if list_unsubscribe:
            # Parse header format: <url1>, <url2>, etc.
            matches = self.header_url_pattern.findall(list_unsubscribe)
            for match in matches:
                if match.strip():
                    links.append(match.strip())
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(links))
    
    def extract_from_body(self, html_content: Optional[str], text_content: Optional[str]) -> List[str]:
        """Extract unsubscribe links from email body content."""
        links = []
        
        # Extract from HTML content
        if html_content:
            html_links = self._extract_from_html(html_content)
            links.extend(html_links)
        
        # Extract from text content
        if text_content:
            text_links = self._extract_from_text(text_content)
            links.extend(text_links)
        
        # Filter for unsubscribe-related links
        unsubscribe_links = self.filter_unsubscribe_links(links)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(unsubscribe_links))
    
    def _extract_from_html(self, html_content: str) -> List[str]:
        """Extract links from HTML content."""
        links = []
        
        # Unwrap quoted-printable soft line breaks before parsing
        unwrapped_html = self._unwrap_quoted_printable_lines(html_content)
        
        try:
            soup = BeautifulSoup(unwrapped_html, 'html.parser')
            
            # Find all anchor tags with href
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                if href:
                    links.append(href)
            
            # Also extract mailto links from text
            text = soup.get_text()
            email_matches = EMAIL_PATTERN.findall(text)
            for email in email_matches:
                # Check if email appears in unsubscribe context
                email_context = self._get_email_context(text, email)
                if self._is_unsubscribe_context(email_context):
                    links.append(f"mailto:{email}")
                    
        except Exception:
            # If HTML parsing fails, fall back to regex
            links = self.url_pattern.findall(unwrapped_html)
        
        return links
    
    def _extract_from_text(self, text_content: str) -> List[str]:
        """Extract links from plain text content."""
        links = []
        
        # Unwrap quoted-printable soft line breaks before URL extraction
        unwrapped_text = self._unwrap_quoted_printable_lines(text_content)
        
        # Find all URLs
        url_matches = self.url_pattern.findall(unwrapped_text)
        links.extend(url_matches)
        
        # Find email addresses that might be unsubscribe addresses
        email_matches = EMAIL_PATTERN.findall(unwrapped_text)
        for email in email_matches:
            email_context = self._get_email_context(unwrapped_text, email)
            if self._is_unsubscribe_context(email_context):
                links.append(f"mailto:{email}")
        
        return links
    
    def _get_email_context(self, text: str, email: str) -> str:
        """Get surrounding context for an email address."""
        # Find the email in text and get surrounding words
        pattern = re.compile(rf'\b.{{0,50}}{re.escape(email)}.{{0,50}}\b', re.IGNORECASE)
        match = pattern.search(text)
        return match.group(0) if match else ""
    
    def _is_unsubscribe_context(self, context: str) -> bool:
        """Check if context indicates unsubscribe purpose."""
        context_lower = context.lower()
        return any(keyword in context_lower for keyword in self.unsubscribe_keywords)
    
    def extract_all_links(self, html_content: str) -> List[str]:
        """Extract all links from HTML content (for filtering)."""
        links = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                if href:
                    links.append(href)
        except Exception:
            links = self.url_pattern.findall(html_content)
        
        return links
    
    def filter_unsubscribe_links(self, links: List[str]) -> List[str]:
        """Filter links to only include unsubscribe-related ones."""
        unsubscribe_links = []
        
        for link in links:
            if self._is_unsubscribe_link(link):
                unsubscribe_links.append(link)
        
        return unsubscribe_links
    
    def _is_unsubscribe_link(self, link: str) -> bool:
        """Check if a link appears to be unsubscribe-related."""
        link_lower = link.lower()
        
        # Check URL path and parameters for unsubscribe keywords
        for keyword in self.unsubscribe_keywords:
            if keyword.replace(' ', '') in link_lower or keyword.replace(' ', '-') in link_lower:
                return True
        
        # Check for common unsubscribe parameter names
        unsubscribe_params = ['unsub', 'remove', 'optout', 'preferences', 'manage']
        parsed = urllib.parse.urlparse(link)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        for param in query_params:
            if any(unsub_param in param.lower() for unsub_param in unsubscribe_params):
                return True
        
        return False
    
    def extract_all_unsubscribe_methods(self, headers: Dict[str, str], 
                                      html_content: Optional[str], 
                                      text_content: Optional[str]) -> List[str]:
        """Extract all unsubscribe methods from an email."""
        all_links = []
        
        # Extract from headers
        header_links = self.extract_from_headers(headers)
        all_links.extend(header_links)
        
        # Extract from body
        body_links = self.extract_from_body(html_content, text_content)
        all_links.extend(body_links)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(all_links))
    
    def analyze_link_method(self, link: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Analyze a link to determine its unsubscribe method."""
        # Check for one-click capability
        if 'List-Unsubscribe-Post' in headers:
            post_header = headers['List-Unsubscribe-Post']
            if 'List-Unsubscribe=One-Click' in post_header and link in headers.get('List-Unsubscribe', ''):
                return {
                    'method': 'one_click',
                    'url': link,
                    'one_click_capable': True,
                    'post_data': post_header
                }
        
        # Default classification based on URL
        if link.startswith('mailto:'):
            return {'method': 'email_reply', 'url': link}
        else:
            return {'method': 'http_get', 'url': link}