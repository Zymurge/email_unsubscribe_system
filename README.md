# Email Subscription Manager

A Python tool to scan email accounts, detect subscriptions, and manage unsubscribe operations.

## Architecture

The system is built with three main phases:

1. **Email Collection** ✅: Scan email accounts via IMAP and store messages in SQLite
2. **Subscription Detection** ✅: Analyze stored emails to identify subscriptions with confidence scoring  
3. **Unsubscribe Processing**: Extract and process unsubscribe links (planned for Phase 3)

The system uses Test-Driven Development (TDD) methodology with comprehensive test coverage across all components.

## Features

- **Phase 1 (Complete)**: Email scanning and database storage ✅
  - Connect to email accounts via IMAP
  - Scan and index emails in SQLite database
  - Detect emails with unsubscribe information
  - Account and message management
  - Comprehensive test coverage (12 tests)

- **Phase 2 (Complete)**: Subscription detection ✅
  - Intelligent subscription detection from email patterns
  - Deterministic confidence scoring (15-100 scale)
  - Marketing keyword detection with word boundaries
  - Full domain extraction and sender analysis
  - Data validation and graceful error handling
  - Comprehensive test coverage (8 tests)

- **Violation Tracking (Complete)**: Unsubscribe monitoring ✅  
  - Track emails arriving after unsubscribe attempts
  - Violation counting and timestamp tracking
  - Comprehensive violation reporting system
  - Integration with subscription detection
  - Comprehensive test coverage (7 tests)

- **Phase 3 (Planned)**: Automated unsubscribing
  - Extract and classify unsubscribe links from emails
  - Support multiple unsubscribe methods (HTTP GET/POST, email replies, one-click)
  - Safe unsubscribe link processing with validation
  - Attempt tracking and success/failure reporting

## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate     # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The system uses environment variables for configuration. Create a `.env` file:

```bash
# Database (defaults to SQLite in data/ directory)
DATABASE_URL=sqlite:///email_subscriptions.db

# Scanning settings
DEFAULT_SCAN_DAYS=30
DEFAULT_BATCH_SIZE=50

# Connection settings
IMAP_TIMEOUT=30
```

## Usage

### Initialize Database
```bash
py main.py init
```

### Add Email Account
```bash
py main.py add-account user@comcast.net
```

### Scan Account for Messages
```bash
py main.py scan 1           # Scan account ID 1 (last 30 days)
py main.py scan 1 7         # Scan last 7 days
py main.py scan 1 30 1000   # Scan last 30 days, limit to 1000 messages
```

### List Accounts
```bash
py main.py list-accounts
```

### View Account Statistics
```bash
py main.py stats 1
```

### Detect Subscriptions (New!)
```bash
py main.py detect-subscriptions 1    # Detect subscriptions for account ID 1
```

### View Violation Reports (New!)
```bash
py main.py violations 1              # View unsubscribe violations for account ID 1
```

## Database Schema

The system uses SQLite with the following main tables:

- **accounts**: Email account information and IMAP settings
- **email_messages**: Individual emails with metadata and unsubscribe indicators  
- **subscriptions**: Detected subscriptions with confidence scoring and violation tracking
  - Confidence scoring (15-100 scale)
  - Marketing keyword detection
  - Unsubscribe status and violation monitoring
  - Email count and date tracking
- **unsubscribe_attempts**: Tracking of unsubscribe operations (Phase 3)

## Supported Email Providers

- Gmail (imap.gmail.com)
- Comcast (imap.comcast.net)
- Outlook/Hotmail (outlook.office365.com)
- Yahoo (imap.mail.yahoo.com)
- Generic IMAP servers

## Development

### Running Tests
```bash
python -m pytest tests/                    # Run all 30 tests
python -m pytest tests/test_violations.py  # Run violation tracking tests  
python -m pytest tests/test_step1_subscription_creation.py # Run subscription detection tests
```

### Project Structure
```
email_unsub_manager/
├── src/
│   ├── config/          # Configuration management
│   ├── database/        # Database models, management, and violation reporting
│   │   ├── models.py    # SQLAlchemy models with violation tracking
│   │   ├── violations.py # Violation reporting system
│   │   └── __init__.py  # Database initialization
│   ├── email_processor/ # Email processing and subscription detection
│   │   ├── imap_client.py      # IMAP connection handling
│   │   ├── scanner.py          # Email scanning and storage
│   │   └── subscription_detector.py # Subscription detection (NEW!)
│   └── utils/           # Utility functions
├── tests/               # Comprehensive test suite (30 tests)
│   ├── test_basic.py                        # Basic functionality tests
│   ├── test_deduplication.py               # Database constraint tests
│   ├── test_step1_subscription_creation.py # Subscription detection tests
│   └── test_violations.py                  # Violation tracking tests
├── data/                # Database and data files (created automatically)
├── main.py              # CLI entry point
└── requirements.txt     # Python dependencies
```

## Security Notes

- Passwords are not stored in the database
- IMAP connections use SSL by default
- Email content is limited to prevent excessive storage
- Future unsubscribe operations will include safety checks

## Roadmap

- [x] **Phase 1**: Basic email scanning and storage ✅ **COMPLETE**
- [x] **Phase 2**: Advanced subscription detection with confidence scoring ✅ **COMPLETE**
- [ ] **Phase 3**: Safe automated unsubscribing (in planning)
- [ ] **Phase 4**: Web interface and reporting
- [ ] **Phase 5**: OAuth support for major providers