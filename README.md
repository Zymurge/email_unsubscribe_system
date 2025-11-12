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
  - Secure credential storage with automatic password lookup
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

- **Phase 3 (Complete)**: Unsubscribe extraction and processing ✅
  - Extract and classify unsubscribe links from emails
  - Support multiple unsubscribe methods (HTTP GET/POST, email replies, one-click)
  - RFC 2369 and RFC 8058 compliance (List-Unsubscribe headers)
  - Safe unsubscribe link processing with comprehensive security validation
  - Attempt tracking and success/failure reporting
  - Comprehensive test coverage (27 tests)

## Installation

1. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Linux/Mac
   # or
   venv\Scripts\activate     # On Windows
   ```

1. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The system uses environment variables for configuration. Create a `.env` file:

```bash
# Database (defaults to SQLite in data/ directory)
DATABASE_URL=sqlite:///email_subscriptions.db

# Data directory (where database, logs, private settings are stored)
DATA_DIR=./data

# Scanning settings
DEFAULT_SCAN_DAYS=30
DEFAULT_BATCH_SIZE=50

# Connection settings
IMAP_TIMEOUT=30

# Optional: Store credentials for automatic login
# File is created in DATA_DIR with secure permissions (600)
EMAIL_PSWD_STORE_PATH={$DATA_DIR}/email_passwords.json
```

**Note**: The credential store file is automatically excluded from git via `.gitignore` and has restrictive file permissions (owner read/write only) for security.

## Usage

### Initialize Database

```bash
py main.py init
```

### Add Email Account

```bash
py main.py add-account user@comcast.net
```

### Store Credentials (New!)

Store passwords securely to avoid repeated prompts:

```bash
# Store password for an account
py main.py store-password user@comcast.net

# List accounts with stored passwords
py main.py list-passwords

# Remove stored password
py main.py remove-password user@comcast.net
```

**Note**: Stored credentials are saved in `data/email_passwords.json` with restrictive file permissions (600). When running commands that require passwords (scan, add-account, etc.), the system automatically uses stored credentials if available.

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

### List Subscriptions (New!)

```bash
```

### List Subscriptions

```bash
# List all subscriptions
py main.py list-subscriptions 1

# Filter by keep status
py main.py list-subscriptions 1 --keep=yes    # Only kept subscriptions
py main.py list-subscriptions 1 --keep=no     # Only non-kept (ready to unsubscribe)
py main.py list-subscriptions 1 --keep=all    # All subscriptions (default)
```

Output shows:

- Subscription ID, sender email, email count
- Keep status (✓ for kept, blank otherwise)
- Unsubscribed status (Yes/No)
- Violation count (if unsubscribed)
- Unsubscribe method available

### Unsubscribe Execution (New!)

```bash
# Test unsubscribe (dry-run - safe, no actual request)
py main.py unsubscribe 8 --dry-run

# Execute unsubscribe (with confirmation prompt)
py main.py unsubscribe 8

# Execute without confirmation (use with caution!)
py main.py unsubscribe 8 --yes
```

**Safety Features:**

- ✅ Won't unsubscribe from subscriptions marked "keep"
- ✅ Skips already unsubscribed subscriptions
- ✅ Validates unsubscribe link exists
- ✅ Shows detailed subscription info before executing
- ✅ Requires confirmation (type 'yes')
- ✅ Records all attempts in database
- ✅ Supports dry-run mode for testing

**What it shows:**

- Subscription details (ID, sender, email count, keep status)
- Previous attempt history (last 3 attempts with status)
- Safety check results
- HTTP status code and response
- Success/failure with detailed messages

### Manage Subscriptions (New!)

```python
# Mark subscriptions to keep (skip unsubscribe processing)
```
```

Output shows:

- Subscription ID, sender email, email count
- Keep status (✓ for kept, blank otherwise)
- Unsubscribed status (Yes/No)
- Violation count (if unsubscribed)
- Unsubscribe method available

### Manage Subscriptions (New!)

