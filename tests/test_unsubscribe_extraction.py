"""
Test-Driven Development tests for Phase 3: Unsubscribe Link Extraction and Method Detection

Following TDD Red-Green-Refactor methodology:
1. Write failing tests (RED)
2. User reviews tests
3. Implement minimal code to pass (GREEN) 
4. Refactor for quality (REFACTOR)

These tests define the complete specification for Phase 3 unsubscribe processing.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.database.models import Account, EmailMessage, Subscription, UnsubscribeAttempt
from src.email_processor.unsubscribe import (
    UnsubscribeLinkExtractor, UnsubscribeMethodClassifier, 
    UnsubscribeSafetyValidator, UnsubscribeProcessor,
    UnsubscribeMethodUpdater, UnsubscribeMethodConflictResolver
)


class TestUnsubscribeLinkExtractor:
    """Test suite for extracting unsubscribe links from emails."""
    
    def test_extract_from_email_with_no_unsubscribe_methods(self):
        """Test that extractor returns empty list when no unsubscribe methods are found."""
        
        extractor = UnsubscribeLinkExtractor()
        
        # Email with no List-Unsubscribe header and no unsubscribe links in body
        headers = {'Subject': 'Personal email from friend'}
        html_content = """
        <html>
        <body>
            <p>Hey! How are you doing?</p>
            <p>Check out this <a href="https://example.com/article">interesting article</a></p>
            <p>Let's meet up soon!</p>
        </body>
        </html>
        """
        text_content = "Hey! How are you doing? Check out https://example.com/article"
        
        # Should return empty results
        header_links = extractor.extract_from_headers(headers)
        body_links = extractor.extract_from_body(html_content, text_content)
        
        assert len(header_links) == 0
        assert len(body_links) == 0
        
        # Complete extraction should also return empty
        all_methods = extractor.extract_all_unsubscribe_methods(headers, html_content, text_content)
        assert len(all_methods) == 0
    
    def test_extract_from_list_unsubscribe_header(self):
        """Test extraction from List-Unsubscribe header."""
        # This will fail initially - RED phase
        
        extractor = UnsubscribeLinkExtractor()
        
        # Single URL in header
        header_value = "<https://company.com/unsubscribe?id=12345>"
        links = extractor.extract_from_headers({'List-Unsubscribe': header_value})
        
        assert len(links) == 1
        assert links[0] == "https://company.com/unsubscribe?id=12345"
        
        # Multiple URLs in header
        header_value = "<https://company.com/unsubscribe?id=12345>, <mailto:unsubscribe@company.com?subject=remove>"
        links = extractor.extract_from_headers({'List-Unsubscribe': header_value})
        
        assert len(links) == 2
        assert "https://company.com/unsubscribe?id=12345" in links
        assert "mailto:unsubscribe@company.com?subject=remove" in links
        
    def test_extract_from_list_unsubscribe_post_header(self):
        """Test extraction from List-Unsubscribe-Post header (RFC 8058)."""
        
        extractor = UnsubscribeLinkExtractor()
        
        headers = {
            'List-Unsubscribe': '<https://company.com/unsubscribe?id=12345>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'
        }
        
        links = extractor.extract_from_headers(headers)
        assert len(links) == 1
        
        # Should detect one-click capability
        link_info = extractor.analyze_link_method(links[0], headers)
        assert link_info['method'] == 'one_click'
        assert link_info['one_click_capable'] == True
        
    def test_extract_from_html_body(self):
        """Test extraction from HTML email body."""
        
        extractor = UnsubscribeLinkExtractor()
        
        html_content = """
        <html>
        <body>
            <p>Thanks for subscribing to our newsletter!</p>
            <p>If you no longer wish to receive these emails, 
               <a href="https://company.com/unsubscribe?token=abc123">click here to unsubscribe</a>
            </p>
            <p>Or visit our <a href="https://company.com/preferences">email preferences</a> page.</p>
        </body>
        </html>
        """
        
        links = extractor.extract_from_body(html_content, None)
        
        assert len(links) == 2
        assert "https://company.com/unsubscribe?token=abc123" in links
        assert "https://company.com/preferences" in links
        
    def test_extract_from_text_body(self):
        """Test extraction from plain text email body."""
        
        extractor = UnsubscribeLinkExtractor()
        
        text_content = """
        Thanks for subscribing to our newsletter!
        
        To unsubscribe from future emails, visit:
        https://company.com/unsubscribe?id=12345
        
        Or email us at unsubscribe@company.com
        
        Manage your preferences: https://company.com/manage
        """
        
        links = extractor.extract_from_body(None, text_content)
        
        assert len(links) >= 2
        assert "https://company.com/unsubscribe?id=12345" in links
        assert "https://company.com/manage" in links
        # mailto links should also be detected
        assert any("unsubscribe@company.com" in link for link in links)
        
    def test_filter_unsubscribe_keywords(self):
        """Test filtering links based on unsubscribe-related keywords."""
        
        extractor = UnsubscribeLinkExtractor()
        
        html_content = """
        <a href="https://company.com/products">Shop Now</a>
        <a href="https://company.com/unsubscribe">Unsubscribe</a>
        <a href="https://company.com/optout">Opt Out</a>
        <a href="https://company.com/preferences">Email Preferences</a>
        <a href="https://company.com/contact">Contact Us</a>
        <a href="https://company.com/remove-me">Remove Me</a>
        """
        
        all_links = extractor.extract_all_links(html_content)
        unsubscribe_links = extractor.filter_unsubscribe_links(all_links)
        
        # Should only include unsubscribe-related links
        assert len(unsubscribe_links) == 4
        assert "https://company.com/products" not in unsubscribe_links
        assert "https://company.com/contact" not in unsubscribe_links
        assert "https://company.com/unsubscribe" in unsubscribe_links
        assert "https://company.com/optout" in unsubscribe_links
        assert "https://company.com/preferences" in unsubscribe_links
        assert "https://company.com/remove-me" in unsubscribe_links


class TestUnsubscribeMethodClassifier:
    """Test suite for classifying unsubscribe methods."""
    
    def test_classify_http_get_method(self):
        """Test detection of HTTP GET unsubscribe methods."""
        
        classifier = UnsubscribeMethodClassifier()
        
        # Simple GET with parameters
        url = "https://company.com/unsubscribe?email=user@example.com&token=abc123"
        method_info = classifier.classify_method(url)
        
        assert method_info['method'] == 'http_get'
        assert method_info['url'] == url
        assert 'email' in method_info['parameters']
        assert 'token' in method_info['parameters']
        assert method_info['parameters']['email'] == 'user@example.com'
        
    def test_classify_http_post_method(self):
        """Test detection of HTTP POST unsubscribe methods."""
        
        classifier = UnsubscribeMethodClassifier()
        
        # Mock HTML form analysis
        html_with_form = """
        <form method="POST" action="https://company.com/unsubscribe">
            <input type="hidden" name="subscriber_id" value="12345">
            <input type="hidden" name="list_id" value="newsletter">
            <input type="submit" value="Unsubscribe">
        </form>
        """
        
        method_info = classifier.analyze_form_method("https://company.com/unsubscribe", html_with_form)
        
        assert method_info['method'] == 'http_post'
        assert method_info['action_url'] == 'https://company.com/unsubscribe'
        assert method_info['form_data']['subscriber_id'] == '12345'
        assert method_info['form_data']['list_id'] == 'newsletter'
        
    def test_classify_email_reply_method(self):
        """Test detection of email reply unsubscribe methods."""
        
        classifier = UnsubscribeMethodClassifier()
        
        # mailto link with subject
        mailto_url = "mailto:unsubscribe@company.com?subject=Unsubscribe%20Request&body=Please%20remove%20me"
        method_info = classifier.classify_method(mailto_url)
        
        assert method_info['method'] == 'email_reply'
        assert method_info['email_address'] == 'unsubscribe@company.com'
        assert method_info['subject'] == 'Unsubscribe Request'
        assert 'Please remove me' in method_info['body']
        
    def test_classify_one_click_method(self):
        """Test detection of one-click unsubscribe methods (RFC 8058)."""
        
        classifier = UnsubscribeMethodClassifier()
        
        headers = {
            'List-Unsubscribe': '<https://company.com/unsubscribe?id=12345>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'
        }
        
        url = "https://company.com/unsubscribe?id=12345"
        method_info = classifier.classify_method(url, headers)
        
        assert method_info['method'] == 'one_click'
        assert method_info['url'] == url
        assert method_info['one_click_capable'] == True
        assert method_info['post_data'] == 'List-Unsubscribe=One-Click'
        
    def test_classify_complex_scenarios(self):
        """Test classification of complex unsubscribe scenarios with edge cases."""
        
        classifier = UnsubscribeMethodClassifier()
        
        # SCENARIO 1: URL that could be GET or POST - need to check for forms
        url = "https://company.com/unsubscribe"
        
        # Without form context - defaults to GET
        method_info = classifier.classify_method(url)
        assert method_info['method'] == 'http_get'
        
        # With form context - should detect POST
        form_html = '<form method="post" action="https://company.com/unsubscribe">'
        method_info = classifier.classify_method(url, form_context=form_html)
        assert method_info['method'] == 'http_post'
        
        # SCENARIO 2: Malformed or broken URLs
        broken_urls = [
            "https://broken-domain",  # No TLD
            "http://",               # Incomplete URL
            "",                      # Empty URL
            "not-a-url",            # Not a URL at all
        ]
        
        for broken_url in broken_urls:
            method_info = classifier.classify_method(broken_url)
            assert method_info['method'] == 'invalid'
            assert method_info['error'] is not None
        
        # SCENARIO 3: URL with both GET parameters AND form POST capability
        complex_url = "https://company.com/unsubscribe?token=abc123"
        form_html = '<form method="post" action="https://company.com/unsubscribe?token=abc123">'
        
        method_info = classifier.classify_method(complex_url, form_context=form_html)
        # Should prioritize POST over GET when form is present
        assert method_info['method'] == 'http_post'
        assert 'token' in method_info['url_parameters']  # But should still extract GET params
    
    def test_form_complexity_detection(self):
        """Test detection of forms requiring manual user intervention."""
        classifier = UnsubscribeMethodClassifier()
        
        # SCENARIO 1: Simple form with hidden inputs (should NOT require manual intervention)
        simple_form = '''
        <form method="post" action="https://example.com/unsubscribe">
            <input type="hidden" name="user_id" value="123">
            <input type="hidden" name="token" value="abc">
        </form>
        '''
        
        complexity = classifier._analyze_form_complexity(simple_form)
        assert complexity['requires_manual_intervention'] is False
        assert complexity['complexity_reason'] == 'simple_form'
        
        # SCENARIO 2: Form with checkboxes (requires manual intervention)
        checkbox_form = '''
        <form method="post" action="https://example.com/preferences">
            <input type="hidden" name="user_id" value="123">
            <input type="checkbox" name="newsletter" value="1"> Keep newsletter
            <input type="checkbox" name="promotions" value="1"> Keep promotions
        </form>
        '''
        
        complexity = classifier._analyze_form_complexity(checkbox_form)
        assert complexity['requires_manual_intervention'] is True
        assert 'checkboxes' in complexity['complexity_reason']
        
        # SCENARIO 3: Form with radio buttons (requires manual intervention)
        radio_form = '''
        <form method="post" action="https://example.com/preferences">
            <input type="radio" name="frequency" value="daily"> Daily
            <input type="radio" name="frequency" value="weekly"> Weekly
            <input type="radio" name="frequency" value="monthly"> Monthly
        </form>
        '''
        
        complexity = classifier._analyze_form_complexity(radio_form)
        assert complexity['requires_manual_intervention'] is True
        assert 'radio_buttons' in complexity['complexity_reason']
        
        # SCENARIO 4: Form with select dropdown (requires manual intervention)
        select_form = '''
        <form method="post" action="https://example.com/preferences">
            <select name="subscription_type">
                <option value="all">All emails</option>
                <option value="important">Important only</option>
                <option value="none">Unsubscribe all</option>
            </select>
        </form>
        '''
        
        complexity = classifier._analyze_form_complexity(select_form)
        assert complexity['requires_manual_intervention'] is True
        assert 'multiple_choice_dropdowns' in complexity['complexity_reason']
        
        # SCENARIO 5: Form with user choice text (requires manual intervention)
        choice_form = '''
        <form method="post" action="https://example.com/preferences">
            <p>Please select which updates you would like to continue receiving:</p>
            <input type="hidden" name="user_id" value="123">
        </form>
        '''
        
        complexity = classifier._analyze_form_complexity(choice_form)
        assert complexity['requires_manual_intervention'] is True
        assert 'user_choice_required' in complexity['complexity_reason']
    
    def test_manual_intervention_method_classification(self):
        """Test that complex forms are classified as manual intervention by processors."""
        from src.email_processor.unsubscribe.processors import UnsubscribeProcessor
        
        processor = UnsubscribeProcessor()
        
        # Email with complex form (checkboxes)
        headers = {}
        html_content = '<form method="post" action="https://example.com/preferences"><input type="checkbox" name="newsletter" value="1"> Keep newsletter<input type="checkbox" name="offers" value="1"> Keep special offers</form>'
        
        result = processor.process_email_for_unsubscribe_methods(headers, html_content, None)
        
        # Should be classified as manual intervention
        assert result['primary_method'] is not None
        assert result['primary_method']['method'] == 'manual_intervention'
        assert 'checkboxes' in result['primary_method']['complexity_reason']
        assert result['primary_method']['requires_manual_intervention'] is True


class TestUnsubscribeSafetyValidator:
    """Test suite for validating unsubscribe link safety."""
    
    def test_validate_legitimate_domains(self):
        """Test validation works for all legitimate subscription domains (not just 'safe' ones)."""
        
        validator = UnsubscribeSafetyValidator()
        
        # ANY legitimate domain should be considered safe for unsubscribing
        # This includes major email service providers AND regular company domains
        legitimate_urls = [
            "https://mailchimp.com/unsubscribe?id=123",      # Email service provider
            "https://constantcontact.com/optout?token=abc",   # Email service provider  
            "https://nike.com/unsubscribe",                  # Regular company
            "https://github.com/notifications/unsubscribe",  # Tech company
            "https://localstore.com/optout",                 # Small business
            "https://newsletter.university.edu/remove"       # Educational institution
        ]
        
        for url in legitimate_urls:
            result = validator.validate_safety(url)
            assert result['is_safe'] == True, f"Legitimate domain should be safe: {url}"
            
        # The point is to detect MALICIOUS patterns, not restrict to "approved" domains
            
    def test_validate_suspicious_patterns(self):
        """Test detection of suspicious unsubscribe patterns."""
        
        validator = UnsubscribeSafetyValidator()
        
        # Suspicious patterns
        suspicious_urls = [
            "https://malicious.com/download?file=virus.exe",  # Download links
            "https://phishing.com/confirm?delete=account",    # Dangerous actions
            "http://unsecure.com/unsubscribe",               # HTTP instead of HTTPS
            "https://bit.ly/abc123",                         # URL shorteners
            "javascript:alert('xss')",                       # JavaScript
        ]
        
        for url in suspicious_urls:
            result = validator.validate_safety(url)
            assert result['is_safe'] == False
            assert 'warning' in result
            
    def test_validate_https_requirement(self):
        """Test HTTPS requirement validation."""
        
        validator = UnsubscribeSafetyValidator()
        
        # HTTPS should be safe
        https_url = "https://company.com/unsubscribe"
        result = validator.validate_safety(https_url)
        assert result['is_safe'] == True
        
        # HTTP should trigger warning
        http_url = "http://company.com/unsubscribe"
        result = validator.validate_safety(http_url)
        assert result['is_safe'] == False
        assert 'insecure' in result['warning'].lower()
        
    def test_validate_parameter_safety(self):
        """Test validation of URL parameters for safety."""
        
        validator = UnsubscribeSafetyValidator()
        
        # Safe parameters
        safe_url = "https://company.com/unsubscribe?email=user@example.com&token=abc123"
        result = validator.validate_safety(safe_url)
        assert result['is_safe'] == True
        
        # Suspicious parameters
        suspicious_url = "https://company.com/unsubscribe?cmd=delete&action=destroy"
        result = validator.validate_safety(suspicious_url)
        assert result['is_safe'] == False
        assert 'suspicious parameters' in result['warning'].lower()


class TestUnsubscribeProcessorIntegration:
    """Integration tests for the complete unsubscribe processing pipeline."""
    
    def test_extract_and_classify_real_email(self):
        """Test extraction and classification from a realistic email."""
        
        processor = UnsubscribeProcessor()
        
        # Realistic email content
        headers = {
            'List-Unsubscribe': '<https://newsletter.company.com/unsubscribe?token=xyz789>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'
        }
        
        html_body = """
        <html>
        <body>
            <h1>Weekly Newsletter</h1>
            <p>Thank you for subscribing!</p>
            <footer>
                <p>Don't want these emails? 
                   <a href="https://newsletter.company.com/unsubscribe?token=xyz789">Unsubscribe here</a>
                </p>
                <p>Or <a href="https://newsletter.company.com/preferences">manage your preferences</a></p>
            </footer>
        </body>
        </html>
        """
        
        result = processor.process_email_for_unsubscribe_methods(headers, html_body, None)
        
        # Should detect multiple methods
        assert len(result['methods']) >= 2
        
        # Should detect one-click method
        one_click_methods = [m for m in result['methods'] if m['method'] == 'one_click']
        assert len(one_click_methods) == 1
        
        # Should detect HTTP GET method
        get_methods = [m for m in result['methods'] if m['method'] == 'http_get']
        assert len(get_methods) >= 1
        
        # All methods should pass safety validation
        for method in result['methods']:
            assert method['safety_check']['is_safe'] == True
            
    def test_update_subscription_with_unsubscribe_info(self):
        """Test updating subscription record with extracted unsubscribe information."""
        # This will use the database models we already have
        from src.database import DatabaseManager
        
        # Setup in-memory database
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            # Create test data
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            subscription = Subscription(
                account_id=account.id,
                sender_email="newsletter@company.com",
                sender_name="Company Newsletter"
            )
            session.add(subscription)
            session.commit()
            session.refresh(subscription)
            
            # Mock email with unsubscribe info
            headers = {'List-Unsubscribe': '<https://company.com/unsubscribe?id=123>'}
            html_body = '<a href="https://company.com/unsubscribe?id=123">Unsubscribe</a>'
            
            processor = UnsubscribeProcessor()
            processor.update_subscription_unsubscribe_info(subscription.id, headers, html_body, None, session)
            
            # Verify subscription was updated
            session.refresh(subscription)
            assert subscription.unsubscribe_link is not None
            assert subscription.unsubscribe_method is not None
            assert subscription.unsubscribe_method in ['http_get', 'http_post', 'email_reply', 'one_click']


class TestUnsubscribeAttemptTracking:
    """Test suite for tracking unsubscribe attempts."""
    
    def test_create_unsubscribe_attempt_record(self):
        """Test creation of unsubscribe attempt tracking records."""
        from src.database import DatabaseManager
        from src.email_processor.unsubscribe_processor import UnsubscribeAttemptTracker
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            # Create test subscription
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            subscription = Subscription(
                account_id=account.id,
                sender_email="newsletter@company.com",
                unsubscribe_link="https://company.com/unsubscribe?id=123",
                unsubscribe_method="http_get"
            )
            session.add(subscription)
            session.commit()
            session.refresh(subscription)
            
            # Create attempt tracker
            tracker = UnsubscribeAttemptTracker(session)
            
            # Record an attempt
            attempt = tracker.create_attempt(
                subscription_id=subscription.id,
                method_used="http_get",
                status="pending"
            )
            
            assert attempt.subscription_id == subscription.id
            assert attempt.method_used == "http_get"
            assert attempt.status == "pending"
            assert attempt.attempted_at is not None
            
    def test_update_attempt_with_results(self):
        """Test updating attempt records with success/failure results."""
        from src.database import DatabaseManager
        from src.email_processor.unsubscribe_processor import UnsubscribeAttemptTracker
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            # Create test data
            account = Account(email_address="test@example.com", provider="test")
            subscription = Subscription(
                account_id=1,  # Will be set properly after account creation
                sender_email="newsletter@company.com"
            )
            session.add(account)
            session.commit()
            session.refresh(account)
            
            subscription.account_id = account.id
            session.add(subscription)
            session.commit()
            session.refresh(subscription)
            
            # Create initial attempt
            attempt = UnsubscribeAttempt(
                subscription_id=subscription.id,
                method_used="http_get",
                status="pending"
            )
            session.add(attempt)
            session.commit()
            session.refresh(attempt)
            
            # Update with success
            tracker = UnsubscribeAttemptTracker(session)
            tracker.update_attempt_success(attempt.id, response_code=200, notes="Successfully unsubscribed")
            
            session.refresh(attempt)
            assert attempt.status == "success"
            assert attempt.response_code == 200
            assert "Successfully unsubscribed" in attempt.notes
            
            # Also verify subscription status updated
            session.refresh(subscription)
            assert subscription.unsubscribe_status == "unsubscribed"
            assert subscription.unsubscribed_at is not None


class TestKeepSubscriptionFlag:
    """Test handling of keep_subscription flag to skip wanted subscriptions."""
    
    def test_skip_unsubscribe_processing_for_kept_subscriptions(self):
        """Test that subscriptions marked as 'keep' are skipped during unsubscribe processing."""
        from src.database import DatabaseManager
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            # Create account and subscriptions
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Subscription 1: User wants to keep (keep_subscription=True)
            keep_sub = Subscription(
                account_id=account.id,
                sender_email="newsletter@company.com",
                sender_name="Company Newsletter",
                keep_subscription=True  # User marked to keep
            )
            
            # Subscription 2: Normal subscription (keep_subscription=False)
            normal_sub = Subscription(
                account_id=account.id,
                sender_email="marketing@store.com", 
                sender_name="Store Marketing",
                keep_subscription=False
            )
            
            session.add_all([keep_sub, normal_sub])
            session.commit()
            session.refresh(keep_sub)
            session.refresh(normal_sub)
            
            processor = UnsubscribeProcessor()
            
            # Process both subscriptions for unsubscribe
            candidates = processor.get_unsubscribe_candidates(account.id, session)
            
            # Should only include the normal subscription, not the kept one
            candidate_emails = [c.sender_email for c in candidates]
            assert "marketing@store.com" in candidate_emails
            assert "newsletter@company.com" not in candidate_emails
            
            # Verify the keep subscription check
            assert keep_sub.should_skip_unsubscribe() == True
            assert normal_sub.should_skip_unsubscribe() == False
            
    def test_skip_already_unsubscribed_subscriptions(self):
        """Test that already unsubscribed subscriptions are also skipped."""
        from src.database import DatabaseManager
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            # Subscription already unsubscribed
            unsubscribed_sub = Subscription(
                account_id=account.id,
                sender_email="old@newsletter.com",
                unsubscribe_status="unsubscribed",
                unsubscribed_at=datetime.now()
            )
            
            session.add(unsubscribed_sub)
            session.commit()
            session.refresh(unsubscribed_sub)
            
            # Should be skipped due to already unsubscribed status
            assert unsubscribed_sub.should_skip_unsubscribe() == True
            
            processor = UnsubscribeProcessor()
            candidates = processor.get_unsubscribe_candidates(account.id, session)
            
            # Should be empty since only subscription is already unsubscribed
            assert len(candidates) == 0
            
    def test_mark_subscription_as_keep(self):
        """Test marking a subscription to keep."""
        from src.database import DatabaseManager
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            subscription = Subscription(
                account_id=1,  # Will update after account creation
                sender_email="newsletter@company.com"
            )
            
            session.add(account)
            session.commit()
            session.refresh(account)
            
            subscription.account_id = account.id
            session.add(subscription)
            session.commit()
            session.refresh(subscription)
            
            # Initially should not be marked as keep
            assert subscription.keep_subscription == False
            assert subscription.should_skip_unsubscribe() == False
            
            # Mark as keep
            subscription.mark_keep_subscription(True)
            session.commit()
            session.refresh(subscription)
            
            assert subscription.keep_subscription == True
            assert subscription.should_skip_unsubscribe() == True
            
            # Unmark as keep
            subscription.mark_keep_subscription(False)
            session.commit()
            session.refresh(subscription)
            
            assert subscription.keep_subscription == False
            assert subscription.should_skip_unsubscribe() == False
            
    def test_unsubscribe_attempt_tracking_skips_kept_subscriptions(self):
        """Test that unsubscribe attempt tracking respects keep_subscription flag."""
        from src.database import DatabaseManager
        from src.email_processor.unsubscribe_processor import UnsubscribeAttemptTracker
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            account = Account(email_address="test@example.com", provider="test")
            subscription = Subscription(
                account_id=1,  # Will update after account creation
                sender_email="newsletter@company.com",
                keep_subscription=True,  # User wants to keep this
                unsubscribe_link="https://company.com/unsubscribe?id=123",
                unsubscribe_method="http_get"
            )
            
            session.add(account)
            session.commit()
            session.refresh(account)
            
            subscription.account_id = account.id
            session.add(subscription)
            session.commit()
            session.refresh(subscription)
            
            tracker = UnsubscribeAttemptTracker(session)
            
            # Attempt to create unsubscribe attempt for kept subscription
            result = tracker.create_attempt_if_eligible(subscription.id)
            
            # Should be skipped due to keep_subscription=True
            assert result['created'] == False
            assert result['reason'] == 'subscription_marked_to_keep'
            assert result['attempt'] is None


class TestMultipleUnsubscribeMethodsPerSubscription:
    """Test handling multiple unsubscribe methods for the same subscription."""
    
    def test_multiple_methods_same_email(self):
        """Test when a single email has multiple unsubscribe methods."""
        
        processor = UnsubscribeProcessor()
        
        # Email with BOTH header and body unsubscribe methods
        headers = {
            'List-Unsubscribe': '<https://company.com/header-unsubscribe?id=123>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'
        }
        
        html_body = """
        <html>
        <body>
            <p>Newsletter content here...</p>
            <footer>
                <p><a href="https://company.com/body-unsubscribe?token=xyz">Unsubscribe</a></p>
                <p>Or email <a href="mailto:remove@company.com">remove@company.com</a></p>
            </footer>
        </body>
        </html>
        """
        
        result = processor.process_email_for_unsubscribe_methods(headers, html_body, None)
        
        # Should detect multiple methods
        assert len(result['methods']) >= 3  # one-click + GET + email
        
        # Should prioritize methods by reliability (one-click > GET > email reply)
        primary_method = result['primary_method']
        assert primary_method['method'] == 'one_click'
        
    def test_conflicting_methods_across_emails(self):
        """Test when different emails from same subscription have different methods.
        
        RULE: Most recent email wins - unsubscribe method from latest email is used.
        """
        from src.database import DatabaseManager
        from datetime import datetime, timedelta
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            # Create subscription
            account = Account(email_address="test@example.com", provider="test")
            session.add(account)
            session.commit()
            session.refresh(account)
            
            subscription = Subscription(
                account_id=account.id,
                sender_email="newsletter@company.com"
            )
            session.add(subscription)
            session.commit()
            session.refresh(subscription)
            
            # Simulate processing multiple emails with different methods
            resolver = UnsubscribeMethodConflictResolver(session)
            
            # Email 1 (older): One-click method
            older_date = datetime.now() - timedelta(days=5)
            methods_1 = [{'method': 'one_click', 'url': 'https://company.com/unsubscribe?id=123'}]
            resolver.update_subscription_methods(subscription.id, methods_1, email_date=older_date)
            
            session.refresh(subscription)
            assert subscription.unsubscribe_method == 'one_click'
            
            # Email 2 (newer): Different method (GET) - should replace the one-click
            newer_date = datetime.now() - timedelta(days=1)
            methods_2 = [{'method': 'http_get', 'url': 'https://company.com/remove?token=xyz'}]
            resolver.update_subscription_methods(subscription.id, methods_2, email_date=newer_date)
            
            session.refresh(subscription)
            # RULE: Most recent email wins, regardless of method "quality"
            assert subscription.unsubscribe_method == 'http_get'
            assert subscription.unsubscribe_link == 'https://company.com/remove?token=xyz'
            
            # Should track the method change history (for now, just verify current method)
            # Full history tracking would require additional tables in production
            history = resolver.get_method_history(subscription.id)
            assert len(history) >= 1
            assert history[0]['method'] == 'http_get'  # Most recent method is current
            
    def test_method_within_single_email_priority(self):
        """Test priority when a SINGLE email has multiple unsubscribe methods.
        
        RULE: Within one email, prefer one-click > http_post > http_get > email_reply
        """
        
        processor = UnsubscribeProcessor()
        
        # Single email with multiple methods
        headers = {
            'List-Unsubscribe': '<https://company.com/unsubscribe?id=123>, <mailto:remove@company.com>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'
        }
        
        html_body = """
        <form method="post" action="https://company.com/unsubscribe-form">
            <input type="submit" value="Unsubscribe">
        </form>
        <a href="https://company.com/unsubscribe-get?token=xyz">Or click here</a>
        """
        
        result = processor.process_email_for_unsubscribe_methods(headers, html_body, None)
        
        # Should detect all methods but prioritize one-click as primary
        assert len(result['methods']) >= 3  # one-click, POST, GET, email
        assert result['primary_method']['method'] == 'one_click'
        
        # All methods should be available as alternatives
        method_types = [m['method'] for m in result['methods']]
        assert 'one_click' in method_types
        assert 'http_post' in method_types
        assert 'http_get' in method_types
            
    def test_update_method_when_better_found(self):
        """Test updating subscription when a better unsubscribe method is found."""
        from src.database import DatabaseManager
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.initialize_database()
        
        with db_manager.get_session() as session:
            # Create subscription with basic method
            account = Account(email_address="test@example.com", provider="test")
            subscription = Subscription(
                account_id=1,  # Will update after account creation
                sender_email="newsletter@company.com",
                unsubscribe_method="email_reply",
                unsubscribe_link="mailto:unsubscribe@company.com"
            )
            
            session.add(account)
            session.commit()
            session.refresh(account)
            
            subscription.account_id = account.id
            session.add(subscription)
            session.commit()
            session.refresh(subscription)
            
            updater = UnsubscribeMethodUpdater(session)
            
            # Find a better method (one-click)
            better_method = {
                'method': 'one_click',
                'url': 'https://company.com/unsubscribe?id=123',
                'reliability_score': 95
            }
            
            result = updater.update_if_better(subscription.id, better_method)
            
            assert result['updated'] == True
            assert result['reason'] == 'most_recent_email_wins'
            
            session.refresh(subscription)
            assert subscription.unsubscribe_method == 'one_click'
            assert subscription.unsubscribe_link == 'https://company.com/unsubscribe?id=123'


if __name__ == '__main__':
    # These tests will fail initially (RED phase) - this is expected in TDD
    # After user review, we'll implement the classes to make them pass (GREEN phase)
    pytest.main([__file__, '-v'])