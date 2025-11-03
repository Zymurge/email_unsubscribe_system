# Changelog

All notable changes to the Email Subscription Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-02

### Added
- **Core Infrastructure (Phase 1 Complete)**
  - SQLAlchemy database models with comprehensive schema
  - IMAP client supporting major email providers (Gmail, Comcast, Outlook, Yahoo)
  - Email scanner with batch processing and duplicate detection
  - CLI interface for account and email management
  - Database initialization and management utilities
  - Configuration management with environment variables
  - Basic unsubscribe detection (headers and body text patterns)
  - Comprehensive test suite with pytest
  - Project documentation and setup instructions

### Database Schema
- `accounts` table for email account information and IMAP settings
- `email_messages` table for individual emails with metadata
- `subscriptions` table (ready for Phase 2 implementation)
- `unsubscribe_attempts` table (ready for Phase 3 implementation)

### CLI Commands
- `init` - Initialize database
- `add-account <email>` - Add email accounts with secure password prompting
- `scan <account_id>` - Scan accounts for messages with configurable date ranges
- `list-accounts` - Display all configured accounts
- `stats <account_id>` - Show detailed account statistics

### Technical Features
- Secure password handling (not stored in database)
- Batch processing for efficient large mailbox handling
- Duplicate message detection and prevention
- Proper database indexing for performance
- Comprehensive error handling and logging
- Environment-based configuration
- Extensible architecture for future phases

## [Unreleased]

### Planned for Phase 2 - Subscription Detection
- Advanced pattern recognition for subscription identification
- Email categorization and confidence scoring
- Subscription frequency analysis
- Enhanced unsubscribe link extraction

### Planned for Phase 3 - Automated Unsubscribing  
- Safe unsubscribe link processing
- Multiple unsubscribe methods (HTTP GET/POST, email replies)
- Unsubscribe attempt tracking and reporting
- Rate limiting and safety checks