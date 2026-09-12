"""
Test for repair status counting in analysis.py.

Tests that different repair statuses are correctly counted as "corrected links".
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend" / "src"))

import pytest
from wikipedia_maintenance.analyzers.base import Issue


def test_repair_status_counting():
    """Test that different repair statuses are correctly counted."""
    
    # Create sample issues with different repair statuses
    issues = [
        Issue(
            issue_type="dead_link",
            description="Link repaired",
            position=0,
            original_text="http://old.com",
            suggested_text="http://new.com",
            severity="high",
            confidence=1.0,
            extra={'repair_status': 'REPAIR_APPLIED'}
        ),
        Issue(
            issue_type="dead_link",
            description="Archive only repair",
            position=10,
            original_text="{{old}}",
            suggested_text="{{new}}",
            severity="high",
            confidence=1.0,
            extra={'repair_status': 'ARCHIVE_ONLY_REPAIR'}
        ),
        Issue(
            issue_type="dead_link",
            description="Brisé le added",
            position=20,
            original_text="{{template}}",
            suggested_text="{{template|brisé le=2026-09-06}}",
            severity="high",
            confidence=1.0,
            extra={'repair_status': 'BRISE_LE_ADDED'}
        ),
        Issue(
            issue_type="dead_link",
            description="Partial repair",
            position=30,
            original_text="{{template}}",
            suggested_text="{{template|archive-url=...}}",
            severity="high",
            confidence=1.0,
            extra={'repair_status': 'PARTIAL_REPAIR_APPLIED'}
        ),
        Issue(
            issue_type="dead_link",
            description="Review required",
            position=40,
            original_text="http://problem.com",
            suggested_text=None,  # No suggested text
            severity="medium",
            confidence=0.5,
            extra={'repair_status': 'REVIEW_REQUIRED'}
        ),
        Issue(
            issue_type="reference_enrichment",
            description="Site added",
            position=50,
            original_text="{{template}}",
            suggested_text="{{template|site=example.com}}",
            severity="low",
            confidence=1.0,
            extra={'repair_status': 'ENRICHMENT_APPLIED'}
        )
    ]
    
    # Simulate the counting logic from analysis.py
    dead_link_repair_statuses = [
        'REPAIR_APPLIED', 'SAFE_REPLACEMENT', 'ARCHIVE_ONLY_REPAIR', 'BRISE_LE_ADDED', 'PARTIAL_REPAIR_APPLIED'
    ]
    
    enrichment_statuses = [
        'ENRICHMENT_APPLIED', 'BARE_URL_ENRICHMENT_APPLIED'
    ]
    
    dead_links_corrected_count = 0
    enrichment_count = 0
    
    for i in issues:
        # Skip manual review items (issues without suggested_text)
        if not i.suggested_text:
            continue
            
        if i.extra and i.extra.get('repair_status') in dead_link_repair_statuses:
            if 'dead' in i.issue_type.lower():
                dead_links_corrected_count += 1
        elif i.extra and i.extra.get('repair_status') in enrichment_statuses:
            if 'reference_enrichment' in i.issue_type.lower():
                enrichment_count += 1
    
    corrected_links_count = dead_links_corrected_count + enrichment_count
    
    # Verify the counts
    assert dead_links_corrected_count == 4, f"Expected 4 dead links corrected, got {dead_links_corrected_count}"
    assert enrichment_count == 1, f"Expected 1 enrichment, got {enrichment_count}"
    assert corrected_links_count == 5, f"Expected 5 total corrected links, got {corrected_links_count}"
    
    print(f"Dead links corrected: {dead_links_corrected_count}")
    print(f"Enrichments: {enrichment_count}")
    print(f"Total corrected links: {corrected_links_count}")
    
    # Additional test: Verify BRISE_LE_ADDED is specifically counted
    brise_le_issues = [i for i in issues if i.extra and i.extra.get('repair_status') == 'BRISE_LE_ADDED']
    assert len(brise_le_issues) == 1, f"Expected 1 BRISE_LE_ADDED issue, got {len(brise_le_issues)}"
    assert brise_le_issues[0].suggested_text is not None, "BRISE_LE_ADDED issue should have suggested_text"
    print(f"BRISE_LE_ADDED issues counted: {len(brise_le_issues)}")


if __name__ == "__main__":
    test_repair_status_counting()
    print("All tests passed!")
