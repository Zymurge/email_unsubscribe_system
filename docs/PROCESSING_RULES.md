# Email Subscription Manager - Processing Rules Documentation

**Version**: Phase 5 (December 2025)  
**Purpose**: Comprehensive business logic rules enforced by the test suite

## Overview

This document defines all processing rules and business logic for the Email Subscription Manager across all five phases. These rules are enforced through Test-Driven Development (TDD) and validated by automated tests.

**Architecture Note**: Phase 4 executors use a unified BaseUnsubscribeExecutor class to eliminate code duplication and ensure consistent validation, rate limiting, and attempt tracking across all execution methods (HTTP GET, HTTP POST, Email Reply).

---

## Phase 1: Email Collection Rules

### Email Scanning Rules

- **Deduplication**: Messages with same UID per account/folder are skipped
- **Date Range**: Default scan covers last 30 days, configurable
- **Batch Processing**: Process messages in batches of 50 for memory efficiency
- **Error Handling**: Individual message failures don't stop batch processing

### Database Storage Rules

- **Account Uniqueness**: One account record per email address (case-insensitive)
- **Message Storage**: Store metadata only, not full email content
- **Indexing**: Optimize for sender lookups and date queries
- **Relationships**: Maintain referential integrity between accounts and messages

---

## Phase 2: Subscription Detection Rules

### Detection Algorithm Rules

- **Data Authority**: Database email count is authoritative source of truth
- **Minimum Threshold**: Require at least 1 email to create subscription record
- **Confidence Scoring**: Deterministic algorithm (15-100 scale) based on multiple factors
- **Marketing Keywords**: Use word boundary matching to prevent false positives

### Confidence Scoring Rules

Base Score Calculation:

- Base confidence: 15 points (minimum for any subscription)
- Email frequency bonus: min(email_count * 2, 30) points
- Marketing keyword bonus: 10 points per keyword found
- Unsubscribe header bonus: 15 points if List-Unsubscribe header present
- Unsubscribe link bonus: 10 points if unsubscribe links in body
- Domain consistency bonus: 5 points if sender domain matches
- Total cap: 100 points maximum

### Marketing Keywords Detection

- **Keywords**: "sale", "offer", "discount", "deal", "promotion", "coupon", "savings", "free shipping", "limited time", "newsletter", "marketing", "advertisement"
- **Matching**: Use word boundaries (`\b`) to prevent partial matches
- **Case Insensitive**: Keywords matched regardless of case

### Subscription Creation Rules

- **Uniqueness**: One subscription per account/sender_email combination
- **Updates**: Existing subscriptions are updated with new data (email count, confidence, last seen)
- **Domain Extraction**: Extract domain from sender email for analysis
- **Active Status**: New subscriptions default to active=True
- **Keep Flag**: New subscriptions default to keep_subscription=False (eligible for unsubscribe)

---

## Phase 3: Unsubscribe Processing Rules

### Subscription Eligibility Rules

#### **RULE: Skip Subscriptions Marked as "Keep"**

- Users can mark any subscription with `keep_subscription=True` to indicate they want to stay subscribed
- **All unsubscribe processing is skipped** for subscriptions with `keep_subscription=True`
- This includes:
  - Link extraction and method detection
  - Unsubscribe attempt creation
  - Automated unsubscribe execution

#### **RULE: Skip Already Unsubscribed Subscriptions**

- Subscriptions with `unsubscribe_status='unsubscribed'` are skipped
- No duplicate unsubscribe attempts for already processed subscriptions

#### Eligibility Check Function

```python
def should_skip_unsubscribe(subscription) -> bool:
    return (subscription.keep_subscription or 
            subscription.unsubscribe_status == 'unsubscribed')
```

### Link Extraction Rules

#### Priority Order for Multiple Methods in Single Email

When a single email contains multiple unsubscribe methods:

