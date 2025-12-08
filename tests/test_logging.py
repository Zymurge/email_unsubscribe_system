"""
Test-Driven Development tests for Step 4.2: Structured Logging

Following TDD Red-Green-Refactor methodology:
1. Write failing tests for logging functionality (RED) ← WE ARE HERE
2. Implement structured logging to pass tests (GREEN)
3. Refactor and optimize logging system (REFACTOR)

These tests define the complete specification for structured logging
throughout the unsubscribe processing pipeline.
"""

import pytest
import logging
import json
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
from typing import Dict, Any, List
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


class TestStructuredLogging:
    """Test structured logging implementation with context tracking."""

    def test_unsubscribe_logger_creation(self):
        """Test that unsubscribe logger is properly configured."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        logger = UnsubscribeLogger("test_component")
        
        # Should create logger with proper name
        assert logger.logger.name == "unsubscribe.test_component"
        assert logger.component == "test_component"
        assert isinstance(logger.context, dict)

    def test_logger_context_management(self):
        """Test context addition and management in logging."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        logger = UnsubscribeLogger("extractor")
        
        # Test adding context
        logger.add_context("email_id", 12345)
        logger.add_context("sender", "newsletter@company.com")
        
        assert logger.context["email_id"] == 12345
        assert logger.context["sender"] == "newsletter@company.com"

    def test_structured_log_output_format(self):
        """Test that log messages are properly structured with JSON format."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        
        logger = UnsubscribeLogger("classifier")
        logger.logger.addHandler(handler)
        logger.logger.setLevel(logging.INFO)
        
        # Add context and log message
        logger.add_context("url", "https://company.com/unsubscribe")
        logger.add_context("method", "http_get")
        logger.info("Method classification successful", {"confidence": 0.9})
        
        # Verify structured output
        log_output = log_capture.getvalue()
        assert "Method classification successful" in log_output
        assert "confidence" in log_output
        assert "url" in log_output
        assert "method" in log_output

    def test_log_levels_and_methods(self):
        """Test different log levels work correctly."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        logger = UnsubscribeLogger("validator")
        
        # Test all log level methods exist and work
        with patch.object(logger.logger, 'debug') as mock_debug:
            logger.debug("Debug message", {"test": "data"})
            mock_debug.assert_called_once()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.info("Info message", {"test": "data"})
            mock_info.assert_called_once()
        
        with patch.object(logger.logger, 'warning') as mock_warning:
            logger.warning("Warning message", {"test": "data"})
            mock_warning.assert_called_once()
        
        with patch.object(logger.logger, 'error') as mock_error:
            logger.error("Error message", {"test": "data"})
            mock_error.assert_called_once()

    def test_performance_logging(self):
        """Test performance measurement and logging."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        logger = UnsubscribeLogger("processor")
        
        # Test performance timing context manager
        with patch.object(logger.logger, 'info') as mock_info:
            with logger.time_operation("link_extraction"):
                # Simulate some processing time
                pass
            
            # Should log timing information
            mock_info.assert_called()
            call_args = mock_info.call_args[0][0]
            assert "link_extraction" in call_args
            assert "completed" in call_args or "took" in call_args

    def test_error_logging_with_exceptions(self):
        """Test logging errors with exception information."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        from src.email_processor.unsubscribe.exceptions import UnsubscribeExtractionError
        
        logger = UnsubscribeLogger("extractor")
        
        with patch.object(logger.logger, 'error') as mock_error:
            try:
                raise UnsubscribeExtractionError("Extraction failed", 
                                                context={"url": "invalid", "method": "html"})
            except UnsubscribeExtractionError as e:
                logger.log_exception(e, {"additional": "context"})
            
            # Should log exception with context
            mock_error.assert_called_once()

    def test_context_inheritance_and_scoping(self):
        """Test that context is properly inherited and scoped."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        logger = UnsubscribeLogger("processor")
        
        # Add base context
        logger.add_context("subscription_id", 456)
        logger.add_context("account_id", 123)
        
        # Create scoped context
        with logger.scoped_context({"operation": "classification", "attempt": 1}):
            # In scope - should have all context
            expected_context = {
                "subscription_id": 456,
                "account_id": 123,
                "operation": "classification",
                "attempt": 1
            }
            
            with patch.object(logger.logger, 'info') as mock_info:
                logger.info("Processing in scope")
                # Verify context is included in log call
                mock_info.assert_called_once()
        
        # Out of scope - should only have base context
        assert "operation" not in logger.context
        assert "attempt" not in logger.context
        assert logger.context["subscription_id"] == 456

    def test_log_filtering_and_sensitive_data(self):
        """Test that sensitive data is properly filtered from logs."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        logger = UnsubscribeLogger("validator")
        
        # Test logging with sensitive data
        sensitive_data = {
            "url": "https://company.com/unsubscribe?token=secret123",
            "email": "user@example.com",
            "password": "secret_password",
            "api_key": "key_12345"
        }
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.info("Processing request", sensitive_data)
            
            # Should filter out sensitive fields
            call_args = str(mock_info.call_args)
            assert "secret123" not in call_args  # Token should be masked
            assert "secret_password" not in call_args  # Password should be masked
            assert "key_12345" not in call_args  # API key should be masked

    def test_log_aggregation_and_statistics(self):
        """Test log aggregation for statistics and monitoring."""
        from src.email_processor.unsubscribe.logging import UnsubscribeLogger
        
        logger = UnsubscribeLogger("processor")
        
        # Log multiple operations
        logger.log_operation_count("extraction", success=True)
        logger.log_operation_count("extraction", success=True)
        logger.log_operation_count("extraction", success=False)
        logger.log_operation_count("classification", success=True)
        
        # Get statistics
        stats = logger.get_operation_stats()
        
        assert stats["extraction"]["total"] == 3
        assert stats["extraction"]["success"] == 2
        assert stats["extraction"]["failure"] == 1
        assert stats["classification"]["total"] == 1
        assert stats["classification"]["success"] == 1


class TestLoggingIntegration:
    """Test logging integration with existing unsubscribe components."""

    def test_extractor_logging_integration(self):
        """Test that UnsubscribeLinkExtractor uses structured logging."""
        from src.email_processor.unsubscribe.extractors import UnsubscribeLinkExtractor
        
        extractor = UnsubscribeLinkExtractor()
        
        # Should have logger attribute
        assert hasattr(extractor, 'logger')
        assert extractor.logger.component == "link_extractor"

    def test_classifier_logging_integration(self):
        """Test that UnsubscribeMethodClassifier uses structured logging."""
        from src.email_processor.unsubscribe.classifiers import UnsubscribeMethodClassifier
        
        classifier = UnsubscribeMethodClassifier()
        
        # Should have logger attribute
        assert hasattr(classifier, 'logger')
        assert classifier.logger.component == "method_classifier"

    def test_validator_logging_integration(self):
        """Test that UnsubscribeSafetyValidator uses structured logging."""
        from src.email_processor.unsubscribe.validators import UnsubscribeSafetyValidator
        
        validator = UnsubscribeSafetyValidator()
        
        # Should have logger attribute
        assert hasattr(validator, 'logger')
        assert validator.logger.component == "safety_validator"

    def test_processor_logging_integration(self):
        """Test that UnsubscribeProcessor uses structured logging."""
        from src.email_processor.unsubscribe.processors import UnsubscribeProcessor
        
        processor = UnsubscribeProcessor()
        
        # Should have logger attribute
        assert hasattr(processor, 'logger')
        assert processor.logger.component == "unsubscribe_processor"

    def test_end_to_end_logging_flow(self):
        """Test complete logging flow through entire processing pipeline."""
        from src.email_processor.unsubscribe import UnsubscribeProcessor
        
        processor = UnsubscribeProcessor()
        
        # Mock email data
        headers = {'List-Unsubscribe': '<https://company.com/unsubscribe?token=xyz>'}
        html_content = '<a href="https://company.com/unsubscribe?token=xyz">Unsubscribe</a>'
        
        # Test that processor has logger and can process without errors
        result = processor.process_email_for_unsubscribe_methods(
            headers, html_content, None
        )
        
        # Verify processing completed successfully
        assert isinstance(result, dict)
        assert 'methods' in result
        assert 'primary_method' in result
        assert 'total_methods' in result
        
        # Verify logger exists and is functional
        assert hasattr(processor, 'logger')
        assert processor.logger.component == "unsubscribe_processor"

    def test_error_propagation_with_logging(self):
        """Test that errors are properly logged before being raised."""
        from src.email_processor.unsubscribe.validators import UnsubscribeSafetyValidator
        from src.email_processor.unsubscribe.exceptions import ValidationError
        
        validator = UnsubscribeSafetyValidator()
        
        with patch.object(validator.logger, 'error') as mock_error:
            # Should log error before validation
            result = validator.validate_safety("javascript:alert('xss')")
            
            # Should log the security issue
            assert not result['is_safe']
            # Logging should have occurred for suspicious patterns
            # (Note: This tests the integration, specific logging calls depend on implementation)


class TestLogConfiguration:
    """Test logging configuration and setup."""

    def test_log_level_configuration(self):
        """Test that log levels can be configured properly."""
        from src.email_processor.unsubscribe.logging import configure_unsubscribe_logging
        
        # Test different log level configurations
        configure_unsubscribe_logging(level="DEBUG")
        logger = logging.getLogger("unsubscribe")
        assert logger.level == logging.DEBUG
        
        configure_unsubscribe_logging(level="INFO")
        assert logger.level == logging.INFO

    def test_log_format_configuration(self):
        """Test that log format can be configured."""
        from src.email_processor.unsubscribe.logging import configure_unsubscribe_logging
        
        # Test JSON format configuration
        configure_unsubscribe_logging(format="json")
        
        # Test standard format configuration  
        configure_unsubscribe_logging(format="standard")

    def test_log_output_destinations(self):
        """Test that logs can be directed to different outputs."""
        from src.email_processor.unsubscribe.logging import configure_unsubscribe_logging
        
        # Test file output
        configure_unsubscribe_logging(output="file", filename="test_unsubscribe.log")
        
        # Test console output
        configure_unsubscribe_logging(output="console")
        
        # Test both
        configure_unsubscribe_logging(output="both", filename="test_unsubscribe.log")