```python
# Mark subscriptions to keep (skip unsubscribe processing)
from src.database.models import Subscription

subscription.mark_as_keep()    # Set keep_subscription=True
subscription.unmark_as_keep()  # Set keep_subscription=False

# Check if subscription should be processed
if not subscription.should_skip_unsubscribe():
    # Safe to process for unsubscribe
    pass
```

### View Violation Reports (New!)

```bash
py main.py violations 1              # View unsubscribe violations for account ID 1
```

### Unsubscribe Processing (Phase 3 - New!)

```python
# Extract unsubscribe methods from email
from src.email_processor.unsubscribe import UnsubscribeProcessor

processor = UnsubscribeProcessor()
result = processor.process_email_for_unsubscribe_methods(
    headers={'List-Unsubscribe': '<https://company.com/unsubscribe?token=xyz>'},
    html_content='<a href="https://company.com/unsubscribe?token=xyz">Unsubscribe</a>',
    text_content=None
)

# Result contains:
# - methods: List of all detected unsubscribe methods
# - primary_method: Best method based on priority (one-click > POST > GET > email)
# - total_methods: Count of methods found

# Methods are classified as:
# - 'one_click': RFC 8058 one-click unsubscribe
# - 'http_post': POST form submission
# - 'http_get': Simple HTTP GET request  
# - 'email_reply': Email reply to unsubscribe address
```

### Database Schema

The system uses SQLite with the following main tables:

- **accounts**: Email account information and IMAP settings
- **email_messages**: Individual emails with metadata and unsubscribe indicators  
- **subscriptions**: Detected subscriptions with confidence scoring and violation tracking
  - Confidence scoring (15-100 scale)
  - Marketing keyword detection
  - Unsubscribe status and violation monitoring
  - Email count and date tracking
  - **keep_subscription flag**: Users can mark subscriptions to keep (skip unsubscribe)
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
python -m pytest tests/                    # Run all 166 tests
python -m pytest tests/test_http_get_executor.py # Run HTTP GET executor tests (14 tests - NEW!)
python -m pytest tests/test_credentials.py # Run credential storage tests (24 tests)
python -m pytest tests/test_list_subscriptions.py # Run list-subscriptions tests (12 tests)
python -m pytest tests/test_violations.py  # Run violation tracking tests  
python -m pytest tests/test_step1_subscription_creation.py # Run subscription detection tests
python -m pytest tests/test_phase3_unsubscribe_extraction.py # Run Phase 3 unsubscribe tests (27 tests)
```

### Project Structure

```plaintext
email_unsub_manager/
├── src/
│   ├── config/          # Configuration management
│   │   ├── settings.py       # Environment configuration
│   │   └── credentials.py    # Secure credential storage (NEW!)
│   ├── database/        # Database models, management, and violation reporting
│   │   ├── models.py    # SQLAlchemy models with keep_subscription flag
│   │   ├── violations.py # Violation reporting system
│   │   └── __init__.py  # Database initialization
│   ├── email_processor/ # Email processing and subscription detection
│   │   ├── imap_client.py      # IMAP connection handling
│   │   ├── scanner.py          # Email scanning and storage
│   │   ├── subscription_detector.py # Subscription detection
│   │   ├── unsubscribe_processor.py # Unsubscribe attempt tracking
│   │   └── unsubscribe/        # Unsubscribe extraction pipeline (NEW!)
│   │       ├── __init__.py     # Clean API exports
│   │       ├── constants.py    # Shared patterns and configuration
│   │       ├── extractors.py   # Link extraction from headers/HTML/text
│   │       ├── classifiers.py  # Method classification (GET/POST/email/one-click)
│   │       ├── validators.py   # Security validation and safety checks
│   │       └── processors.py   # Main pipeline and method management
│   └── utils/           # Utility functions
├── tests/               # Comprehensive test suite (132 tests)
│   ├── test_basic.py                        # Basic functionality tests
│   ├── test_credentials.py                  # Credential storage tests (24 tests - NEW!)
│   ├── test_deduplication.py               # Database constraint tests
│   ├── test_keep_subscription_schema.py    # keep_subscription flag tests
│   ├── test_phase3_unsubscribe_extraction.py # Phase 3 unsubscribe tests (27 tests)
│   ├── test_step1_subscription_creation.py # Subscription detection tests
│   └── test_violations.py                  # Violation tracking tests
├── docs/                # Documentation
│   └── PROCESSING_RULES.md # Detailed unsubscribe extraction rules
├── data/                # Database and data files (created automatically)
│   └── email_passwords.json  # Stored credentials (excluded from git)
├── main.py              # CLI entry point
└── requirements.txt     # Python dependencies

