"""
Unsubscribe link extraction and method classification for Phase 3.

This module handles:
- Extracting unsubscribe links from email headers and body content
- Classifying unsubscribe methods (GET, POST, email reply, one-click)
- Safety validation of unsubscribe links
- Processing multiple methods per subscription with "most recent email wins" rule
"""

import re
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from ..database.models import Subscription


class UnsubscribeLinkExtractor:
    """Extract unsubscribe links from email headers and body content."""
    
    def __init__(self):
        # Keywords that indicate unsubscribe-related links
        self.unsubscribe_keywords = [
            'unsubscribe', 'opt-out', 'opt out', 'optout',
            'remove', 'remove me', 'stop emails', 'stop sending',
            'manage preferences', 'email preferences', 'preferences',
            'subscription', 'manage subscription', 'manage'
        ]
        
        # Compile regex patterns for efficiency
        self.url_pattern = re.compile(
            r'https?://[^\s<>"\']+|mailto:[^\s<>"\']+',
            re.IGNORECASE
        )
        
        self.header_url_pattern = re.compile(
            r'<([^>]+)>',
            re.IGNORECASE
        )
    
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
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all anchor tags with href
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                if href:
                    links.append(href)
            
            # Also extract mailto links from text
            text = soup.get_text()
            email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            for email in email_matches:
                # Check if email appears in unsubscribe context
                email_context = self._get_email_context(text, email)
                if self._is_unsubscribe_context(email_context):
                    links.append(f"mailto:{email}")
                    
        except Exception:
            # If HTML parsing fails, fall back to regex
            links = self.url_pattern.findall(html_content)
        
        return links
    
    def _extract_from_text(self, text_content: str) -> List[str]:
        """Extract links from plain text content."""
        links = []
        
        # Find all URLs
        url_matches = self.url_pattern.findall(text_content)
        links.extend(url_matches)
        
        # Find email addresses that might be unsubscribe addresses
        email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
        for email in email_matches:
            email_context = self._get_email_context(text_content, email)
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