1. **One-Click (RFC 8058)** - Highest priority
2. **HTTP POST** - Form-based unsubscribe
3. **HTTP GET** - Simple link-based unsubscribe  
4. **Email Reply** - mailto-based unsubscribe

#### Source Priority

1. **List-Unsubscribe Header** (RFC 2369) - Most reliable
2. **List-Unsubscribe-Post Header** (RFC 8058) - One-click capability
3. **HTML Body Links** - Common placement location
4. **Plain Text Body** - Fallback for text-only emails

### Method Classification Rules

#### HTTP GET Classification

- URLs with query parameters are classified as GET
- No form context required
- Extract parameters for token/ID information

#### HTTP POST Classification  

- Requires HTML form context with `method="post"`
- Extract form action URL and hidden input fields
- Parse form data for required parameters

#### Email Reply Classification

- `mailto:` URLs are classified as email reply
- Extract recipient address, subject, and body from URL
- Parse URL-encoded parameters

#### One-Click Classification (RFC 8058)

- Requires both `List-Unsubscribe` and `List-Unsubscribe-Post` headers
- `List-Unsubscribe-Post: List-Unsubscribe=One-Click` indicates capability
- POST request with specific payload to header URL

### Multiple Methods Per Subscription Rules

#### **RULE: Most Recent Email Wins**

- When processing multiple emails from the same subscription with different unsubscribe methods
- **Always use the method from the most recently received email**
- Ignore method "quality" or "reliability" - recency is the only factor
- Store method history for audit trail

#### Method History Tracking

- Track all method changes with timestamps
- Maintain ordered history (most recent first)
- Record which email/date triggered each method change

### Safety Validation Rules

#### Domain Validation

- **Legitimate Domains**: ALL legitimate domains are considered safe (not just "approved" lists)
- **No Domain Restrictions**: Don't restrict to email service providers only
- **Malicious Pattern Detection**: Focus on detecting harmful patterns, not limiting domains

#### Security Requirements

- **HTTPS Enforcement**: Warn on HTTP URLs, prefer HTTPS
- **Parameter Validation**: Check for suspicious parameters (cmd, delete, destroy, etc.)
- **URL Validation**: Validate URL structure and completeness
- **JavaScript Prevention**: Block javascript: URLs

#### Suspicious Patterns

- Download links (`.exe`, `.zip`, `.dmg` files)
- Dangerous actions (`delete`, `destroy`, `remove-account`)
- URL shorteners (bit.ly, tinyurl, etc.) - potential hiding malicious destinations
- Incomplete or malformed URLs

### Error Handling Rules

#### Invalid URLs

- Malformed URLs are classified as `method: 'invalid'`
- Include error description in result
- Don't fail entire processing - continue with other methods

#### Missing Context

- URLs without sufficient context default to HTTP GET
- Log when assumptions are made
- Provide fallback behavior

### Database Update Rules

#### Subscription Updates

- Update `unsubscribe_link` with most recent method URL
- Update `unsubscribe_method` with most recent method type
- Maintain `last_seen` timestamp for method updates
- **Respect `keep_subscription` flag**: Never modify subscriptions marked to keep

#### Keep Subscription Management

- `keep_subscription` defaults to False (eligible for unsubscribe)
- Users can set `keep_subscription=True` to protect wanted subscriptions
- Keep flag can be toggled on/off as user preferences change
- Keep flag is independent of subscription status (can keep active or inactive subscriptions)

#### Attempt Tracking

- Create `UnsubscribeAttempt` record for each unsubscribe operation
- **Skip attempt creation** for subscriptions with `keep_subscription=True`  
- Track method used, status, response codes, and timestamps
- Link attempts to parent subscription

---

## Phase 4: Unsubscribe Execution Rules

### Executor Selection Rules

#### **RULE: Automatic Method-Based Executor Selection**

- System automatically selects executor based on `subscription.unsubscribe_method`
- Three executors available:
  - `http_get` → HttpGetExecutor
  - `http_post` → HttpPostExecutor
  - `email_reply` → EmailReplyExecutor
