"""
Unsubscribe Executor Module

This module handles the actual execution of unsubscribe requests.
Fully decoupled from email scanning - only requires database access.
"""

from .http_executor import HttpGetExecutor

__all__ = ['HttpGetExecutor']
