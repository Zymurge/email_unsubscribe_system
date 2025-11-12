"""
Configuration settings for the email subscription manager.
"""

import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration settings."""
    
    # Database settings
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///email_subscriptions.db')
    
    # Email scanning settings
    DEFAULT_SCAN_DAYS = int(os.getenv('DEFAULT_SCAN_DAYS', '30'))
    DEFAULT_BATCH_SIZE = int(os.getenv('DEFAULT_BATCH_SIZE', '50'))
    MAX_BODY_LENGTH = int(os.getenv('MAX_BODY_LENGTH', '10000'))
    
    # IMAP connection settings
    IMAP_TIMEOUT = int(os.getenv('IMAP_TIMEOUT', '30'))
    
    # Unsubscribe settings (for future use)
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '1.0'))
    
    # Security settings
    VERIFY_SSL = os.getenv('VERIFY_SSL', 'true').lower() == 'true'
    
    @classmethod
    def get_data_dir(cls) -> Path:
        """Get the data directory for storing database and logs."""
        data_dir = Path(os.getenv('DATA_DIR', Path.cwd() / 'data'))
        data_dir.mkdir(exist_ok=True)
        return data_dir
        
    @classmethod
    def get_database_path(cls) -> str:
        """Get the full path to the database file."""
        if cls.DATABASE_URL.startswith('sqlite:///'):
            # Extract the path part
            db_file = cls.DATABASE_URL[10:]  # Remove 'sqlite:///'
            if not os.path.isabs(db_file):
                # Make it relative to data directory
                db_path = cls.get_data_dir() / db_file
                return f"sqlite:///{db_path}"
        return cls.DATABASE_URL
    
    @classmethod
    def get_credential_store_path(cls) -> Path:
        """Get the path to the credential store file."""
        # Get path from env or use default
        store_path = os.getenv('EMAIL_PSWD_STORE_PATH', 'email_passwords.json')
        
        # Expand {$DATA_DIR} variable if present
        if '{$DATA_DIR}' in store_path:
            store_path = store_path.replace('{$DATA_DIR}', str(cls.get_data_dir()))
        
        # Convert to Path and make absolute if needed
        path = Path(store_path)
        if not path.is_absolute():
            path = cls.get_data_dir() / path
        
        return path


def load_config_from_env_file(env_file: str = '.env'):
    """Load configuration from environment file."""
    env_path = Path(env_file)
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            # dotenv not available, skip
            pass