email_unsub_manager/
├── src/
│   ├── config/          # Configuration management
│   │   ├── settings.py       # Environment configuration
│   │   └── credentials.py    # Secure credential storage (NEW!)
│   ├── database/        # Database models, management, and violation reporting
│   │   ├── models.py    # SQLAlchemy models with keep_subscription flag
│   │   ├── violations.py # Violation reporting system
│   │   └── __init__.py  # Database initialization
│   ├── email_processor/ # Email processing and subscription detection
│   │   ├── imap_client.py      # IMAP connection handling
│   │   ├── scanner.py          # Email scanning and storage
│   │   ├── subscription_detector.py # Subscription detection
│   │   ├── unsubscribe_processor.py # Unsubscribe attempt tracking
│   │   └── unsubscribe/        # Unsubscribe extraction pipeline (NEW!)
│   │       ├── __init__.py     # Clean API exports
│   │       ├── constants.py    # Shared patterns and configuration
│   │       ├── extractors.py   # Link extraction from headers/HTML/text
│   │       ├── classifiers.py  # Method classification (GET/POST/email/one-click)
│   │       ├── validators.py   # Security validation and safety checks
│   │       └── processors.py   # Main pipeline and method management
│   └── utils/           # Utility functions
├── tests/               # Comprehensive test suite (132 tests)
│   ├── test_basic.py                        # Basic functionality tests
│   ├── test_credentials.py                  # Credential storage tests (24 tests - NEW!)
│   ├── test_deduplication.py               # Database constraint tests
│   ├── test_keep_subscription_schema.py    # keep_subscription flag tests
│   ├── test_phase3_unsubscribe_extraction.py # Phase 3 unsubscribe tests (27 tests)
│   ├── test_step1_subscription_creation.py # Subscription detection tests
│   └── test_violations.py                  # Violation tracking tests
├── docs/                # Documentation
│   └── PROCESSING_RULES.md # Detailed unsubscribe extraction rules
├── data/                # Database and data files (created automatically)
│   └── email_passwords.json  # Stored credentials (excluded from git)
├── main.py              # CLI entry point
└── requirements.txt     # Python dependencies
```

## Security Notes

- Passwords can be securely stored in `data/email_passwords.json` with restrictive permissions (600)
- Stored credentials are excluded from git via `.gitignore`
- IMAP connections use SSL by default
- Email content is limited to prevent excessive storage
- Unsubscribe operations include comprehensive safety checks and validation

## Roadmap

- [x] **Phase 1**: Basic email scanning and storage ✅ **COMPLETE**
- [x] **Phase 2**: Advanced subscription detection with confidence scoring ✅ **COMPLETE**
- [x] **Phase 3**: Unsubscribe extraction and processing ✅ **COMPLETE**
  - [x] Modular architecture with clean separation of concerns
  - [x] RFC compliance (2369, 8058) with one-click unsubscribe support
  - [x] Comprehensive security validation and safety checks
  - [x] "Most recent email wins" rule for method conflicts
  - [x] Full TDD methodology with 27 comprehensive tests
- [ ] **Phase 4**: Automated unsubscribe execution (in planning)
- [ ] **Phase 5**: Web interface and reporting
- [ ] **Phase 6**: OAuth support for major providers
