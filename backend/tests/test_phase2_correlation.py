"""
Test Phase 2: Issue/Correction Correlation

Tests that Issue and Correction are properly correlated via operation_id.
This ensures we can trace which detection led to which correction.
"""

import pytest
import uuid
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from wikipedia_maintenance.analyzers.base import Issue
from wikipedia_maintenance.utils.publisher import Corrector, Correction


class TestPhase2Correlation:
    """Test Phase 2 Issue/Correction correlation."""

    def test_issue_with_operation_id(self):
        """Test that Issue can have operation_id."""
        operation_id = str(uuid.uuid4())
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            operation_id=operation_id
        )
        
        assert issue.operation_id == operation_id
        assert "operation_id" in issue.to_dict()
        
        print("[OK] Issue with operation_id works")

    def test_correction_with_operation_id(self):
        """Test that Correction can have operation_id."""
        operation_id = str(uuid.uuid4())
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            operation_id=operation_id
        )
        
        correction = Correction(
            issue=issue,
            applied=True,
            operation_id=operation_id
        )
        
        assert correction.operation_id == operation_id
        assert correction.operation_id == issue.operation_id
        assert "operation_id" in correction.to_dict()
        
        print("[OK] Correction with operation_id works")

    def test_corrector_preserves_operation_id(self):
        """Test that Corrector preserves operation_id from Issue to Correction."""
        operation_id = str(uuid.uuid4())
        content = "Test content with https://example.com link"
        
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=15,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            operation_id=operation_id
        )
        
        corrector = Corrector(content)
        corrections = corrector.apply_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.operation_id == operation_id
        assert correction.operation_id == issue.operation_id
        
        print("[OK] Corrector preserves operation_id")

    def test_multiple_correlations(self):
        """Test correlation with multiple issues and corrections."""
        operation_id_1 = str(uuid.uuid4())
        operation_id_2 = str(uuid.uuid4())
        
        content = "Test with https://example1.com and https://example2.com"
        
        issue1 = Issue(
            issue_type="dead_link",
            description="Test issue 1",
            position=10,
            original_text="https://example1.com",
            suggested_text="https://archive.org/example1",
            severity="high",
            operation_id=operation_id_1
        )
        
        issue2 = Issue(
            issue_type="dead_link",
            description="Test issue 2",
            position=35,
            original_text="https://example2.com",
            suggested_text="https://archive.org/example2",
            severity="high",
            operation_id=operation_id_2
        )
        
        corrector = Corrector(content)
        corrections = corrector.apply_corrections([issue1, issue2])
        
        assert len(corrections) == 2
        
        # Verify each correction has the correct operation_id
        operation_ids = [correction.operation_id for correction in corrections]
        assert operation_id_1 in operation_ids
        assert operation_id_2 in operation_ids
        
        print("[OK] Multiple correlations work correctly")

    def test_failed_correction_correlation(self):
        """Test that failed corrections also preserve operation_id."""
        operation_id = str(uuid.uuid4())
        content = "Test content without the target link"
        
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            operation_id=operation_id
        )
        
        corrector = Corrector(content)
        corrections = corrector.apply_corrections([issue])
        
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.applied == False  # Should fail since original_text not in content
        assert correction.operation_id == operation_id
        
        print("[OK] Failed correction preserves operation_id")

    def test_correction_without_operation_id(self):
        """Test backward compatibility: Correction without operation_id."""
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high"
            # No operation_id - backward compatibility
        )
        
        correction = Correction(
            issue=issue,
            applied=True
            # No operation_id - backward compatibility
        )
        
        assert correction.operation_id is None
        assert correction.operation_id == issue.operation_id
        
        print("[OK] Backward compatibility works")

    def test_correction_to_dict_includes_operation_id(self):
        """Test that correction.to_dict() includes operation_id."""
        operation_id = str(uuid.uuid4())
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            operation_id=operation_id
        )
        
        correction = Correction(
            issue=issue,
            applied=True,
            operation_id=operation_id
        )
        
        correction_dict = correction.to_dict()
        assert "operation_id" in correction_dict
        assert correction_dict["operation_id"] == operation_id
        
        print("[OK] Correction.to_dict() includes operation_id")

    def test_correlation_chain(self):
        """Test full correlation chain: Issue → Correction → to_dict."""
        operation_id = str(uuid.uuid4())
        content = "Test with https://example.com"
        
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            operation_id=operation_id
        )
        
        corrector = Corrector(content)
        corrections = corrector.apply_corrections([issue])
        
        correction = corrections[0]
        correction_dict = correction.to_dict()
        
        # Verify the full chain
        assert issue.operation_id == operation_id
        assert correction.operation_id == operation_id
        assert correction_dict["operation_id"] == operation_id
        assert correction_dict["issue"]["operation_id"] == operation_id
        
        print("[OK] Full correlation chain works correctly")


if __name__ == "__main__":
    print("=== Phase 2 Correlation Tests ===\n")
    
    test_class = TestPhase2Correlation()
    
    print("\n--- Test 1: Issue with operation_id ---")
    test_class.test_issue_with_operation_id()
    
    print("\n--- Test 2: Correction with operation_id ---")
    test_class.test_correction_with_operation_id()
    
    print("\n--- Test 3: Corrector preserves operation_id ---")
    test_class.test_corrector_preserves_operation_id()
    
    print("\n--- Test 4: Multiple correlations ---")
    test_class.test_multiple_correlations()
    
    print("\n--- Test 5: Failed correction correlation ---")
    test_class.test_failed_correction_correlation()
    
    print("\n--- Test 6: Backward compatibility ---")
    test_class.test_correction_without_operation_id()
    
    print("\n--- Test 7: Correction.to_dict() includes operation_id ---")
    test_class.test_correction_to_dict_includes_operation_id()
    
    print("\n--- Test 8: Full correlation chain ---")
    test_class.test_correlation_chain()
    
    print("\n=== All Phase 2 Tests Passed ===")
    print("[OK] Issue/Correction correlation is working correctly")