- Unsupported methods are rejected with clear error message

### HTTP Executor Rules (GET & POST)

#### Request Requirements

- **User-Agent Header**: Custom header identifying the application
- **Timeout**: Default 30 seconds, configurable
- **Redirect Handling**: Automatically follow redirects
- **Success Criteria**: HTTP 2xx status codes
- **POST Specific**: Include RFC 8058 List-Unsubscribe=One-Click header

#### Safety Validations

- Check subscription not marked `keep_subscription=True`
- Check not already unsubscribed (`unsubscribed_at` is None)
- Validate unsubscribe link exists
- Verify method matches subscription method
- Enforce max attempts limit (default 3)

#### Error Handling

- HTTP errors: Record status code and error message
- Network exceptions: Capture and log connection failures
- Timeout errors: Record timeout and retry count
- All failures recorded in database with error details

### Email Reply Executor Rules

#### SMTP Requirements

- **Credentials Required**: Email address and password mandatory
- **SMTP Configuration**: Configurable host and port
- **Encryption**: STARTTLS for secure connection
- **Authentication**: Login with stored credentials
- **Timeout**: Default 30 seconds, configurable

#### mailto: URL Parsing

- Extract recipient from URL path
- Parse query parameters for subject and body
- URL decode all parameters properly
- Use defaults if subject/body not provided:
  - Default subject: "Unsubscribe"
  - Default body: "Please unsubscribe me from this mailing list."

#### Email Composition

- **From**: User's email address from account
- **To**: Recipient from mailto: URL
- **Subject**: From mailto: params or default
- **Body**: From mailto: params or default
- **Format**: Plain text MIME message

#### Safety Validations

- Same checks as HTTP executors
- Additional check for credentials availability
- Automatic credential lookup from stored passwords
- Fail gracefully if credentials not found

#### Error Handling

- SMTP connection errors: Record connection failures
- Authentication errors: Record auth failures
- Send failures: Record SMTP exceptions
- Network timeouts: Record timeout errors
- All failures recorded with detailed error messages

### Rate Limiting Rules

#### **RULE: Prevent Request/Email Flooding**

- **Delay Between Requests**: Configurable (default 2 seconds)
- **Per-Executor Instance**: Each executor tracks its own timing
- **Implementation**: Sleep if elapsed time less than delay
- **First Request**: No delay on first request
- **Subsequent Requests**: Apply full rate limit

#### Rate Limit Calculation

```python
if last_request_time is not None:
    elapsed = current_time - last_request_time
    if elapsed < rate_limit_delay:
        sleep(rate_limit_delay - elapsed)
```

### Dry-Run Mode Rules

#### **RULE: Safe Testing Without Execution**

- **Purpose**: Test unsubscribe flow without actual execution
- **Behavior**: Simulate all checks and steps
- **Output**: Report what would happen
- **Database**: NO updates to subscription or attempts
- **Network**: NO HTTP requests or SMTP connections
- **CLI Flag**: `--dry-run` enables dry-run mode

#### Dry-Run Return Values

- All executors return success with `status: 'dry_run'`
- Message indicates simulation: "Would send...", "Would request..."
- All safety checks still performed
- No database modifications

### Database Update Rules (Phase 4)

#### Successful Unsubscribe

- Set `subscription.unsubscribed_at` to current timestamp
- Set `subscription.unsubscribe_status` to 'unsubscribed'
- Create `UnsubscribeAttempt` with status='success'
- Record method used in `method_used` field
- Commit transaction

#### Failed Unsubscribe

- Keep `subscription.unsubscribed_at` as None
- Keep `subscription.unsubscribe_status` unchanged
- Create `UnsubscribeAttempt` with status='failed'
- Record error message in `error_message` field
- Record HTTP status code if applicable
- Commit transaction (to preserve failure record)

#### Attempt Record Fields

