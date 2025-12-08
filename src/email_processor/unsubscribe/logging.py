"""
Structured logging system for unsubscribe processing pipeline.

This module provides structured logging with context tracking, performance
monitoring, sensitive data filtering, and statistics aggregation.
"""

import logging
import json
import time
import re
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from datetime import datetime, timezone
from collections import defaultdict


class SensitiveDataFilter:
    """Filter sensitive data from log messages."""
    
    def __init__(self):
        self.sensitive_patterns = [
            (re.compile(r'token=([^&\s]+)', re.IGNORECASE), 'token=***'),
            (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s&]+)', re.IGNORECASE), 'password=***'),
            (re.compile(r'api_key["\']?\s*[:=]\s*["\']?([^"\'\s&]+)', re.IGNORECASE), 'api_key=***'),
            (re.compile(r'key["\']?\s*[:=]\s*["\']?([^"\'\s&]+)', re.IGNORECASE), 'key=***'),
            (re.compile(r'secret["\']?\s*[:=]\s*["\']?([^"\'\s&]+)', re.IGNORECASE), 'secret=***'),
        ]
    
    def filter_message(self, message: str) -> str:
        """Filter sensitive data from a message string."""
        filtered = message
        for pattern, replacement in self.sensitive_patterns:
            filtered = pattern.sub(replacement, filtered)
        return filtered
    
    def filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter sensitive data from a dictionary."""
        filtered = {}
        sensitive_keys = {'password', 'token', 'api_key', 'key', 'secret'}
        
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                filtered[key] = '***'
            elif isinstance(value, str):
                filtered[key] = self.filter_message(value)
            elif isinstance(value, dict):
                filtered[key] = self.filter_dict(value)
            else:
                filtered[key] = value
        return filtered


class UnsubscribeLogger:
    """Structured logger for unsubscribe processing with context tracking."""
    
    def __init__(self, component: str):
        self.component = component
        self.logger = logging.getLogger(f"unsubscribe.{component}")
        self.context: Dict[str, Any] = {}
        self.filter = SensitiveDataFilter()
        self.operation_stats = defaultdict(lambda: {'total': 0, 'success': 0, 'failure': 0})
    
    def add_context(self, key: str, value: Any) -> None:
        """Add context information to all subsequent log messages."""
        self.context[key] = value
    
    def _prepare_log_data(self, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Prepare structured log data with context and filtering."""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'component': self.component,
            'message': self.filter.filter_message(message),
            'context': self.filter.filter_dict(self.context.copy())
        }
        
        if extra:
            filtered_extra = self.filter.filter_dict(extra)
            log_data['extra'] = filtered_extra
        
        return log_data
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message with structured data."""
        log_data = self._prepare_log_data(message, extra)
        self.logger.debug(json.dumps(log_data))
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message with structured data."""
        log_data = self._prepare_log_data(message, extra)
        self.logger.info(json.dumps(log_data))
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message with structured data."""
        log_data = self._prepare_log_data(message, extra)
        self.logger.warning(json.dumps(log_data))
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log error message with structured data."""
        log_data = self._prepare_log_data(message, extra)
        self.logger.error(json.dumps(log_data))
    
    @contextmanager
    def time_operation(self, operation_name: str):
        """Context manager to time operations and log performance."""
        start_time = time.time()
        self.debug(f"Starting {operation_name}", {"operation": operation_name})
        
        try:
            yield
            duration = time.time() - start_time
            self.info(f"Operation {operation_name} completed successfully", {
                "operation": operation_name,
                "duration_seconds": round(duration, 3),
                "status": "success"
            })
        except Exception as e:
            duration = time.time() - start_time
            self.error(f"Operation {operation_name} failed", {
                "operation": operation_name,
                "duration_seconds": round(duration, 3),
                "status": "failure",
                "error": str(e)
            })
            raise
    
    def log_exception(self, exception: Exception, extra: Optional[Dict[str, Any]] = None):
        """Log exception with full context and traceback."""
        log_data = self._prepare_log_data(f"Exception occurred: {str(exception)}", extra)
        log_data['exception'] = {
            'type': type(exception).__name__,
            'message': str(exception)
        }
        
        # Add exception context if available
        if hasattr(exception, 'context') and exception.context:
            log_data['exception']['context'] = self.filter.filter_dict(exception.context)
        
        self.logger.error(json.dumps(log_data), exc_info=True)
    
    @contextmanager
    def scoped_context(self, context: Dict[str, Any]):
        """Context manager for scoped context that is automatically removed."""
        # Save original context
        original_context = self.context.copy()
        
        # Add scoped context
        self.context.update(context)
        
        try:
            yield
        finally:
            # Restore original context
            self.context = original_context
    
    def log_operation_count(self, operation: str, success: bool):
        """Log operation count for statistics."""
        self.operation_stats[operation]['total'] += 1
        if success:
            self.operation_stats[operation]['success'] += 1
        else:
            self.operation_stats[operation]['failure'] += 1
    
    def get_operation_stats(self) -> Dict[str, Dict[str, int]]:
        """Get operation statistics."""
        return dict(self.operation_stats)


def configure_unsubscribe_logging(
    level: str = "INFO",
    format: str = "json",
    output: str = "console",
    filename: Optional[str] = None
):
    """Configure the unsubscribe logging system."""
    
    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Get or create the unsubscribe logger
    logger = logging.getLogger("unsubscribe")
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Configure formatter
    if format == "json":
        formatter = logging.Formatter('%(message)s')
    else:  # standard format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Configure handlers based on output
    if output in ["console", "both"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    if output in ["file", "both"] and filename:
        file_handler = logging.FileHandler(filename)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger