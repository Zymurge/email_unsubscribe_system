"""
Tests for credential storage functionality.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path

from src.config.credentials import CredentialStore, get_credential_store


class TestCredentialStore:
    """Test suite for CredentialStore class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.store_path = Path(self.temp_file.name)
        self.store = CredentialStore(self.store_path)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Remove the temp file
        if self.store_path.exists():
            self.store_path.unlink()
    
    def test_init_creates_empty_store(self):
        """Test that initializing creates an empty credential store."""
        assert len(self.store.list_stored_emails()) == 0
    
    def test_set_and_get_password(self):
        """Test storing and retrieving a password."""
        email = "test@example.com"
        password = "test_password_123"
        
        self.store.set_password(email, password)
        retrieved = self.store.get_password(email)
        
        assert retrieved == password
    
    def test_get_nonexistent_password(self):
        """Test retrieving a password that doesn't exist."""
        result = self.store.get_password("nonexistent@example.com")
        assert result is None
    
    def test_case_insensitive_lookup(self):
        """Test that email lookup is case-insensitive."""
        email = "Test@Example.COM"
        password = "password123"
        
        self.store.set_password(email, password)
        
        # Try various case combinations
        assert self.store.get_password("test@example.com") == password
        assert self.store.get_password("TEST@EXAMPLE.COM") == password
        assert self.store.get_password("Test@Example.COM") == password
    
    def test_remove_password(self):
        """Test removing a stored password."""
        email = "test@example.com"
        password = "password123"
        
        self.store.set_password(email, password)
        assert self.store.has_password(email)
        
        result = self.store.remove_password(email)
        assert result is True
        assert not self.store.has_password(email)
        assert self.store.get_password(email) is None
    
    def test_remove_nonexistent_password(self):
        """Test removing a password that doesn't exist."""
        result = self.store.remove_password("nonexistent@example.com")
        assert result is False
    
    def test_has_password(self):
        """Test checking if a password exists."""
        email = "test@example.com"
        
        assert not self.store.has_password(email)
        
        self.store.set_password(email, "password")
        assert self.store.has_password(email)
    
    def test_list_stored_emails(self):
        """Test listing all stored email addresses."""
        emails = [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com"
        ]
        
        for email in emails:
            self.store.set_password(email, f"password_for_{email}")
        
        stored = self.store.list_stored_emails()
        assert len(stored) == 3
        assert set(stored) == set([e.lower() for e in emails])
        # Should be sorted
        assert stored == sorted(stored)
    
    def test_clear_all(self):
        """Test clearing all stored credentials."""
        self.store.set_password("test1@example.com", "pass1")
        self.store.set_password("test2@example.com", "pass2")
        
        assert len(self.store.list_stored_emails()) == 2
        
        self.store.clear_all()
        assert len(self.store.list_stored_emails()) == 0
    
    def test_persistence_across_instances(self):
        """Test that credentials persist across CredentialStore instances."""
        email = "persistent@example.com"
        password = "my_password"
        
        # Store in first instance
        self.store.set_password(email, password)
        
        # Create a new instance pointing to the same file
        new_store = CredentialStore(self.store_path)
        
        # Should be able to retrieve from new instance
        assert new_store.get_password(email) == password
    
    def test_update_existing_password(self):
        """Test updating an existing password."""
        email = "test@example.com"
        old_password = "old_password"
        new_password = "new_password"
        
        self.store.set_password(email, old_password)
        assert self.store.get_password(email) == old_password
        
        self.store.set_password(email, new_password)
        assert self.store.get_password(email) == new_password
    
    def test_file_permissions(self):
        """Test that the credential file has restrictive permissions."""
        email = "test@example.com"
        self.store.set_password(email, "password")
        
        # Check file permissions (should be 600)
        stat_info = os.stat(self.store_path)
        permissions = stat_info.st_mode & 0o777
        
        assert permissions == 0o600, f"Expected 0o600 but got {oct(permissions)}"
    
    def test_handles_corrupted_json(self):
        """Test that corrupted JSON file is handled gracefully."""
        # Write invalid JSON to the file
        with open(self.store_path, 'w') as f:
            f.write("this is not valid json{[")
        
        # Should not raise an exception, should start fresh
        store = CredentialStore(self.store_path)
        assert len(store.list_stored_emails()) == 0
    
    def test_handles_invalid_json_structure(self):
        """Test that invalid JSON structure is handled gracefully."""
        # Write valid JSON but wrong structure (list instead of dict)
        with open(self.store_path, 'w') as f:
            json.dump(["this", "is", "a", "list"], f)
        
        # Should not raise an exception, should start fresh
        store = CredentialStore(self.store_path)
        assert len(store.list_stored_emails()) == 0
    
    def test_json_file_format(self):
        """Test that the JSON file is properly formatted."""
        self.store.set_password("test1@example.com", "pass1")
        self.store.set_password("test2@example.com", "pass2")
        
        # Read and verify JSON structure
        with open(self.store_path, 'r') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert "test1@example.com" in data
        assert "test2@example.com" in data
        assert data["test1@example.com"] == "pass1"
        assert data["test2@example.com"] == "pass2"
    
    def test_multiple_operations(self):
        """Test multiple operations in sequence."""
        # Add several passwords
        self.store.set_password("user1@example.com", "pass1")
        self.store.set_password("user2@example.com", "pass2")
        self.store.set_password("user3@example.com", "pass3")
        
        assert len(self.store.list_stored_emails()) == 3
        
        # Remove one
        self.store.remove_password("user2@example.com")
        assert len(self.store.list_stored_emails()) == 2
        
        # Update one
        self.store.set_password("user1@example.com", "new_pass1")
        assert self.store.get_password("user1@example.com") == "new_pass1"
        
        # Verify final state
        emails = self.store.list_stored_emails()
        assert "user1@example.com" in emails
        assert "user2@example.com" not in emails
        assert "user3@example.com" in emails


