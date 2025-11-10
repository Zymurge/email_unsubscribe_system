"""
Constants and shared configuration for unsubscribe functionality.

This module contains all shared patterns, keywords, and configuration
used across the unsubscribe extraction and processing pipeline.
"""

import re
from typing import List, Pattern

# Unsubscribe keywords for link detection
UNSUBSCRIBE_KEYWORDS: List[str] = [
    'unsubscribe', 'opt-out', 'opt out', 'optout',
    'remove', 'remove me', 'stop emails', 'stop sending',
    'manage preferences', 'email preferences', 'preferences',
    'subscription', 'manage subscription', 'manage'
]

# Suspicious patterns that indicate potential malicious links
SUSPICIOUS_PATTERNS: List[str] = [
    'download', 'exe', 'zip', 'dmg', 'install',
    'delete', 'destroy', 'remove-account', 'cancel-account',
    'confirm', 'verify-deletion', 'permanent',
    'javascript:', 'data:', 'vbscript:'
]

# URL shorteners that could hide malicious destinations
URL_SHORTENERS: List[str] = [
    'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly',
    's.id', 'j.mp', 'buff.ly', 'dlvr.it'
]

# Suspicious parameter names in URLs
SUSPICIOUS_PARAMS: List[str] = [
    'cmd', 'command', 'exec', 'delete', 'destroy',
    'action', 'do', 'operation'
]

# Pre-compiled regex patterns for performance
URL_PATTERN: Pattern = re.compile(
    r'https?://[^\s<>"\']+|mailto:[^\s<>"\']+',
    re.IGNORECASE
)

HEADER_URL_PATTERN: Pattern = re.compile(
    r'<([^>]+)>',
    re.IGNORECASE
)

# Form detection patterns
FORM_PATTERNS: List[Pattern] = [
    re.compile(r'<form[^>]*method=["\']?post["\']?[^>]*>', re.IGNORECASE),
    re.compile(r'<input[^>]*type=["\']?submit["\']?[^>]*>', re.IGNORECASE),
    re.compile(r'<button[^>]*type=["\']?submit["\']?[^>]*>', re.IGNORECASE)
]

# Email address pattern for mailto detection
EMAIL_PATTERN: Pattern = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Method classification constants
METHOD_GET = "http_get"
METHOD_POST = "http_post"
METHOD_EMAIL = "email_reply"
METHOD_ONE_CLICK = "one_click"

# Confidence scores for method classification
CONFIDENCE_HIGH = 1.0
CONFIDENCE_MEDIUM = 0.8
CONFIDENCE_LOW = 0.6

# Safety validation thresholds
SAFETY_SCORE_THRESHOLD = 0.8
REQUIRE_HTTPS = True