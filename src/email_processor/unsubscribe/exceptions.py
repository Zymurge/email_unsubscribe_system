"""
Custom exceptions for unsubscribe processing with enhanced error context.

This module provides structured exception classes that carry context
information for better debugging and error handling.
"""

from typing import Dict, Any, Optional


class UnsubscribeExtractionError(Exception):
    """Exception raised when unsubscribe link extraction fails."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context
    
    def __str__(self) -> str:
        base_message = super().__str__()
        if self.context is not None and self.context:
            context_info = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{base_message} (context: {context_info})"
        return base_message


class ValidationError(Exception):
    """Exception raised when URL validation fails."""
    
    def __init__(self, message: str, url: Optional[str] = None, risk_score: Optional[float] = None):
        super().__init__(message)
        self.url = url
        self.risk_score = risk_score
    
    def __str__(self) -> str:
        base_message = super().__str__()
        details = []
        if self.url:
            details.append(f"url={self.url}")
        if self.risk_score is not None:
            details.append(f"risk_score={self.risk_score}")
        
        if details:
            return f"{base_message} ({', '.join(details)})"
        return base_message


class ProcessingError(Exception):
    """Exception raised when unsubscribe processing pipeline fails."""
    
    def __init__(self, message: str, stage: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.stage = stage
        self.details = details or {}
    
    def __str__(self) -> str:
        base_message = super().__str__()
        context_parts = []
        
        if self.stage:
            context_parts.append(f"stage={self.stage}")
        
        if self.details:
            detail_strs = [f"{k}={v}" for k, v in self.details.items()]
            context_parts.extend(detail_strs)
        
        if context_parts:
            return f"{base_message} ({', '.join(context_parts)})"
        return base_message