- `subscription_id`: Foreign key to parent subscription
- `method_used`: 'http_get', 'http_post', or 'email_reply'
- `status`: 'success' or 'failed'
- `attempted_at`: Timestamp of attempt
- `response_code`: HTTP status code (for HTTP methods)
- `error_message`: Error details (for failures)

**Note**: EmailMessage does NOT have a subscription_id field. The relationship between EmailMessage and Subscription is established through matching `sender_email` and `account_id`.

### CLI Command Rules (Phase 4)

#### User Confirmation Flow

1. Display subscription details (ID, sender, email count, keep status)
2. Show previous attempt history (last 3 attempts)
3. Show unsubscribe link and method
4. Request confirmation: "Type 'yes' to confirm"
5. Execute only if user confirms
6. Skip confirmation with `--yes` flag (use with caution!)

#### Safety Check Display

- Clear indication of why unsubscribe cannot proceed
- Detailed reason messages for failed checks
- Examples:
  - "Subscription marked to keep (skip unsubscribe)"
  - "Already unsubscribed"
  - "No unsubscribe link available"
  - "Max attempts (3) reached"

#### Result Display

- Success: Show confirmation with method details
- Failure: Show error message and status codes
- Dry-run: Clearly indicate simulation mode
- Database: Confirm attempt recorded

---

## Phase 5: Email Deletion Rules

### Email Deletion Eligibility Rules

#### **RULE: Strict Safety Requirements for Deletion**

All of the following conditions MUST be met before any emails can be deleted:

1. **Successful Unsubscribe**: `subscription.unsubscribe_status = 'unsubscribed'`
2. **Not Marked Keep**: `subscription.keep_subscription = False`
3. **Has Unsubscribe Date**: `subscription.unsubscribed_at` is not None
4. **Waiting Period Elapsed**: At least X days since unsubscribe (configurable, default 7 days)
5. **No Violations**: `subscription.violation_count = 0` (preserve evidence)
6. **Has Unsubscribe Link**: `subscription.unsubscribe_link` is not empty

#### Eligibility Check Function

```python
def is_eligible_for_deletion(subscription, waiting_days: int = 7) -> tuple[bool, str]:
    """
    Check if subscription is eligible for email deletion.
    Returns (eligible, reason) tuple.
    """
    if subscription.keep_subscription:
        return False, "Subscription marked to keep"
    
    if subscription.unsubscribe_status != 'unsubscribed':
        return False, "Not unsubscribed"
    
    if subscription.unsubscribed_at is None:
        return False, "No unsubscribe date recorded"
    
    if subscription.violation_count > 0:
        return False, f"Has {subscription.violation_count} violations (preserve evidence)"
    
    days_since_unsubscribe = (datetime.now() - subscription.unsubscribed_at).days
    if days_since_unsubscribe < waiting_days:
        return False, f"Waiting period not elapsed ({days_since_unsubscribe}/{waiting_days} days)"
    
    if not subscription.unsubscribe_link:
        return False, "No unsubscribe link available"
    
    return True, "Eligible for deletion"
```

### Email Deletion Scope Rules

#### **RULE: Only Delete Pre-Unsubscribe Emails**

- **Delete**: Emails where `email.received_date < subscription.unsubscribed_at`
- **Preserve**: ALL emails where `email.received_date >= subscription.unsubscribed_at`
- **Purpose**: Keep violation evidence and post-unsubscribe correspondence

#### Date Comparison Logic

```python
def get_deletable_emails(subscription, session):
    """
    Returns emails that can be safely deleted.
    Only includes emails received BEFORE unsubscribe.
    
    Note: EmailMessage links to Subscription through sender_email
    and account_id matching, not through a subscription_id field.
    """
    return session.query(EmailMessage).filter(
        EmailMessage.account_id == subscription.account_id,
        EmailMessage.sender_email == subscription.sender_email,
        EmailMessage.date_sent < subscription.unsubscribed_at
    ).all()
```

