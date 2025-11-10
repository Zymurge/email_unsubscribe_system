"""
Test-Driven Development tests for Step 4: Type Safety & Validation

Following TDD Red-Green-Refactor methodology:
1. Write failing tests for dataclasses (RED) ← WE ARE HERE
2. Implement dataclasses to pass tests (GREEN)
3. Refactor for quality (REFACTOR)

These tests define the complete specification for Phase 3 type safety improvements.
"""

import pytest
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestUnsubscribeDataclasses:
    """Test dataclass implementations for type-safe returns."""

    def test_unsubscribe_method_result_structure(self):
        """Test UnsubscribeMethodResult dataclass structure and validation."""
        from src.email_processor.unsubscribe.types import UnsubscribeMethodResult
        
        # Test valid method result creation
        result = UnsubscribeMethodResult(
            method="http_get",
            url="https://company.com/unsubscribe?token=123",
            confidence=0.9,
            metadata={"source": "header"}
        )
        
        assert result.method == "http_get"
        assert result.url == "https://company.com/unsubscribe?token=123"
        assert result.confidence == 0.9
        assert result.metadata == {"source": "header"}
        assert result.is_valid is True
        assert result.error is None

    def test_unsubscribe_method_result_invalid_cases(self):
        """Test UnsubscribeMethodResult with invalid data."""
        from src.email_processor.unsubscribe.types import UnsubscribeMethodResult
        
        # Test invalid method result
        result = UnsubscribeMethodResult(
            method="invalid",
            url="malformed-url",
            confidence=0.0,
            is_valid=False,
            error="Invalid URL format"
        )
        
        assert result.method == "invalid"
        assert result.is_valid is False
        assert result.error == "Invalid URL format"
        assert result.confidence == 0.0

    def test_validation_result_structure(self):
        """Test ValidationResult dataclass for safety validation."""
        from src.email_processor.unsubscribe.types import ValidationResult
        
        # Test safe validation result
        result = ValidationResult(
            is_safe=True,
            url="https://company.com/unsubscribe",
            warnings=[],
            risk_score=0.1
        )
        
        assert result.is_safe is True
        assert result.url == "https://company.com/unsubscribe"
        assert result.warnings == []
        assert result.risk_score == 0.1
        assert result.summary == "URL is safe to use"

    def test_validation_result_with_warnings(self):
        """Test ValidationResult with safety warnings."""
        from src.email_processor.unsubscribe.types import ValidationResult
        
        # Test unsafe validation result
        warnings = ["HTTP instead of HTTPS", "Suspicious parameter detected"]
        result = ValidationResult(
            is_safe=False,
            url="http://suspicious.com/unsubscribe?cmd=delete",
            warnings=warnings,
            risk_score=0.8
        )
        
        assert result.is_safe is False
        assert result.warnings == warnings
        assert result.risk_score == 0.8
        assert "2 security warnings" in result.summary

    def test_processing_result_structure(self):
        """Test ProcessingResult dataclass for complete processing pipeline."""
        from src.email_processor.unsubscribe.types import ProcessingResult, UnsubscribeMethodResult
        
        # Create sample methods
        method1 = UnsubscribeMethodResult(
            method="one_click",
            url="https://company.com/unsubscribe",
            confidence=1.0
        )
        method2 = UnsubscribeMethodResult(
            method="http_get", 
            url="https://company.com/unsubscribe?token=123",
            confidence=0.8
        )
        
        # Test complete processing result
        result = ProcessingResult(
            success=True,
            methods=[method1, method2],
            primary_method=method1,
            total_methods=2,
            processing_time=0.15
        )
        
        assert result.success is True
        assert len(result.methods) == 2
        assert result.primary_method.method == "one_click"
        assert result.total_methods == 2
        assert result.processing_time == 0.15
        assert result.error is None

    def test_processing_result_failure_case(self):
        """Test ProcessingResult for failed processing."""
        from src.email_processor.unsubscribe.types import ProcessingResult
        
        # Test failed processing result
        result = ProcessingResult(
            success=False,
            methods=[],
            primary_method=None,
            total_methods=0,
            processing_time=0.05,
            error="No unsubscribe methods found"
        )
        
        assert result.success is False
        assert result.methods == []
        assert result.primary_method is None
        assert result.total_methods == 0
        assert result.error == "No unsubscribe methods found"

    def test_dataclass_immutability(self):
        """Test that dataclasses are frozen (immutable) for safety."""
        from src.email_processor.unsubscribe.types import UnsubscribeMethodResult
        
        result = UnsubscribeMethodResult(
            method="http_get",
            url="https://company.com/unsubscribe",
            confidence=0.9
        )
        
        # Should not be able to modify frozen dataclass
        with pytest.raises(AttributeError):
            result.method = "http_post"
        
        with pytest.raises(AttributeError):
            result.confidence = 0.5

    def test_dataclass_validation_methods(self):
        """Test validation methods on dataclasses."""
        from src.email_processor.unsubscribe.types import UnsubscribeMethodResult
        
        # Test valid result
        valid_result = UnsubscribeMethodResult(
            method="http_get",
            url="https://company.com/unsubscribe",
            confidence=0.9
        )
        
        assert valid_result.is_high_confidence() is True  # confidence >= 0.8
        assert valid_result.has_error() is False
        
        # Test low confidence result
        low_confidence_result = UnsubscribeMethodResult(
            method="http_get",
            url="https://company.com/unsubscribe",
            confidence=0.5
        )
        
        assert low_confidence_result.is_high_confidence() is False
        
        # Test error result
        error_result = UnsubscribeMethodResult(
            method="invalid",
            url="bad-url",
            confidence=0.0,
            is_valid=False,
            error="Invalid URL"
        )
        
        assert error_result.has_error() is True
        assert error_result.is_high_confidence() is False


