# Email Subscription Manager

A Python tool to scan email accounts, detect subscriptions, and manage unsubscribe operations.

## Architecture

The system is built with five main phases:

1. **Email Collection** ✅: Scan email accounts via IMAP and store messages in SQLite
2. **Subscription Detection** ✅: Analyze stored emails to identify subscriptions with confidence scoring
3. **Unsubscribe Extraction** ✅: Extract and classify unsubscribe methods from email headers and body content
4. **Unsubscribe Execution** ✅: Execute unsubscribe requests via HTTP GET/POST or email reply (unified executor architecture)
5. **Email Deletion** ✅: Safely delete pre-unsubscribe emails with comprehensive safety checks

The system uses Test-Driven Development (TDD) methodology with comprehensive test coverage across all components. The executor layer uses a unified base class pattern to eliminate code duplication and ensure consistent validation, rate limiting, and attempt tracking across all unsubscribe methods.

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
  - Deterministic confidence scoring (15-100 scale) with regular pattern bonus
  - Marketing keyword detection with word boundaries
  - Full domain extraction and sender analysis
  - Data validation and graceful error handling
  - Comprehensive test coverage (8 tests)

- **Phase 3 (Complete)**: Unsubscribe extraction ✅
  - Extract unsubscribe links from List-Unsubscribe headers and email body
  - Classify unsubscribe methods (HTTP GET, HTTP POST, Email Reply, One-Click, Manual Intervention)
  - **Form Complexity Detection**: Identifies forms requiring user selections (checkboxes, dropdowns, etc.)
  - **Manual Intervention Logging**: Logs sites with complex forms that need human handling
  - Safety validation for extracted links
  - Modular architecture with extractors, classifiers, validators, and processors
  - Conflict resolution for multiple unsubscribe methods
  - Comprehensive test coverage (140+ tests)

- **Phase 4 (Complete)**: Unsubscribe execution ✅
  - Unified base executor class with shared validation and rate limiting
  - HTTP GET executor with comprehensive safety checks
  - HTTP POST executor with RFC 8058 compliance (List-Unsubscribe=One-Click header)
  - Email Reply executor with SMTP sending
  - Automatic executor selection based on subscription method
  - Support for Gmail, Outlook, Yahoo, and other SMTP providers
  - Dry-run mode for safe testing
  - Interactive CLI command with confirmations
  - Full attempt tracking and database integration
  - Comprehensive test coverage (52 tests: 14 GET + 15 POST + 23 Email)

- **Phase 5 (Complete)**: Email deletion and cleanup ✅
  - Safely delete pre-unsubscribe emails from IMAP mailbox
  - 6 comprehensive safety checks (unsubscribed status, waiting period, violations, etc.)
  - Preserves post-unsubscribe emails as violation evidence
  - Strong confirmation requirements (no --yes flag)
  - Dry-run mode for preview
  - Two-phase deletion (IMAP then database)
  - Comprehensive test coverage (26 tests)

- **Violation Tracking (Complete)**: Unsubscribe monitoring ✅
  - Track emails arriving after unsubscribe attempts
  - Violation counting and timestamp tracking
  - Comprehensive violation reporting system
  - Integration with subscription detection
  - Comprehensive test coverage (7 tests)

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
py main.py account add user@comcast.net
py main.py account add user@custom.com --imap-server mail.custom.com --provider custom
```

**Supported Providers** (auto-detected from email domain):

- Gmail (`imap.gmail.com`)
- Outlook/Hotmail (`outlook.office365.com`)
- Yahoo (`imap.mail.yahoo.com`)
- iCloud (`imap.mail.me.com`)
- Comcast (`imap.comcast.net`)

**Options:**

- `--provider`: Override auto-detected provider
- `--imap-server`: IMAP server address (required for custom providers)
- `--imap-port`: IMAP port (default: 993)

Store passwords securely to avoid repeated prompts:

```bash
# Store password for an account
py main.py store-password user@comcast.net

# List accounts with stored passwords
py main.py list-passwords