### User Confirmation Rules

#### **RULE: Strong Confirmation Required**

Deletion is permanent and dangerous. Require multiple confirmations:

1. **Display Preview**: Show subscription details and email count to be deleted
2. **Show Date Range**: Display oldest to newest deletable email dates
3. **Preserve Count**: Show count of emails that will be preserved
4. **Type Confirmation**: User must type subscription ID OR "DELETE ALL" to confirm
5. **No --yes Flag**: `--yes` flag MUST NOT skip confirmation for delete operations

#### Confirmation Prompt Format

```text
WARNING: This will permanently delete emails from your mailbox!

Subscription: sender@example.com (ID: 42)
Unsubscribed: 2025-11-05
Waiting period: 7 days (elapsed: 11 days)

Emails to DELETE: 150 emails (2025-01-15 to 2025-11-04)
Emails to PRESERVE: 3 emails (after 2025-11-05)

Type the subscription ID (42) to confirm deletion: _
```

### Dry-Run Mode Rules

#### **RULE: Safe Preview Without Deletion**

- **Purpose**: Preview what would be deleted without making changes
- **CLI Flag**: `--dry-run` enables preview mode
- **Output**: Show detailed list of emails that would be deleted
- **Database**: NO updates to database
- **IMAP**: NO connection or deletion operations
- **Display**: Show first 10 and last 10 emails with dates/subjects

#### Dry-Run Output Format

```text
DRY RUN: No emails will be deleted

Subscription: sender@example.com (ID: 42)
Deletable emails: 150 (before 2025-11-05)
Preserved emails: 3 (on or after 2025-11-05)

Sample emails to delete (first 10):
  UID 1001: "Special Offer!" (2025-01-15)
  UID 1045: "Weekly Newsletter" (2025-01-22)
  ...

Sample emails to delete (last 10):
  UID 8921: "Final Sale" (2025-10-28)
  UID 9012: "Last Chance" (2025-11-04)
  ...
```

### IMAP Deletion Rules

#### **RULE: Two-Phase Deletion Process**

Email deletion in IMAP requires two steps:

1. **Mark for Deletion**: Set `\Deleted` flag on messages
2. **Expunge**: Permanently remove messages marked for deletion

#### Deletion Implementation

```python
def delete_emails_from_imap(account, email_uids):
    """
    Delete emails from IMAP server.
    Returns (success_count, failure_count, errors)
    """
    imap_client = connect_to_imap(account)
    
    success_count = 0
    failure_count = 0
    errors = []
    
    for uid in email_uids:
        try:
            # Mark message for deletion
            imap_client.store(uid, '+FLAGS', '\\Deleted')
            success_count += 1
        except Exception as e:
            failure_count += 1
            errors.append(f"UID {uid}: {str(e)}")
    
    # Permanently remove marked messages
    imap_client.expunge()
    
    return success_count, failure_count, errors
```

#### Error Handling

- **Individual Failures**: Continue processing remaining emails if one fails
- **Connection Errors**: Fail gracefully, preserve database integrity
- **Partial Success**: Report counts of successful vs failed deletions
- **Retry Logic**: Do NOT auto-retry - require user to re-run command

### Database Update Rules

#### **RULE: Delete Database Records After IMAP Success**

- **Phase 1**: Delete emails from IMAP server first
- **Phase 2**: Delete EmailMessage records from database only if IMAP succeeds
- **Transaction**: Use database transaction for atomicity
- **Subscription**: Keep subscription record, only delete email records

#### Deletion Order