class UnsubscribeMethodClassifier:
    """Classify unsubscribe methods and extract parameters."""
    
    def classify_method(self, url: str, headers: Optional[Dict[str, str]] = None, 
                       form_context: Optional[str] = None) -> Dict[str, Any]:
        """Classify an unsubscribe method and extract relevant parameters."""
        
        # Validate URL first
        if not url or not self._is_valid_url(url):
            return {
                'method': 'invalid',
                'url': url,
                'error': 'Invalid or malformed URL'
            }
        
        # Check for one-click method (RFC 8058)
        if headers and self._is_one_click_method(url, headers):
            return self._classify_one_click(url, headers)
        
        # Check for email reply method
        if url.startswith('mailto:'):
            return self._classify_email_reply(url)
        
        # Check for HTTP POST method (requires form context)
        if form_context and self._has_post_form(url, form_context):
            return self._classify_http_post(url, form_context)
        
        # Default to HTTP GET
        return self._classify_http_get(url)
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and complete."""
        if not url or not url.strip():
            return False
        
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Check for basic URL structure
            if url.startswith('mailto:'):
                return '@' in url and '.' in url
            elif url.startswith(('http://', 'https://')):
                # Must have scheme, netloc, and a valid domain with TLD
                if not (parsed.netloc and parsed.scheme):
                    return False
                # Check for valid domain (must have at least one dot for TLD)
                if '.' not in parsed.netloc:
                    return False
                # Check that it's not incomplete like "http://"
                if parsed.netloc == "":
                    return False
                return True
            else:
                # If it doesn't start with recognized schemes, it's invalid
                return False
                
        except Exception:
            return False
    
    def _is_one_click_method(self, url: str, headers: Dict[str, str]) -> bool:
        """Check if URL supports one-click unsubscribe (RFC 8058)."""
        list_unsubscribe = headers.get('List-Unsubscribe', '')
        list_unsubscribe_post = headers.get('List-Unsubscribe-Post', '')
        
        return (url in list_unsubscribe and 
                'List-Unsubscribe=One-Click' in list_unsubscribe_post)
    
    def _classify_one_click(self, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Classify one-click unsubscribe method."""
        return {
            'method': 'one_click',
            'url': url,
            'one_click_capable': True,
            'post_data': 'List-Unsubscribe=One-Click'
        }
    
    def _classify_email_reply(self, url: str) -> Dict[str, Any]:
        """Classify email reply unsubscribe method."""
        try:
            parsed = urllib.parse.urlparse(url)
            email_address = parsed.path
            
            # Parse query parameters for subject and body
            query_params = urllib.parse.parse_qs(parsed.query)
            subject = query_params.get('subject', [''])[0]
            body = query_params.get('body', [''])[0]
            
            # URL decode
            subject = urllib.parse.unquote_plus(subject) if subject else ''
            body = urllib.parse.unquote_plus(body) if body else ''
            
            return {
                'method': 'email_reply',
                'email_address': email_address,
                'subject': subject,
                'body': body
            }
            
        except Exception as e:
            return {
                'method': 'invalid',
                'url': url,
                'error': f'Failed to parse mailto URL: {e}'
            }
    
    def _has_post_form(self, url: str, form_context: str) -> bool:
        """Check if URL has associated POST form."""
        try:
            soup = BeautifulSoup(form_context, 'html.parser')
            forms = soup.find_all('form')
            
            for form in forms:
                method = form.get('method', 'get').lower()
                action = form.get('action', '')
                
                if method == 'post' and (action == url or action in url or url in action):
                    return True
                    
            return False
            
        except Exception:
            return False
    
    def _classify_http_post(self, url: str, form_context: str) -> Dict[str, Any]:
        """Classify HTTP POST unsubscribe method."""
        try:
            soup = BeautifulSoup(form_context, 'html.parser')
            forms = soup.find_all('form')
            
            for form in forms:
                method = form.get('method', 'get').lower()
                action = form.get('action', '')
                
                if method == 'post' and (action == url or action in url or url in action):
                    # Extract form data
                    form_data = {}
                    for input_tag in form.find_all('input'):
                        input_name = input_tag.get('name')
                        input_value = input_tag.get('value', '')
                        if input_name:
                            form_data[input_name] = input_value
                    
                    # Also extract URL parameters (for complex scenarios)
                    url_parameters = {}
                    try:
                        parsed = urllib.parse.urlparse(action or url)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        for key, values in query_params.items():
                            url_parameters[key] = values[0] if values else ''
                    except Exception:
                        pass
                    
                    return {
                        'method': 'http_post',
                        'action_url': action or url,
                        'form_data': form_data,
                        'url_parameters': url_parameters
                    }
            
            # Fallback to GET if no matching form found
            return self._classify_http_get(url)
            
        except Exception:
            return self._classify_http_get(url)
    
    def _classify_http_get(self, url: str) -> Dict[str, Any]:
        """Classify HTTP GET unsubscribe method."""
        try:
            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            
            # Convert query params to simple dict
            parameters = {}
            for key, values in query_params.items():
                parameters[key] = values[0] if values else ''
            
            return {
                'method': 'http_get',
                'url': url,
                'parameters': parameters
            }
            
        except Exception as e:
            return {
                'method': 'invalid',
                'url': url,
                'error': f'Failed to parse URL: {e}'
            }
    
    def analyze_form_method(self, url: str, html_form: str) -> Dict[str, Any]:
        """Analyze HTML form for POST method details."""
        return self._classify_http_post(url, html_form)


