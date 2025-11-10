"""
Unsubscribe extraction and processing module.

This module provides comprehensive unsubscribe functionality including:
- Link extraction from email headers and body content
- Method classification (GET, POST, email reply, one-click)
- Safety validation of unsubscribe URLs
- Processing pipeline for complete unsubscribe workflow
"""

from .extractors import UnsubscribeLinkExtractor
from .classifiers import UnsubscribeMethodClassifier
from .validators import UnsubscribeSafetyValidator
from .processors import (
    UnsubscribeProcessor, UnsubscribeMethodUpdater, 
    UnsubscribeMethodConflictResolver
)

__all__ = [
    'UnsubscribeLinkExtractor',
    'UnsubscribeMethodClassifier', 
    'UnsubscribeSafetyValidator',
    'UnsubscribeProcessor',
    'UnsubscribeMethodUpdater',
    'UnsubscribeMethodConflictResolver'
]