```python
def delete_subscription_emails(subscription, session, imap_client):
    """
    Delete emails in safe order: IMAP first, then database.
    """
    deletable_emails = get_deletable_emails(subscription, session)
    email_uids = [email.uid for email in deletable_emails]
    
    # Step 1: Delete from IMAP
    success_count, failure_count, errors = delete_emails_from_imap(
        subscription.account, email_uids
    )
    
    if failure_count > 0:
        return False, f"IMAP deletion failed for {failure_count} emails"
    
    # Step 2: Delete from database (only if IMAP succeeded)
    try:
        for email in deletable_emails:
            session.delete(email)
        session.commit()
        return True, f"Deleted {success_count} emails successfully"
    except Exception as e:
        session.rollback()
        return False, f"Database deletion failed: {str(e)}"
```

#### Subscription Record Updates

- **Update email_count**: Recalculate based on remaining emails
- **Keep subscription**: Do NOT delete subscription record
- **Preserve metadata**: Keep all subscription fields intact
- **Update last_modified**: Record when deletion occurred

### Rate Limiting Rules

#### **RULE: Prevent IMAP Server Overload**

- **Batch Size**: Delete in batches of 50 emails
- **Delay Between Batches**: Wait 1 second between batches
- **Total Limit**: Configurable max emails per command (default 1000)
- **Progress Display**: Show progress every 50 emails

### CLI Command Rules

#### Command Syntax

```bash
# Dry-run to preview what would be deleted
python main.py delete-emails <subscription_id> --dry-run

# Interactive deletion with confirmation
python main.py delete-emails <subscription_id>

# Specify custom waiting period (default 7 days)
python main.py delete-emails <subscription_id> --waiting-days 14
```

#### Safety Check Display

```text
Checking eligibility for email deletion...

Subscription ID: 42
Sender: sender@example.com
Status: unsubscribed ✓
Unsubscribed: 2025-11-05 (11 days ago) ✓
Keep flag: not set ✓
Violations: 0 ✓
Waiting period: 7 days ✓

Eligible for deletion ✓
```

#### Result Display

```text
Deleting emails from IMAP...
Progress: 50/150 emails deleted
Progress: 100/150 emails deleted
Progress: 150/150 emails deleted

IMAP deletion: 150 emails deleted successfully

Updating database...
Database: 150 email records deleted

Summary:
- Deleted: 150 emails (2025-01-15 to 2025-11-04)
- Preserved: 3 emails (after 2025-11-05)
- Updated email count: 153 → 3
```

### Error Recovery Rules

#### **RULE: Preserve Database Integrity**

- **IMAP Failure**: Do NOT delete database records if IMAP fails
- **Partial IMAP Success**: Only delete database records for successfully deleted IMAP emails
- **Database Failure**: Report error, allow manual cleanup
- **Network Errors**: Fail gracefully, provide clear error messages

#### Error Messages

- Connection errors: "Could not connect to IMAP server: [details]"
- Authentication errors: "IMAP authentication failed for [account]"
- Permission errors: "No permission to delete emails from folder"
- Partial failures: "Deleted X of Y emails, Z failed: [error details]"

---

## Cross-Phase Integration Rules

### Email Message Processing

- Phase 1: Store email metadata and basic unsubscribe indicators
- Phase 2: Analyze stored emails for subscription patterns
- Phase 3: Extract detailed unsubscribe methods from stored emails

### Data Consistency Rules

- **Single Source of Truth**: Database is authoritative for all data
- **Immutable History**: Never delete historical data, only mark as inactive
- **Referential Integrity**: Maintain foreign key relationships
- **Audit Trail**: Track all significant changes with timestamps

### Performance Rules

- **Batch Processing**: Process items in batches to manage memory
- **Indexing Strategy**: Index frequently queried fields
- **Query Optimization**: Use database-level aggregation over application logic
- **Connection Management**: Use connection pooling and proper session handling

---

## Violation Tracking Rules (Phase 2 Extension)

### Violation Detection

- **Violation Definition**: Emails received after successful unsubscribe
- **Automatic Detection**: Check new emails against unsubscribed subscriptions
- **Timestamp Comparison**: Email date_sent > subscription.unsubscribed_at

### Violation Recording