# Remove stored password
py main.py remove-password user@comcast.net
```

**Note**: Stored credentials are saved in `data/email_passwords.json` with restrictive file permissions (600). When running commands that require passwords (scan, account add, etc.), the system automatically uses stored credentials if available.

### Scan Account for Messages

```bash
py main.py scan 1           # Scan account ID 1 (last 30 days)
py main.py scan 1 7         # Scan last 7 days
py main.py scan 1 30 1000   # Scan last 30 days, limit to 1000 messages
```

### List Accounts

```bash
py main.py account list
```

### View Account Statistics

```bash
py main.py stats 1
```

### Detect Subscriptions

```bash
py main.py detect-subscriptions 1    # Detect subscriptions for account ID 1
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

### Manage Keep Status

Mark subscriptions to protect them from unsubscribe operations (e.g., important services, legitimate newsletters you want to keep):

```bash
# Mark specific subscriptions to keep
py main.py keep 1 2 3                    # By ID list
py main.py keep 1,2,3                    # Comma-separated
py main.py keep 10-20                    # By ID range
py main.py keep --pattern %sutter%       # By SQL pattern (case-insensitive)
py main.py keep --domain example.com     # By domain

# Unmark subscriptions (make eligible for unsubscribe)
py main.py unkeep 1 2 3                  # By ID list
py main.py unkeep --pattern %newsletter% # By SQL pattern
py main.py unkeep --domain spam.com      # By domain

# Skip confirmation prompt (for automation)
py main.py keep 1 2 3 --yes
py main.py unkeep 4 5 6 --yes
```

**Features:**

- ✅ Multiple matching modes (IDs, ranges, patterns, domains)
- ✅ Shows preview of affected subscriptions
- ✅ Requires confirmation (unless `--yes` flag used)
- ✅ Idempotent operations (handles already kept/unkept gracefully)
- ✅ SQL LIKE pattern matching with wildcards (%, _)
- ✅ Domain matching with optional @ prefix

### Unsubscribe Execution

Execute unsubscribe operations using HTTP GET, HTTP POST, or Email Reply methods. The system automatically selects the appropriate executor based on the subscription's unsubscribe method.

```bash
# Test unsubscribe (dry-run - safe, no actual request/email)
py main.py unsubscribe 8 --dry-run

# Execute unsubscribe (with confirmation prompt)
py main.py unsubscribe 8

# Execute without confirmation (use with caution!)
py main.py unsubscribe 8 --yes
```

**Supported Methods:**

- ✅ **HTTP GET**: Simple link-based unsubscribe (most common)
- ✅ **HTTP POST**: Form-based unsubscribe with RFC 8058 compliance (List-Unsubscribe=One-Click header)
- ✅ **Email Reply**: mailto: unsubscribe links with SMTP sending

**Safety Features:**

- ✅ Won't unsubscribe from subscriptions marked "keep"
- ✅ Skips already unsubscribed subscriptions
- ✅ Validates unsubscribe link exists
- ✅ Verifies correct method type (http_get, http_post, or email_reply)
- ✅ Enforces maximum retry attempts
- ✅ Shows detailed subscription info before executing
- ✅ Requires confirmation (type 'yes')
- ✅ Records all attempts in database
- ✅ Supports dry-run mode for testing
- ✅ Automatic credential lookup for email unsubscribe

**What it shows:**

- Subscription details (ID, sender, email count, keep status)
- Previous attempt history (last 3 attempts with status)
- Safety check results
- HTTP status code / email delivery confirmation
- Success/failure with detailed messages

### View Violation Reports

```bash
py main.py violations 1              # View unsubscribe violations for account ID 1
```

### Delete Subscription Emails

⚠️ **WARNING: This permanently deletes emails from your mailbox!**

After successfully unsubscribing and waiting for a grace period, you can delete old marketing emails to reclaim mailbox space. This feature includes multiple safety checks to prevent accidental deletion.

```bash
# Preview what would be deleted (safe, no actual deletion)
py main.py delete-emails 42 --dry-run

# Delete emails with interactive confirmation
py main.py delete-emails 42

# Specify custom waiting period (default 7 days)
py main.py delete-emails 42 --waiting-days 14
```

**Strict Safety Requirements** (ALL must be met):