class UnsubscribeSafetyValidator:
    """Validate unsubscribe links for safety and security."""
    
    def __init__(self):
        # Suspicious patterns that indicate potential malicious links
        self.suspicious_patterns = [
            'download', 'exe', 'zip', 'dmg', 'install',
            'delete', 'destroy', 'remove-account', 'cancel-account',
            'confirm', 'verify-deletion', 'permanent',
            'javascript:', 'data:', 'vbscript:'
        ]
        
        # URL shorteners that could hide malicious destinations
        self.url_shorteners = [
            'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly',
            's.id', 'j.mp', 'buff.ly', 'dlvr.it'
        ]
        
        # Suspicious parameter names
        self.suspicious_params = [
            'cmd', 'command', 'exec', 'delete', 'destroy',
            'action', 'do', 'operation'
        ]
    
    def validate_safety(self, url: str) -> Dict[str, Any]:
        """Validate URL safety for unsubscribe operations."""
        warnings = []
        is_safe = True
        
        # Check HTTPS requirement
        if not url.startswith('https://') and not url.startswith('mailto:'):
            warnings.append('Insecure connection - HTTP instead of HTTPS')
            is_safe = False
        
        # Check for suspicious patterns
        url_lower = url.lower()
        for pattern in self.suspicious_patterns:
            if pattern in url_lower:
                warnings.append(f'Suspicious pattern detected: {pattern}')
                is_safe = False
        
        # Check for URL shorteners (exact domain match)
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower()
        if domain in self.url_shorteners or any(domain.endswith('.' + shortener) for shortener in self.url_shorteners):
            warnings.append('URL shortener detected - potential security risk')
            is_safe = False
        
        # Check for suspicious parameters
        if self._has_suspicious_parameters(url):
            warnings.append('Suspicious parameters detected')
            is_safe = False
        
        # Check URL structure
        if not self._is_well_formed_url(url):
            warnings.append('Malformed or incomplete URL')
            is_safe = False
        
        return {
            'is_safe': is_safe,
            'warnings': warnings,
            'warning': '; '.join(warnings) if warnings else None
        }
    
    def is_safe_domain(self, url: str) -> bool:
        """Check if domain is considered safe (legacy method - now always checks patterns)."""
        result = self.validate_safety(url)
        return result['is_safe']
    
    def _has_suspicious_parameters(self, url: str) -> bool:
        """Check for suspicious URL parameters."""
        try:
            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            
            for param_name in query_params:
                param_lower = param_name.lower()
                if any(suspicious in param_lower for suspicious in self.suspicious_params):
                    return True
                    
                # Check parameter values too
                for value in query_params[param_name]:
                    value_lower = value.lower()
                    if any(suspicious in value_lower for suspicious in ['delete', 'destroy', 'remove']):
                        return True
            
            return False
            
        except Exception:
            return True  # Assume suspicious if can't parse
    
    def _is_well_formed_url(self, url: str) -> bool:
        """Check if URL is well-formed."""
        if not url:
            return False
        
        try:
            parsed = urllib.parse.urlparse(url)
            
            if url.startswith('mailto:'):
                return '@' in url and '.' in url.split('@')[1]
            elif url.startswith(('http://', 'https://')):
                return bool(parsed.netloc and parsed.scheme and '.' in parsed.netloc)
            else:
                return False
                
        except Exception:
            return False