- **Counter Increment**: Increment violation_count for each violation
- **Email Tracking**: Track emails_after_unsubscribe count
- **Latest Violation**: Update last_violation_at with most recent violation date

### Violation Reporting

- **Recent Violations**: Show violations from configurable time window (default 7 days)
- **Worst Offenders**: Rank by total emails received after unsubscribe
- **Summary Statistics**: Total violations, total violation emails

---

## Test Coverage Requirements

### Test Categories

- **Unit Tests**: Test individual methods and functions
- **Integration Tests**: Test component interactions
- **Database Tests**: Test data persistence and relationships
- **Edge Case Tests**: Test error conditions and boundary cases

### Required Test Scenarios

- **Happy Path**: Normal operation with valid data
- **Empty Data**: Processing with no unsubscribe methods found
- **Invalid Data**: Malformed URLs, missing headers, broken HTML
- **Multiple Methods**: Single email with multiple unsubscribe options
- **Method Conflicts**: Different methods across multiple emails
- **Security Tests**: Malicious URLs and suspicious patterns

### Test Data Standards

- **Realistic Content**: Use actual email patterns and content
- **Edge Cases**: Include boundary conditions and error scenarios
- **Database Integration**: Test with actual database operations
- **Mock Usage**: Mock external dependencies, test internal logic

---

## Implementation Notes

### TDD Methodology

- **Red-Green-Refactor**: Write failing tests, implement minimal code, refactor
- **Test First**: Always write tests before implementation
- **Comprehensive Coverage**: Every rule documented here should have test coverage

### Code Organization

- **Separation of Concerns**: Separate extraction, classification, validation, and storage
- **Dependency Injection**: Use DI pattern for testability
- **Error Handling**: Graceful degradation with informative error messages
- **Logging**: Comprehensive logging for debugging and audit

### Future Extensibility

- **Plugin Architecture**: Design for easy addition of new unsubscribe methods
- **Configuration**: Make rules configurable where appropriate
- **API Design**: Clean interfaces for potential future web API
- **Standards Compliance**: Follow RFC standards where applicable

---

## Changelog

### Phase 5 (November 2025)

- Added email deletion rules for cleaning up after successful unsubscribe
- Defined strict eligibility requirements (unsubscribed, waiting period, no violations)
- Added "preserve violations" rule to keep evidence of post-unsubscribe emails
- Defined two-phase IMAP deletion process (mark + expunge)
- Added strong user confirmation requirements (no --yes flag allowed)
- Defined dry-run mode for safe preview
- Added rate limiting for IMAP operations
- Defined database update rules (IMAP first, then database)
- Added error recovery and partial failure handling

### Phase 4 (November 2025)

- Added unsubscribe execution rules for HTTP GET, HTTP POST, and Email Reply
- Defined automatic executor selection based on subscription method
- Added comprehensive safety validation rules for all executors
- Defined rate limiting rules to prevent request/email flooding
- Added dry-run mode rules for safe testing without execution
- Defined database update rules for successful and failed attempts
- Added CLI command rules with user confirmation flow
- Defined SMTP configuration and mailto: URL parsing rules
- Added credential management rules for email unsubscribe

### Phase 3 (November 2025)

- Added unsubscribe method extraction and classification rules
- Defined "most recent email wins" rule for method conflicts
- Added comprehensive safety validation rules
- Defined one-click unsubscribe support (RFC 8058)
- **Added `keep_subscription` flag** to allow users to protect wanted subscriptions
- Added subscription eligibility rules to skip kept and already unsubscribed subscriptions

### Phase 2 (November 2025)

- Added subscription detection and confidence scoring rules
- Added violation tracking and reporting rules
- Defined marketing keyword detection rules

### Phase 1 (November 2025)

- Initial email scanning and storage rules
- Database schema and relationship rules
- Basic duplicate detection and error handling

---

This document is maintained alongside the codebase and updated whenever processing rules change. All rules defined here MUST be enforced through automated tests.