- ✅ Subscription must be successfully unsubscribed
- ✅ Subscription cannot be marked as "keep"
- ✅ Waiting period must have elapsed (default 7 days since unsubscribe)
- ✅ Subscription must have NO violations (preserves evidence)
- ✅ Must have valid unsubscribe link recorded

**What Gets Deleted:**

- ✅ Emails received **BEFORE** the unsubscribe date
- ❌ Emails received **AFTER** unsubscribe are **PRESERVED** (violation evidence)

**Safety Features:**

- 🔒 Strong confirmation required (type subscription ID to confirm)
- 🔒 No `--yes` flag support (prevents accidental automation)
- 🔒 Dry-run mode to preview before deleting
- 🔒 Two-phase deletion (IMAP first, then database)
- 🔒 Preserves all post-unsubscribe emails
- 🔒 Preserves subscription record and metadata
- 🔒 Rate limiting to prevent server overload
- 🔒 Error recovery for partial failures

**Example Output:**

```text
WARNING: This will permanently delete emails from your mailbox!

Subscription: newsletters@example.com (ID: 42)
Unsubscribed: 2025-11-05
Waiting period: 7 days (elapsed: 11 days) ✓

Emails to DELETE: 150 emails (2025-01-15 to 2025-11-04)
Emails to PRESERVE: 3 emails (after 2025-11-05)

Type the subscription ID (42) to confirm deletion: _
```

### Unsubscribe Processing (Phase 3)

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
  - Fields: `email_address`, `provider`, `imap_server`, `imap_port`, `use_ssl`
- **email_messages**: Individual emails with metadata and unsubscribe indicators
  - Links to subscriptions via `sender_email` and `account_id` (no direct foreign key)
  - Fields include: `sender_email`, `date_sent`, `uid`, `message_id`
