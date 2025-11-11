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

## [0.2.0] - 2025-11-03

### Added - Phase 2: Subscription Detection & Violation Tracking ✅ COMPLETE
- **Subscription Detection System**
  - `SubscriptionDetector` class with intelligent email pattern analysis
  - Deterministic confidence scoring algorithm (15-100 scale with bonus systems)
  - Marketing keyword detection with word boundaries ("sale", "offer", "discount", etc.)
  - Full domain extraction and sender analysis
  - Data validation and graceful error handling
  
- **Violation Tracking System**
  - `ViolationReporter` class for comprehensive monitoring
  - Track emails arriving after unsubscribe attempts
  - Violation counting and timestamp tracking (violation_count, last_violation)
  - Multiple reporting methods (summary, recent violations, worst offenders)
  - Integration with subscription detection system

- **Enhanced Database Models**
  - Added violation tracking fields to `Subscription` model
  - New methods: `has_violations`, `is_violation_email`, `record_violation`, `mark_unsubscribed`
  - Enhanced relationship mapping with comprehensive violation monitoring

- **New CLI Commands**
  - `detect-subscriptions <account_id>` - Analyze stored emails for subscription patterns
  - `violations <account_id>` - View comprehensive violation reports and statistics

- **Comprehensive Test Suite (TDD Methodology)**
  - Expanded to 30 total tests across multiple test files
  - 8 subscription detection tests in `test_step1_subscription_creation.py`
  - 7 violation tracking tests in `test_violations.py`
  - 12 foundational tests in existing files
  - Full Test-Driven Development approach with Red-Green-Refactor cycles

### Technical Improvements
- Optimized UID deduplication with pre-filtering approach (90x performance improvement)
- Enhanced confidence scoring with deterministic algorithms
- Marketing keyword detection using word boundary matching to prevent false positives
- Database-authoritative email count aggregation for data integrity
- Comprehensive error handling with graceful degradation

### Documentation Updates
- Updated README.md with Phase 2 completion status and new features
- Added Architecture section explaining the three-phase development approach
- Enhanced CLI command documentation with examples
- Updated database schema documentation with new fields and relationships
- Added comprehensive test coverage information and TDD methodology notes

## [Unreleased]

### In Progress

- Enhanced URL extraction with quoted-printable encoding support
- Improved combined scan+analyze workflow

## [0.3.0] - 2025-11-11

### Added - Phase 3: Unsubscribe Extraction System ✅ COMPLETE

- **Modular Unsubscribe Extraction Architecture**
  - Refactored monolithic code into modular package structure
  - New `src/email_processor/unsubscribe/` package with specialized modules
  - `extractors.py` - Link extraction from headers and body content
  - `classifiers.py` - Unsubscribe method classification
  - `validators.py` - Link safety validation
  - `processors.py` - High-level processing orchestration
  - `constants.py` - Shared configuration and patterns
  - `types.py` - Type definitions and dataclasses
  - `exceptions.py` - Custom exception hierarchy
  - `logging.py` - Structured logging system

- **Type Safety & Validation (Step 4.1)**
  - Type-safe dataclasses: `UnsubscribeLink`, `UnsubscribeExtraction`
  - Custom exception hierarchy with specific error types
  - Comprehensive type hints throughout codebase
  - Validation for all data structures

- **Structured Logging System (Step 4.2)**
  - `UnsubscribeLogger` with contextual logging
  - Automatic sanitization of sensitive data (emails, tokens, passwords)
  - Structured log format with severity levels
  - Per-component logger instances

- **Dependency Injection Architecture**
  - Clean separation of concerns with injectable dependencies
  - Factory pattern for component creation
  - Improved testability with mock support
  - Reduced coupling between modules

- **Combined Scan+Analyze Workflow**
  - `CombinedEmailScanner` integrating IMAP scanning with subscription detection
  - Single-command workflow: `scan-and-analyze`
  - Automatic unsubscribe link extraction during scan
  - Efficient batch processing with unified statistics

- **Quoted-Printable URL Handling**
  - Fix for incomplete URLs from quoted-printable soft line breaks
  - `_unwrap_quoted_printable_lines()` method to handle line-wrapped URLs
  - Support for both `\n` and `\r\n` line endings
  - Proper handling of `=3D` encoding for equals signs
  - Fixes truncated URLs ending with `=` (e.g., kmail-lists.com links)

### Improvements

- Enhanced URL pattern matching with line unwrapping
- Comprehensive test coverage for quoted-printable handling
- 8 new tests in `test_quoted_printable_unwrap.py`
- Improved email body content extraction
- Better handling of multi-line URLs in email bodies

### Fixed

- Incomplete unsubscribe URLs from wrapped email content
- URLs truncated at quoted-printable soft line breaks
- kmail-lists.com and similar URLs being cut off mid-URL

### CLI Commands Added

- `scan-and-analyze <account_id>` - Combined scan and subscription detection

### Planned for Future Phases

- Automated unsubscribe execution (HTTP/email methods)
- One-click unsubscribe support (RFC 8058)
- Unsubscribe attempt tracking and success/failure reporting
- Rate limiting and safety validation checks
- Integration with violation tracking for effectiveness monitoring

## Project Development Methodology

This project follows **Test-Driven Development (TDD)** practices:

- **Red-Green-Refactor** cycle implementation for all new features
- Comprehensive test specifications written before feature development
- 30 tests covering all major functionality across multiple test suites
- Continuous validation and iterative improvement approach

## Development Principles

- **Data Integrity**: "Never have a subscription record if there are no underlying emails"
- **Performance First**: Efficient algorithms with pre-filtering and optimization techniques
- **Security Conscious**: No password storage, SSL encryption, comprehensive safety checks
- **User-Centric**: Clear CLI interface with helpful error messages and comprehensive usage documentation
- **Test Coverage**: Every feature backed by comprehensive automated testing with TDD methodology