class UnsubscribeProcessor:
    """Main processor for handling complete unsubscribe extraction pipeline."""
    
    def __init__(self):
        self.extractor = UnsubscribeLinkExtractor()
        self.classifier = UnsubscribeMethodClassifier()
        self.validator = UnsubscribeSafetyValidator()
        
        # Method priority for single email (higher number = higher priority)
        self.method_priority = {
            'one_click': 4,
            'http_post': 3,
            'http_get': 2,
            'email_reply': 1,
            'invalid': 0
        }
    
    def process_email_for_unsubscribe_methods(self, headers: Dict[str, str], 
                                            html_content: Optional[str], 
                                            text_content: Optional[str]) -> Dict[str, Any]:
        """Process an email to extract and classify all unsubscribe methods."""
        
        # Extract all unsubscribe links
        all_links = self.extractor.extract_all_unsubscribe_methods(headers, html_content, text_content)
        
        if not all_links:
            return {
                'methods': [],
                'primary_method': None,
                'total_methods': 0
            }
        
        # Also look for form-based unsubscribe methods in HTML
        if html_content:
            form_methods = self._extract_form_methods(html_content)
            all_links.extend(form_methods)
        
        # Remove duplicates while preserving order
        all_links = list(dict.fromkeys(all_links))
        
        # Classify each method and validate safety
        methods = []
        for link in all_links:
            # Classify the method
            method_info = self.classifier.classify_method(link, headers, html_content)
            
            # Validate safety
            safety_check = self.validator.validate_safety(link)
            method_info['safety_check'] = safety_check
            
            methods.append(method_info)
        
        # Determine primary method based on priority
        primary_method = self._get_primary_method(methods)
        
        return {
            'methods': methods,
            'primary_method': primary_method,
            'total_methods': len(methods)
        }
    
    def _get_primary_method(self, methods: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get the primary (highest priority) method from a list."""
        if not methods:
            return None
        
        # Sort by priority (highest first)
        sorted_methods = sorted(
            methods, 
            key=lambda m: self.method_priority.get(m['method'], 0),
            reverse=True
        )
        
        return sorted_methods[0]
    
    def _extract_form_methods(self, html_content: str) -> List[str]:
        """Extract form action URLs that might be unsubscribe methods."""
        form_urls = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            forms = soup.find_all('form')
            
            for form in forms:
                action = form.get('action', '')
                if action and self.extractor._is_unsubscribe_link(action):
                    form_urls.append(action)
                    
        except Exception:
            pass
            
        return form_urls
    
    def get_unsubscribe_candidates(self, account_id: int, session: Session) -> List[Subscription]:
        """Get subscriptions eligible for unsubscribe processing."""
        return session.query(Subscription).filter(
            Subscription.account_id == account_id,
            Subscription.keep_subscription == False,  # Not marked to keep
            Subscription.unsubscribe_status != 'unsubscribed'  # Not already unsubscribed
        ).all()
    
    def update_subscription_unsubscribe_info(self, subscription_id: int, 
                                           headers: Dict[str, str],
                                           html_content: Optional[str], 
                                           text_content: Optional[str],
                                           session: Session,
                                           email_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Update subscription with unsubscribe information from email."""
        
        subscription = session.query(Subscription).get(subscription_id)
        if not subscription:
            return {'error': 'Subscription not found'}
        
        # Skip if marked to keep
        if subscription.should_skip_unsubscribe():
            return {'skipped': True, 'reason': 'subscription_marked_to_keep_or_already_unsubscribed'}
        
        # Process email for unsubscribe methods
        result = self.process_email_for_unsubscribe_methods(headers, html_content, text_content)
        
        if not result['methods']:
            return {'updated': False, 'reason': 'no_unsubscribe_methods_found'}
        
        # Use primary method to update subscription
        primary_method = result['primary_method']
        if primary_method and primary_method['safety_check']['is_safe']:
            # Update subscription with most recent method (most recent email wins rule)
            subscription.unsubscribe_link = primary_method.get('url', primary_method.get('action_url'))
            subscription.unsubscribe_method = primary_method['method']
            subscription.updated_at = datetime.now()
            
            session.commit()
            
            return {
                'updated': True,
                'method': primary_method['method'],
                'link': subscription.unsubscribe_link,
                'email_date': email_date
            }
        
        return {'updated': False, 'reason': 'unsafe_or_invalid_method'}


class UnsubscribeMethodConflictResolver:
    """Handle conflicts when multiple emails have different unsubscribe methods."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def update_subscription_methods(self, subscription_id: int, 
                                  methods: List[Dict[str, Any]], 
                                  email_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Update subscription methods following 'most recent email wins' rule."""
        
        subscription = self.session.query(Subscription).get(subscription_id)
        if not subscription:
            return {'error': 'Subscription not found'}
        
        if not methods:
            return {'updated': False, 'reason': 'no_methods_provided'}
        
        # Get the primary method (highest priority within this email)
        processor = UnsubscribeProcessor()
        primary_method = processor._get_primary_method(methods)
        
        if primary_method:
            # Update with most recent method (this email's method wins)
            subscription.unsubscribe_link = primary_method.get('url', primary_method.get('action_url'))
            subscription.unsubscribe_method = primary_method['method']
            subscription.updated_at = email_date or datetime.now()
            
            self.session.commit()
            
            return {
                'updated': True,
                'method': primary_method['method'],
                'email_date': email_date
            }
        
        return {'updated': False, 'reason': 'no_valid_methods'}
    
    def get_method_history(self, subscription_id: int) -> List[Dict[str, Any]]:
        """Get method change history for a subscription (placeholder for future implementation)."""
        # This would require a separate history table in a full implementation
        # For now, return current method only
        subscription = self.session.query(Subscription).get(subscription_id)
        if subscription:
            return [{
                'method': subscription.unsubscribe_method,
                'link': subscription.unsubscribe_link,
                'updated_at': subscription.updated_at
            }]
        return []


class UnsubscribeMethodUpdater:
    """Update subscription methods when better methods are found."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def update_if_better(self, subscription_id: int, new_method: Dict[str, Any]) -> Dict[str, Any]:
        """Update subscription if new method is from more recent email (most recent wins rule)."""
        
        subscription = self.session.query(Subscription).get(subscription_id)
        if not subscription:
            return {'error': 'Subscription not found'}
        
        # In "most recent email wins" rule, we always update with the new method
        # since it represents a more recent email
        subscription.unsubscribe_link = new_method.get('url', new_method.get('action_url'))
        subscription.unsubscribe_method = new_method['method']
        subscription.updated_at = datetime.now()
        
        self.session.commit()
        
        return {
            'updated': True,
            'reason': 'most_recent_email_wins',
            'new_method': new_method['method']
        }