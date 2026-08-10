"""
Test suite for P0 CRITICAL FIXES - Publication Safety Validations.

These tests ensure that:
1. Diff size validation prevents massive unintended modifications
2. Revision conflict detection prevents overwriting concurrent edits
3. Both validations are applied before publication
"""

import pytest
from unittest.mock import Mock, patch
from wikipedia_maintenance.utils.publisher import Publisher


class TestDiffSizeValidation:
    """Test P0 CRITICAL FIX: Diff size validation."""
    
    def test_diff_size_validation_pass(self):
        """Test that valid diff sizes pass validation."""
        publisher = Publisher(dry_run=True)
        
        original = "Content\nwith\nthree\nlines"
        new = "Content\nwith\nthree\nlines\nand one more"  # Small addition
        
        is_valid, error_msg = publisher._validate_diff_size(original, new)
        
        assert is_valid == True
        assert error_msg == ""
    
    def test_diff_size_validation_fail_too_large(self):
        """Test that overly large diffs are rejected."""
        publisher = Publisher(dry_run=True)
        
        original = "Short content"
        new = "A" * 3000  # Far exceeds max_diff_size (2000)
        
        is_valid, error_msg = publisher._validate_diff_size(original, new)
        
        assert is_valid == False
        assert "exceeds maximum allowed" in error_msg
        assert "2000" in error_msg
    
    def test_diff_size_validation_fail_content_doubling(self):
        """Test that content doubling is rejected."""
        publisher = Publisher(dry_run=True)
        
        original = "A" * 1000
        new = "A" * 2500  # More than double the original size
        
        is_valid, error_msg = publisher._validate_diff_size(original, new)
        
        assert is_valid == False
        assert "dramatically" in error_msg
    
    def test_diff_size_validation_fail_content_halving(self):
        """Test that content halving is rejected."""
        publisher = Publisher(dry_run=True)
        
        original = "A" * 1000
        new = "A" * 300  # Less than half the original size
        
        is_valid, error_msg = publisher._validate_diff_size(original, new)
        
        assert is_valid == False
        assert "dramatically" in error_msg
    
    def test_diff_size_validation_exact_match(self):
        """Test that identical content passes (no change needed)."""
        publisher = Publisher(dry_run=True)
        
        original = "Same content"
        new = "Same content"
        
        is_valid, error_msg = publisher._validate_diff_size(original, new)
        
        assert is_valid == True
        assert error_msg == ""


class TestRevisionConflictDetection:
    """Test P0 CRITICAL FIX: Revision conflict detection."""
    
    @patch('wikipedia_maintenance.utils.publisher.Publisher._throttled_get')
    def test_revision_conflict_pass(self, mock_get):
        """Test that matching revision IDs pass validation."""
        mock_get.return_value = Mock(json=lambda: {
            'query': {
                'pages': {
                    '123': {
                        'pageid': 123,
                        'title': 'TestPage',
                        'lastrevid': 12345
                    }
                }
            }
        })
        
        publisher = Publisher(dry_run=True)
        
        is_safe, conflict_msg = publisher._check_revision_conflict('TestPage', 12345)
        
        assert is_safe == True
        assert conflict_msg == ""
    
    @patch('wikipedia_maintenance.utils.publisher.Publisher._throttled_get')
    def test_revision_conflict_fail(self, mock_get):
        """Test that mismatched revision IDs are detected."""
        mock_get.return_value = Mock(json=lambda: {
            'query': {
                'pages': {
                    '123': {
                        'pageid': 123,
                        'title': 'TestPage',
                        'lastrevid': 67890  # Different from expected 12345
                    }
                }
            }
        })
        
        publisher = Publisher(dry_run=True)
        
        is_safe, conflict_msg = publisher._check_revision_conflict('TestPage', 12345)
        
        assert is_safe == False
        assert "Revision conflict" in conflict_msg
        assert "67890" in conflict_msg
        assert "12345" in conflict_msg
    
    @patch('wikipedia_maintenance.utils.publisher.Publisher._throttled_get')
    def test_revision_conflict_disabled(self, mock_get):
        """Test that validation can be disabled."""
        publisher = Publisher(dry_run=True)
        publisher.require_revision_check = False
        
        is_safe, conflict_msg = publisher._check_revision_conflict('TestPage', 12345)
        
        assert is_safe == True
        assert conflict_msg == ""
        assert not mock_get.called  # Should not make API call
    
    @patch('wikipedia_maintenance.utils.publisher.Publisher._throttled_get')
    def test_revision_conflict_api_error_failsafe(self, mock_get):
        """Test that API errors fail safely (allow publication)."""
        mock_get.side_effect = Exception("API error")
        
        publisher = Publisher(dry_run=True)
        
        is_safe, conflict_msg = publisher._check_revision_conflict('TestPage', 12345)
        
        # Should fail safely and allow publication
        assert is_safe == True
        assert conflict_msg == ""


