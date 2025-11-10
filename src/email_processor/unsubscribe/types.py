"""
Type-safe dataclasses for unsubscribe processing results.

This module provides structured, immutable dataclasses to replace
Dict returns throughout the unsubscribe processing pipeline.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass(frozen=True)
class UnsubscribeMethodResult:
    """Type-safe result for unsubscribe method classification."""
    
    method: str
    url: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error: Optional[str] = None
    
    def is_high_confidence(self) -> bool:
        """Check if result has high confidence (>= 0.8)."""
        return self.confidence >= 0.8
    
    def has_error(self) -> bool:
        """Check if result contains an error."""
        return self.error is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        result = {
            'method': self.method,
            'confidence': self.confidence,
            'is_valid': self.is_valid
        }
        
        if self.url:
            result['url'] = self.url
        if self.error:
            result['error'] = self.error
        if self.metadata:
            result['metadata'] = self.metadata
            result.update(self.metadata)
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnsubscribeMethodResult':
        """Create from dictionary for compatibility with existing code."""
        # Map action_url to url for compatibility
        url = data.get('url') or data.get('action_url')
        
        # Extract form_data and other metadata
        metadata = {}
        for key, value in data.items():
            if key not in ['method', 'url', 'action_url', 'confidence', 'is_valid', 'error']:
                metadata[key] = value
        
        return cls(
            method=data.get('method', 'unknown'),
            url=url,
            confidence=data.get('confidence', 1.0),
            metadata=metadata,
            is_valid=data.get('is_valid', True),
            error=data.get('error')
        )


@dataclass(frozen=True)
class ValidationResult:
    """Type-safe result for URL safety validation."""
    
    is_safe: bool
    url: str
    warnings: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    
    @property
    def summary(self) -> str:
        """Human-readable summary of validation result."""
        if self.is_safe:
            return "URL is safe to use"
        else:
            warning_count = len(self.warnings)
            return f"URL has {warning_count} security warnings (risk score: {self.risk_score:.1f})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            'is_safe': self.is_safe,
            'url': self.url,
            'warnings': self.warnings,
            'warning': '; '.join(self.warnings) if self.warnings else None,
            'risk_score': self.risk_score
        }


@dataclass(frozen=True)
class ProcessingResult:
    """Type-safe result for complete unsubscribe processing pipeline."""
    
    success: bool
    methods: List[UnsubscribeMethodResult] = field(default_factory=list)
    primary_method: Optional[UnsubscribeMethodResult] = None
    total_methods: int = 0
    processing_time: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            'success': self.success,
            'methods': [method.to_dict() for method in self.methods],
            'primary_method': self.primary_method.to_dict() if self.primary_method else None,
            'total_methods': self.total_methods,
            'processing_time': self.processing_time,
            'error': self.error
        }