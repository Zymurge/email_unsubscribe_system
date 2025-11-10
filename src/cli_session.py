"""
CLI session management utilities for dependency injection.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session

from .database import DatabaseManager


class CLISessionManager:
    """Manages database sessions for CLI commands with dependency injection."""
    
    def __init__(self, database_url: str = None):
        self.db_manager = DatabaseManager(database_url)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        session = self.db_manager.get_session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def execute_with_session(self, func, *args, **kwargs):
        """Execute a function with a database session injected as the first argument."""
        with self.get_session() as session:
            return func(session, *args, **kwargs)


# Global CLI session manager instance
_cli_session_manager = None


def get_cli_session_manager(database_url: str = None) -> CLISessionManager:
    """Get the global CLI session manager instance."""
    global _cli_session_manager
    if _cli_session_manager is None:
        _cli_session_manager = CLISessionManager(database_url)
    return _cli_session_manager


def with_db_session(func):
    """Decorator to inject database session into CLI command functions."""
    def wrapper(*args, **kwargs):
        session_manager = get_cli_session_manager()
        return session_manager.execute_with_session(func, *args, **kwargs)
    return wrapper