- **subscriptions**: Detected subscriptions with confidence scoring and violation tracking
  - Confidence scoring (15-100 scale via `confidence_score` field) with bonuses for unsubscribe info, marketing keywords, and regular patterns
  - Marketing keyword detection
  - Unsubscribe status and violation monitoring
  - Email count and date tracking
  - **keep_subscription flag**: Users can mark subscriptions to keep (skip unsubscribe)
  - **unsubscribe_complexity**: Reason why manual intervention is required (for complex forms)
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
python -m pytest tests/                    # Run all 341 tests
python -m pytest tests/test_subscription_matcher.py # Run subscription matcher tests (29 tests)
python -m pytest tests/test_cli_action.py # Run CLI action command tests (15 tests)
python -m pytest tests/test_http_get_executor.py # Run HTTP GET executor tests (14 tests)
python -m pytest tests/test_http_post_executor.py # Run HTTP POST executor tests (15 tests)
python -m pytest tests/test_email_reply_executor.py # Run Email Reply executor tests (23 tests)
python -m pytest tests/test_delete_emails.py # Run email deletion tests (26 tests)
python -m pytest tests/test_config_credentials.py # Run credential storage tests (24 tests)
python -m pytest tests/test_list_subscriptions.py # Run list-subscriptions tests (12 tests)
python -m pytest tests/test_database_violations.py  # Run violation tracking tests
python -m pytest tests/test_subscription_creation.py # Run subscription detection tests
python -m pytest tests/test_unsubscribe_extraction.py # Run unsubscribe extraction tests (27 tests)
```

### Project Structure

```plaintext
email_unsub_manager/
├── src/
│   ├── config/          # Configuration management
│   │   ├── settings.py       # Environment configuration
│   │   └── credentials.py    # Secure credential storage
│   ├── database/        # Database models, management, and matching
│   │   ├── models.py    # SQLAlchemy models with keep_subscription flag
│   │   ├── violations.py # Violation reporting system
│   │   ├── subscription_matcher.py # Flexible subscription matching (29 tests)
│   │   └── __init__.py  # Database initialization
│   ├── email_processor/ # Email processing and subscription detection
│   │   ├── imap_client.py      # IMAP connection handling
│   │   ├── scanner.py          # Email scanning and storage
│   │   ├── subscription_detector.py # Subscription detection
│   │   ├── unsubscribe_processor.py # Unsubscribe attempt tracking
│   │   └── unsubscribe/        # Unsubscribe extraction pipeline
│   │       ├── __init__.py     # Clean API exports
│   │       ├── constants.py    # Shared patterns and configuration
│   │       ├── extractors.py   # Link extraction from headers/HTML/text
│   │       ├── classifiers.py  # Method classification (GET/POST/email/one-click)
│   │       ├── validators.py   # Security validation and safety checks
│   │       └── processors.py   # Main pipeline and method management
│   ├── unsubscribe_executor/   # Unsubscribe execution engines
│   │   ├── __init__.py
│   │   ├── http_get_executor.py    # HTTP GET unsubscribe executor
│   │   ├── http_post_executor.py   # HTTP POST unsubscribe executor (RFC 8058)
│   │   └── email_reply_executor.py # Email Reply unsubscribe executor (SMTP)
│   └── utils/           # Utility functions
├── tests/               # Comprehensive test suite (341 tests)
│   ├── test_cli_action.py                     # CLI action command tests (15 tests)
│   ├── test_cli_error_handling.py            # CLI error handling tests (4 tests)
│   ├── test_cli_info.py                      # CLI info command tests
│   ├── test_cli_password.py                  # CLI password command tests
│   ├── test_cli_simple.py                    # CLI simple command tests
│   ├── test_config_credentials.py            # Credential storage tests (24 tests)
│   ├── test_core_dependency_injection.py     # Dependency injection tests
│   ├── test_database_deduplication.py        # Database constraint tests
│   ├── test_database_keep_subscription.py    # keep_subscription flag tests
│   ├── test_database_models.py               # Basic database model tests
│   ├── test_database_violations.py           # Violation tracking tests
│   ├── test_delete_emails.py                 # Email deletion tests (26 tests)
│   ├── test_email_processor_combined_scanner.py # Combined scanner tests
│   ├── test_email_reply_executor.py          # Email Reply executor tests (23 tests)
│   ├── test_http_get_executor.py             # HTTP GET executor tests (14 tests)
│   ├── test_http_post_executor.py            # HTTP POST executor tests (15 tests)
│   ├── test_list_subscriptions.py            # list-subscriptions tests (12 tests)
│   ├── test_logging.py                       # Logging functionality tests
│   ├── test_quoted_printable_unwrap.py       # Quoted printable decoding tests
│   ├── test_subscription_creation.py         # Subscription creation tests
│   ├── test_subscription_creation_spec.py    # Subscription creation specification tests
│   ├── test_subscription_matcher.py          # Subscription matcher tests (29 tests)
│   ├── test_type_safety.py                   # Type safety and validation tests
│   └── test_unsubscribe_extraction.py        # Unsubscribe extraction tests (27 tests)
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
- [x] **Phase 4**: Unsubscribe execution ✅ **COMPLETE**
  - [x] HttpGetExecutor with comprehensive safety checks
  - [x] HttpPostExecutor with RFC 8058 compliance (List-Unsubscribe=One-Click header)
  - [x] EmailReplyExecutor with SMTP sending and authentication
  - [x] Automatic executor selection based on subscription method
  - [x] Support for Gmail, Outlook, Yahoo, and other SMTP providers
  - [x] Dry-run mode for safe testing
  - [x] Interactive CLI command with confirmations
  - [x] Full attempt tracking and database integration
  - [x] Full TDD methodology with 52 comprehensive tests (14 GET + 15 POST + 23 Email)
- [x] **Phase 5**: Email deletion and cleanup ✅ **COMPLETE**
  - [x] Delete old marketing emails after successful unsubscribe
  - [x] Multiple safety checks (waiting period, no violations, not kept)
  - [x] Preserve post-unsubscribe emails (violation evidence)
  - [x] Strong confirmation requirements
  - [x] Dry-run preview mode
  - [x] Two-phase deletion (IMAP + database)
  - [x] TDD methodology with comprehensive test coverage (26 tests)
- [ ] **Phase 6**: Web interface and reporting
- [ ] **Phase 7**: OAuth support for major providers
