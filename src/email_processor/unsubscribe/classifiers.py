"""
Unsubscribe method classification and parameter extraction.

This module handles classifying unsubscribe methods and extracting
relevant parameters for different types of unsubscribe actions:
- HTTP GET requests
- HTTP POST requests  
- Email replies
- One-click unsubscribe (RFC 8058)
"""

import urllib.parse
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

from .constants import (
    METHOD_GET, METHOD_POST, METHOD_EMAIL, METHOD_ONE_CLICK,
    CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW
)


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
            'method': METHOD_ONE_CLICK,
            'url': url,
            'one_click_capable': True,
            'post_data': 'List-Unsubscribe=One-Click',
            'confidence': CONFIDENCE_HIGH
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
                'method': METHOD_EMAIL,
                'email_address': email_address,
                'subject': subject,
                'body': body,
                'confidence': CONFIDENCE_HIGH
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
                        'method': METHOD_POST,
                        'action_url': action or url,
                        'form_data': form_data,
                        'url_parameters': url_parameters,
                        'confidence': CONFIDENCE_HIGH
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
                'method': METHOD_GET,
                'url': url,
                'parameters': parameters,
                'confidence': CONFIDENCE_MEDIUM
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