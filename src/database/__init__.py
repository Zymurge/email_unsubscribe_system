"""
Database initialization and management utilities.
"""

import os
from pathlib import Path
from sqlalchemy.orm import Session
from .models import create_database_engine, create_tables, get_session_maker, Base


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, database_url: str = None):
        if database_url is None:
            # Default to local SQLite database
            db_path = Path(__file__).parent.parent.parent / "data" / "email_subscriptions.db"
            db_path.parent.mkdir(exist_ok=True)
            database_url = f"sqlite:///{db_path}"
        
        self.database_url = database_url
        self.engine = create_database_engine(database_url)
        self.SessionMaker = get_session_maker(self.engine)
        
    def initialize_database(self):
        """Create all tables if they don't exist."""
        create_tables(self.engine)
        
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionMaker()
        
    def drop_all_tables(self):
        """Drop all tables. Use with caution!"""
        Base.metadata.drop_all(self.engine)
        
    def recreate_database(self):
        """Drop and recreate all tables. Use with caution!"""
        self.drop_all_tables()
        self.initialize_database()


# Global database manager instance
_db_manager = None


def get_db_manager(database_url: str = None) -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(database_url)
    return _db_manager


def init_database(database_url: str = None):
    """Initialize the database with tables."""
    db_manager = get_db_manager(database_url)
    db_manager.initialize_database()
    return db_manager