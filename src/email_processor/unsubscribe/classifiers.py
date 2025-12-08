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
from .logging import UnsubscribeLogger


class UnsubscribeMethodClassifier:
    """Classify unsubscribe methods and extract parameters."""
    
    def __init__(self):
        self.logger = UnsubscribeLogger("method_classifier")
    
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
                    
                    # Analyze form complexity
                    complexity_analysis = self._analyze_form_complexity(form_context)
                    
                    result = {
                        'method': METHOD_POST,
                        'action_url': action or url,
                        'form_data': form_data,
                        'url_parameters': url_parameters,
                        'confidence': CONFIDENCE_HIGH,
                        'form_complexity': complexity_analysis
                    }
                    
                    # Log if manual intervention is required
                    if complexity_analysis['requires_manual_intervention']:
                        self.logger.info("Complex form detected requiring manual intervention", {
                            'url': url,
                            'complexity_reason': complexity_analysis['complexity_reason'],
                            'method': 'http_post',
                            'action_url': action or url
                        })
                    
                    return result
            
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
    
    def _analyze_form_complexity(self, form_html: str) -> Dict[str, Any]:
        """Analyze if form requires user interaction beyond simple submission."""
        try:
            soup = BeautifulSoup(form_html, 'html.parser')
            
            # Find all forms in the HTML
            forms = soup.find_all('form')
            if not forms:
                return {'requires_manual_intervention': False, 'complexity_reason': 'no_forms_found'}
            
            # Analyze the first form (most common case)
            form = forms[0]
            
            complexity_indicators = {
                'has_checkboxes': len(form.find_all('input', {'type': 'checkbox'})) > 0,
                'has_radio_buttons': len(form.find_all('input', {'type': 'radio'})) > 0,
                'has_select_dropdowns': len(form.find_all('select')) > 0,
                'has_multiple_select_options': False,
                'has_user_choice_text': False,
                'requires_manual_intervention': False,
                'complexity_reason': 'simple_form'
            }
            
            # Check for select dropdowns with multiple options
            selects = form.find_all('select')
            for select in selects:
                options = select.find_all('option')
                if len(options) > 2:  # More than just "yes/no" or "unsubscribe/keep"
                    complexity_indicators['has_multiple_select_options'] = True
                    break
            
            # Check for text that indicates user choice is required
            choice_indicators = [
                'select which', 'choose', 'pick', 'which of the following',
                'continue receiving', 'stop receiving', 'manage preferences',
                'customize', 'personalize', 'subscription preferences'
            ]
            
            form_text = form.get_text().lower()
            for indicator in choice_indicators:
                if indicator in form_text:
                    complexity_indicators['has_user_choice_text'] = True
                    break
            
            # Determine if manual intervention is required
            complexity_indicators['requires_manual_intervention'] = any([
                complexity_indicators['has_checkboxes'],
                complexity_indicators['has_radio_buttons'],
                complexity_indicators['has_select_dropdowns'] and complexity_indicators['has_multiple_select_options'],
                complexity_indicators['has_user_choice_text']
            ])
            
            # Set complexity reason
            if complexity_indicators['requires_manual_intervention']:
                reasons = []
                if complexity_indicators['has_checkboxes']:
                    reasons.append('checkboxes')
                if complexity_indicators['has_radio_buttons']:
                    reasons.append('radio_buttons')
                if complexity_indicators['has_select_dropdowns'] and complexity_indicators['has_multiple_select_options']:
                    reasons.append('multiple_choice_dropdowns')
                if complexity_indicators['has_user_choice_text']:
                    reasons.append('user_choice_required')
                complexity_indicators['complexity_reason'] = ', '.join(reasons)
            
            return complexity_indicators
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze form complexity: {e}")
            return {
                'requires_manual_intervention': False,
                'complexity_reason': f'analysis_failed: {e}'
            }