class TestUnsubscribeExceptions:
    """Test custom exception classes for proper error handling."""

    def test_unsubscribe_extraction_error(self):
        """Test UnsubscribeExtractionError custom exception."""
        from src.email_processor.unsubscribe.exceptions import UnsubscribeExtractionError
        
        # Test basic exception
        with pytest.raises(UnsubscribeExtractionError) as exc_info:
            raise UnsubscribeExtractionError("Failed to extract unsubscribe links")
        
        assert str(exc_info.value) == "Failed to extract unsubscribe links"
        assert exc_info.value.context is None

    def test_unsubscribe_extraction_error_with_context(self):
        """Test UnsubscribeExtractionError with context information."""
        from src.email_processor.unsubscribe.exceptions import UnsubscribeExtractionError
        
        context = {
            "email_id": 123,
            "sender": "newsletter@company.com",
            "extraction_method": "html_parsing"
        }
        
        with pytest.raises(UnsubscribeExtractionError) as exc_info:
            raise UnsubscribeExtractionError("HTML parsing failed", context=context)
        
        assert "HTML parsing failed" in str(exc_info.value) 
        assert exc_info.value.context == context

    def test_validation_error(self):
        """Test ValidationError for safety validation failures."""
        from src.email_processor.unsubscribe.exceptions import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("URL failed security validation", 
                                url="http://suspicious.com",
                                risk_score=0.9)
        
        assert "URL failed security validation" in str(exc_info.value)
        assert exc_info.value.url == "http://suspicious.com"
        assert exc_info.value.risk_score == 0.9

    def test_processing_error(self):
        """Test ProcessingError for pipeline failures."""
        from src.email_processor.unsubscribe.exceptions import ProcessingError
        
        with pytest.raises(ProcessingError) as exc_info:
            raise ProcessingError("Pipeline processing failed", 
                                stage="classification",
                                details={"classifier": "method", "input": "invalid_url"})
        
        assert "Pipeline processing failed" in str(exc_info.value)
        assert exc_info.value.stage == "classification"
        assert exc_info.value.details["classifier"] == "method"


class TestBackwardCompatibility:
    """Test that new dataclasses maintain compatibility with existing Dict returns."""

    def test_dataclass_to_dict_conversion(self):
        """Test that dataclasses can be converted to dicts for backward compatibility."""
        from src.email_processor.unsubscribe.types import UnsubscribeMethodResult
        
        result = UnsubscribeMethodResult(
            method="http_get",
            url="https://company.com/unsubscribe",
            confidence=0.9,
            metadata={"source": "header"}
        )
        
        # Should be able to convert to dict
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict["method"] == "http_get"
        assert result_dict["url"] == "https://company.com/unsubscribe"
        assert result_dict["confidence"] == 0.9
        assert result_dict["metadata"] == {"source": "header"}

    def test_dataclass_from_dict_creation(self):
        """Test creating dataclasses from dict data for compatibility."""
        from src.email_processor.unsubscribe.types import UnsubscribeMethodResult
        
        data = {
            "method": "http_post",
            "action_url": "https://company.com/unsubscribe-form",
            "form_data": {"user_id": "123"},
            "confidence": 0.95
        }
        
        # Should be able to create from dict
        result = UnsubscribeMethodResult.from_dict(data)
        
        assert result.method == "http_post"
        assert result.url == "https://company.com/unsubscribe-form"  # action_url mapped to url
        assert result.confidence == 0.95
        assert result.metadata["form_data"] == {"user_id": "123"}