# Email Subscription Manager

A Python tool to scan email accounts, detect subscriptions, and manage unsubscribe operations.

## Features

- **Phase 1 (Current)**: Email scanning and database storage
  - Connect to email accounts via IMAP
  - Scan and index emails in SQLite database
  - Detect emails with unsubscribe information
  - Account and message management

- **Phase 2 (Planned)**: Subscription detection
  - Advanced pattern recognition for subscriptions
  - Categorization of email types
  - Subscription confidence scoring

- **Phase 3 (Planned)**: Automated unsubscribing
  - Process unsubscribe links safely
  - Multiple unsubscribe methods (HTTP, email)
  - Status tracking and reporting

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
python main.py init
```

### Add Email Account
```bash
python main.py add-account user@comcast.net
```

### Scan Account for Messages
```bash
python main.py scan 1           # Scan account ID 1 (last 30 days)
python main.py scan 1 7         # Scan last 7 days
python main.py scan 1 30 1000   # Scan last 30 days, limit to 1000 messages
```

### List Accounts
```bash
python main.py list-accounts
```

### View Account Statistics
```bash
python main.py stats 1
```

## Database Schema

The system uses SQLite with the following main tables:

- **accounts**: Email account information and IMAP settings
- **email_messages**: Individual emails with metadata and unsubscribe indicators
- **subscriptions**: Detected subscriptions (Phase 2)
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
python -m pytest tests/
```

### Project Structure
```
email_unsub_manager/
├── src/
│   ├── config/          # Configuration management
│   ├── database/        # Database models and management
│   ├── email/           # Email processing and IMAP client
│   └── utils/           # Utility functions
├── tests/               # Test files
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

- [ ] **Phase 1**: Basic email scanning and storage ✅
- [ ] **Phase 2**: Advanced subscription detection
- [ ] **Phase 3**: Safe automated unsubscribing
- [ ] **Phase 4**: Web interface and reporting
- [ ] **Phase 5**: OAuth support for major providers