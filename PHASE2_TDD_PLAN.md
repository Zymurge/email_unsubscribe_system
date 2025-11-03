# Phase 2 TDD Implementation Plan

## Step-by-Step TDD Approach for Subscription Detection

### Step 1: Basic Subscription Creation from Emails
**Goal**: Analyze stored emails and create Subscription records

**Test Coverage**:
- Test subscription creation from multiple emails from same sender
- Test email count aggregation per subscription
- Test confidence scoring based on email frequency
- Test sender domain extraction
- Test duplicate prevention (existing unique constraint)

### Step 2: Unsubscribe Link Extraction & Parsing
**Goal**: Extract and parse unsubscribe links from email content

**Test Coverage**:
- Test HTML unsubscribe link extraction from email body
- Test plain text unsubscribe link extraction
- Test List-Unsubscribe header parsing (RFC 2369)
- Test multiple unsubscribe links in single email
- Test malformed/invalid unsubscribe links handling
- Test different unsubscribe text patterns

### Step 3: Unsubscribe Method Classification
**Goal**: Classify unsubscribe links by method type

**Test Coverage**:
- Test HTTP GET method detection
- Test HTTP POST method detection (forms)
- Test mailto: method detection
- Test one-click unsubscribe detection (RFC 8058)
- Test complex/unknown method handling
- Test method priority when multiple methods exist

### Step 4: Pattern Recognition & Categorization
**Goal**: Analyze email patterns for better subscription classification

**Test Coverage**:
- Test email frequency analysis (daily/weekly/monthly)
- Test subject pattern recognition
- Test email categorization (marketing/newsletter/notification)
- Test List-ID header processing
- Test sender reputation analysis

### Step 5: Confidence Scoring Algorithm
**Goal**: Calculate subscription confidence based on multiple factors

**Test Coverage**:
- Test confidence scoring with different email counts
- Test confidence scoring with unsubscribe presence
- Test confidence scoring with frequency patterns
- Test confidence scoring with categorization
- Test confidence adjustment based on violation history

### Step 6: Integration & End-to-End Testing
**Goal**: Test complete subscription detection workflow

**Test Coverage**:
- Test complete pipeline: emails → subscriptions → unsubscribe methods
- Test batch processing of large email sets
- Test subscription updating vs creating new
- Test integration with existing violation tracking
- Test performance with realistic data volumes

## Implementation Order:
1. Write comprehensive tests for Step 1
2. Get tests failing (Red)
3. Implement minimal code to pass tests (Green)
4. Refactor and optimize (Refactor)
5. Repeat for each step

This approach ensures:
- ✅ Complete test coverage before implementation
- ✅ Clear requirements definition through tests
- ✅ Incremental progress with working code at each step
- ✅ Integration with existing violation tracking system
- ✅ Performance considerations built in from start