class TestGetCredentialStore:
    """Test suite for the global credential store function."""
    
    def test_get_credential_store_singleton(self):
        """Test that get_credential_store returns a singleton instance."""
        # Note: This test may affect the global state
        # In a real test environment, you'd want to reset the global state
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        temp_file.close()
        temp_path = Path(temp_file.name)
        
        try:
            store1 = get_credential_store(temp_path)
            store2 = get_credential_store(temp_path)
            
            # Should return the same instance
            assert store1 is store2
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()
            # Reset global state for other tests
            import src.config.credentials
            src.config.credentials._credential_store = None


class TestCredentialStoreEdgeCases:
    """Test edge cases and special scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.store_path = Path(self.temp_file.name)
        self.store = CredentialStore(self.store_path)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.store_path.exists():
            self.store_path.unlink()
    
    def test_empty_email_address(self):
        """Test handling of empty email address."""
        self.store.set_password("", "password")
        assert self.store.get_password("") == "password"
    
    def test_empty_password(self):
        """Test handling of empty password."""
        self.store.set_password("test@example.com", "")
        assert self.store.get_password("test@example.com") == ""
    
    def test_special_characters_in_email(self):
        """Test handling of special characters in email."""
        emails = [
            "user+tag@example.com",
            "user.name@example.com",
            "user_name@example.com",
            "123@example.com"
        ]
        
        for email in emails:
            self.store.set_password(email, f"pass_{email}")
            assert self.store.get_password(email) == f"pass_{email}"
    
    def test_special_characters_in_password(self):
        """Test handling of special characters in password."""
        passwords = [
            "p@ssw0rd!",
            "p@ss w0rd",  # with space
            "pässwörd",   # unicode
            "pass\"word'",  # quotes
            "pass\\word",   # backslash
        ]
        
        for i, password in enumerate(passwords):
            email = f"test{i}@example.com"
            self.store.set_password(email, password)
            assert self.store.get_password(email) == password
    
    def test_unicode_in_email(self):
        """Test handling of unicode characters in email."""
        email = "tëst@ëxamplë.com"
        password = "password123"
        
        self.store.set_password(email, password)
        assert self.store.get_password(email) == password
    
    def test_very_long_password(self):
        """Test handling of very long passwords."""
        long_password = "a" * 10000  # 10,000 character password
        email = "test@example.com"
        
        self.store.set_password(email, long_password)
        assert self.store.get_password(email) == long_password
    
    def test_store_with_none_path(self):
        """Test CredentialStore initialization with None path."""
        store = CredentialStore(None)
        
        # Should work but not persist
        store.set_password("test@example.com", "password")
        assert store.get_password("test@example.com") == "password"
        
        # Verify _save_credentials doesn't crash with None path
        assert store.store_path is None