class TestPublishWithValidations:
    """Test that publish method applies P0 validations."""
    
    def test_publish_with_valid_diff_size(self):
        """Test that publish with valid diff size proceeds."""
        publisher = Publisher(dry_run=True)
        
        original = "Original content"
        new = "Original content with small addition"
        
        success, message = publisher.publish(
            'TestPage',
            new,
            'Test summary',
            original_content=original,
            expected_revision_id=None
        )
        
        assert success == True
        assert "DRY RUN" in message
    
    def test_publish_with_invalid_diff_size(self):
        """Test that publish with invalid diff size is blocked."""
        publisher = Publisher(dry_run=True)
        
        original = "Original"
        new = "A" * 3000  # Exceeds max_diff_size
        
        success, message = publisher.publish(
            'TestPage',
            new,
            'Test summary',
            original_content=original,
            expected_revision_id=None
        )
        
        assert success == False
        assert "Publication blocked" in message
        assert "exceeds maximum allowed" in message
    
    @patch('wikipedia_maintenance.utils.publisher.Publisher._check_revision_conflict')
    def test_publish_with_revision_conflict(self, mock_check):
        """Test that publish with revision conflict is blocked."""
        mock_check.return_value = (False, "Revision conflict detected")
        
        publisher = Publisher(dry_run=True)
        
        success, message = publisher.publish(
            'TestPage',
            "New content",
            'Test summary',
            original_content="Original",
            expected_revision_id=12345
        )
        
        assert success == False
        assert "Publication blocked" in message
        assert "Revision conflict" in message
    
    def test_publish_without_validations(self):
        """Test that publish without validation parameters uses legacy behavior."""
        publisher = Publisher(dry_run=True)
        
        # Should work without validations if parameters not provided
        success, message = publisher.publish(
            'TestPage',
            "New content",
            'Test summary'
        )
        
        assert success == True
        assert "DRY RUN" in message
    
    def test_publish_unsafe_method(self):
        """Test that publish_unsafe bypasses validations."""
        publisher = Publisher(dry_run=True)
        
        # Should bypass validations even with large diff
        success, message = publisher.publish_unsafe(
            'TestPage',
            "A" * 3000,
            'Test summary'
        )
        
        assert success == True
        assert "DRY RUN" in message


class TestSafetyParameters:
    """Test that safety parameters are properly configured."""
    
    def test_max_diff_size_default(self):
        """Test that max_diff_size has a safe default value."""
        publisher = Publisher(dry_run=True)
        
        assert publisher.max_diff_size == 2000
        assert publisher.max_diff_size > 0
    
    def test_max_diff_size_custom(self):
        """Test that max_diff_size can be customized."""
        publisher = Publisher(dry_run=True)
        publisher.max_diff_size = 5000
        
        original = "Original"
        new = "A" * 3000  # Would fail with default 2000, pass with 5000
        
        is_valid, error_msg = publisher._validate_diff_size(original, new)
        
        assert is_valid == True
    
    def test_require_revision_check_default(self):
        """Test that revision check is enabled by default."""
        publisher = Publisher(dry_run=True)
        
        assert publisher.require_revision_check == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])