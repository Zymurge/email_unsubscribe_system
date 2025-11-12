"""
Unsubscribe Executor Module

This module handles the actual execution of unsubscribe requests.
Fully decoupled from email scanning - only requires database access.
"""

from .http_executor import HttpGetExecutor
from .http_post_executor import HttpPostExecutor
from .email_reply_executor import EmailReplyExecutor

__all__ = ['HttpGetExecutor', 'HttpPostExecutor', 'EmailReplyExecutor']
