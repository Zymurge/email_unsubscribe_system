# Email Subscription Manager - Processing Rules Documentation

**Version**: Phase 3 (November 2025)  
**Purpose**: Comprehensive business logic rules enforced by the test suite

## Overview

This document defines all processing rules and business logic for the Email Subscription Manager across all three phases. These rules are enforced through Test-Driven Development (TDD) and validated by automated tests.

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

- `subscription_id`: Link to parent subscription
- `method_used`: 'http_get', 'http_post', or 'email_reply'
- `status`: 'success' or 'failed'
- `attempted_at`: Timestamp of attempt
- `response_code`: HTTP status code (for HTTP methods)
- `error_message`: Error details (for failures)

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
