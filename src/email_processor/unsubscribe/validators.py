"""
Unsubscribe URL safety validation and security checks.

This module handles validating unsubscribe URLs for potential security risks:
- HTTPS requirement validation
- Suspicious pattern detection
- URL shortener identification  
- Parameter safety analysis
- URL structure validation
"""

import urllib.parse
from typing import Dict, Any

from .constants import (
    SUSPICIOUS_PATTERNS, URL_SHORTENERS, SUSPICIOUS_PARAMS,
    REQUIRE_HTTPS, SAFETY_SCORE_THRESHOLD
)


class UnsubscribeSafetyValidator:
    """Validate unsubscribe links for safety and security."""
    
    def __init__(self):
        # Use shared constants instead of instance variables
        self.suspicious_patterns = SUSPICIOUS_PATTERNS
        self.url_shorteners = URL_SHORTENERS
        self.suspicious_params = SUSPICIOUS_PARAMS
    
    def validate_safety(self, url: str) -> Dict[str, Any]:
        """Validate URL safety for unsubscribe operations."""
        warnings = []
        is_safe = True
        
        # Check HTTPS requirement
        if REQUIRE_HTTPS and not url.startswith('https://') and not url.startswith('mailto:'):
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