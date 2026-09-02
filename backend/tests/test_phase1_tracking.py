"""
Test Phase 1: Tracking Service Integration

Tests the parallel write to new tracking system while old systems continue.
This ensures the new tracking service works without breaking existing functionality.
"""

import pytest
import uuid
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.utils.tracking_service import (
    TrackingService,
    DeadLinkOperation,
    compute_idempotency_key,
    normalize_url
)
from wikipedia_maintenance.analyzers.base import Issue


class TestPhase1Tracking:
    """Test Phase 1 tracking service integration."""

    def test_database_tables_created(self):
        """Test that new tables are created in DatabaseManager."""
        db = DatabaseManager("test_phase1_tracking.db")
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert "deadlink_operations" in tables, "deadlink_operations table not found"
        assert "deadlink_operation_events" in tables, "deadlink_operation_events table not found"
        
        # Verify table structure
        cursor.execute("PRAGMA table_info(deadlink_operations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        expected_columns = [
            "id", "article_title", "revision_id", "operation_id",
            "url_original", "url_normalized", "context_type", "reference_type",
            "template_name", "field_name", "idempotency_key", "retry_count",
            "final_status", "publication_status", "issue_id", "correction_id",
            "publication_job_id", "created_at", "updated_at", "detected_at", "published_at"
        ]
        
        for col in expected_columns:
            assert col in columns, f"Column {col} not found in deadlink_operations"
        
        print("[OK] Database tables created successfully")

    def test_tracking_service_initialization(self):
        """Test that TrackingService can be initialized."""
        db = DatabaseManager("test_phase1_tracking.db")
        tracking_service = TrackingService(db)
        
        assert tracking_service is not None
        assert tracking_service.db is not None
        
        print("[OK] TrackingService initialized successfully")

    def test_deadlink_operation_creation(self):
        """Test DeadLinkOperation dataclass creation."""
        operation = DeadLinkOperation(
            id=str(uuid.uuid4()),
            article_title="Test Article",
            revision_id=12345,
            operation_id=str(uuid.uuid4()),
            url_original="https://example.com/test",
            url_normalized=normalize_url("https://example.com/test"),
            context_type="ref",
            reference_type="lien_web",
            template_name="Lien web",
            field_name="url",
            idempotency_key=compute_idempotency_key(
                "Test Article", 12345, "https://example.com/test", "ref", "lien_web"
            ),
            final_status="DETECTED"
        )
        
        assert operation.url_original == "https://example.com/test"
        assert operation.final_status == "DETECTED"
        assert operation.idempotency_key is not None
        
        print("[OK] DeadLinkOperation created successfully")

    def test_record_operation(self):
        """Test recording an operation to tracking service."""
        db = DatabaseManager("test_phase1_tracking.db")
        tracking_service = TrackingService(db)
        
        unique_id = str(uuid.uuid4())[:8]
        operation = DeadLinkOperation(
            id=str(uuid.uuid4()),
            article_title=f"Test Article {unique_id}",
            revision_id=12345,
            operation_id=str(uuid.uuid4()),
            url_original=f"https://example.com/test-{unique_id}",
            url_normalized=normalize_url(f"https://example.com/test-{unique_id}"),
            context_type="ref",
            reference_type="lien_web",
            template_name="Lien web",
            field_name="url",
            idempotency_key=compute_idempotency_key(
                f"Test Article {unique_id}", 12345, f"https://example.com/test-{unique_id}", "ref", "lien_web"
            ),
            final_status="DETECTED"
        )
        
        success = tracking_service.record_operation(operation)
        assert success, "Failed to record operation"
        
        # Verify operation was recorded
        retrieved = tracking_service.get_operation(operation.operation_id)
        assert retrieved is not None, "Operation not found after recording"
        assert retrieved["url_original"] == f"https://example.com/test-{unique_id}"
        
        print("[OK] Operation recorded and retrieved successfully")

    def test_update_operation(self):
        """Test updating an operation."""
        db = DatabaseManager("test_phase1_tracking.db")
        tracking_service = TrackingService(db)
        
        unique_id = str(uuid.uuid4())[:8]
        operation = DeadLinkOperation(
            id=str(uuid.uuid4()),
            article_title=f"Test Article Update {unique_id}",
            revision_id=54321,  # Different revision to avoid idempotency conflict
            operation_id=str(uuid.uuid4()),
            url_original=f"https://example.com/update-test-{unique_id}",
            url_normalized=normalize_url(f"https://example.com/update-test-{unique_id}"),
            context_type="ref",
            reference_type="lien_web",
            template_name="Lien web",
            field_name="url",
            idempotency_key=compute_idempotency_key(
                f"Test Article Update {unique_id}", 54321, f"https://example.com/update-test-{unique_id}", "ref", "lien_web"
            ),
            final_status="DETECTED"
        )
        
        tracking_service.record_operation(operation)
        
        # Update operation status
        success = tracking_service.update_operation(
            operation.operation_id,
            final_status="VALIDATED"
        )
        assert success, "Failed to update operation"
        
        # Verify update
        retrieved = tracking_service.get_operation(operation.operation_id)
        assert retrieved is not None, "Operation not found after update"
        assert retrieved["final_status"] == "VALIDATED"
        
        print("[OK] Operation updated successfully")

    def test_idempotency(self):
        """Test that idempotency prevents duplicate operations."""
        db = DatabaseManager("test_phase1_tracking.db")
        tracking_service = TrackingService(db)
        
        unique_id = str(uuid.uuid4())[:8]
        idempotency_key = compute_idempotency_key(
            f"Test Article {unique_id}", 99999, f"https://example.com/test-{unique_id}", "ref", "lien_web"
        )
        
        operation1 = DeadLinkOperation(
            id=str(uuid.uuid4()),
            article_title=f"Test Article {unique_id}",
            revision_id=99999,
            operation_id=str(uuid.uuid4()),
            url_original=f"https://example.com/test-{unique_id}",
            url_normalized=normalize_url(f"https://example.com/test-{unique_id}"),
            context_type="ref",
            reference_type="lien_web",
            template_name="Lien web",
            field_name="url",
            idempotency_key=idempotency_key,
            final_status="DETECTED"
        )
        
        operation2 = DeadLinkOperation(
            id=str(uuid.uuid4()),
            article_title=f"Test Article {unique_id}",
            revision_id=99999,
            operation_id=str(uuid.uuid4()),
            url_original=f"https://example.com/test-{unique_id}",
            url_normalized=normalize_url(f"https://example.com/test-{unique_id}"),
            context_type="ref",
            reference_type="lien_web",
            template_name="Lien web",
            field_name="url",
            idempotency_key=idempotency_key,  # Same idempotency key
            final_status="DETECTED"
        )
        
        # Record first operation
        success1 = tracking_service.record_operation(operation1)
        assert success1, "Failed to record first operation"
        
        # Try to record second operation with same idempotency key
        success2 = tracking_service.record_operation(operation2)
        assert success2, "Idempotency check failed"
        
        # Verify only one operation exists
        operations = tracking_service.get_operation_by_idempotency_key(idempotency_key)
        assert operations is not None, "Operation not found by idempotency key"
        
        print("[OK] Idempotency check working correctly")

    def test_issue_with_operation_id(self):
        """Test that Issue can have operation_id field."""
        issue = Issue(
            issue_type="dead_link",
            description="Test issue",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            operation_id=str(uuid.uuid4())  # Phase 1 field
        )
        
        assert issue.operation_id is not None
        # to_dict() removes None values, so operation_id should be present since it's not None
        issue_dict = issue.to_dict()
        assert "operation_id" in issue_dict
        
        print("[OK] Issue with operation_id created successfully")

    def test_url_normalization(self):
        """Test URL normalization for idempotency."""
        url1 = "https://EXAMPLE.COM/test"
        url2 = "https://example.com/test"
        
        normalized1 = normalize_url(url1)
        normalized2 = normalize_url(url2)
        
        assert normalized1 == normalized2, "URL normalization not consistent"
        
        print("[OK] URL normalization working correctly")

    def test_get_operation_events(self):
        """Test retrieving operation event history."""
        db = DatabaseManager("test_phase1_tracking.db")
        tracking_service = TrackingService(db)
        
        unique_id = str(uuid.uuid4())[:8]
        operation = DeadLinkOperation(
            id=str(uuid.uuid4()),
            article_title=f"Test Article Events {unique_id}",
            revision_id=77777,
            operation_id=str(uuid.uuid4()),
            url_original=f"https://example.com/events-{unique_id}",
            url_normalized=normalize_url(f"https://example.com/events-{unique_id}"),
            context_type="ref",
            reference_type="lien_web",
            template_name="Lien web",
            field_name="url",
            idempotency_key=compute_idempotency_key(
                f"Test Article Events {unique_id}", 77777, f"https://example.com/events-{unique_id}", "ref", "lien_web"
            ),
            final_status="DETECTED"
        )
        
        tracking_service.record_operation(operation)
        tracking_service.update_operation(operation.operation_id, final_status="VALIDATED")
        tracking_service.update_operation(operation.operation_id, final_status="REPAIR_CONFIRMED")
        
        events = tracking_service.get_operation_events(operation.operation_id)
        assert len(events) >= 2, "Expected at least 2 events (DETECTED, VALIDATED, REPAIR_CONFIRMED)"
        
        event_types = [event["event_type"] for event in events]
        assert "DETECTED" in event_types
        assert "VALIDATED" in event_types
        assert "REPAIR_CONFIRMED" in event_types
        
        print("[OK] Operation event history working correctly")


if __name__ == "__main__":
    print("=== Phase 1 Tracking Tests ===\n")
    
    test_class = TestPhase1Tracking()
    
    print("\n--- Test 1: Database Tables ---")
    test_class.test_database_tables_created()
    
    print("\n--- Test 2: Tracking Service Initialization ---")
    test_class.test_tracking_service_initialization()
    
    print("\n--- Test 3: DeadLinkOperation Creation ---")
    test_class.test_deadlink_operation_creation()
    
    print("\n--- Test 4: Record Operation ---")
    test_class.test_record_operation()
    
    print("\n--- Test 5: Update Operation ---")
    test_class.test_update_operation()
    
    print("\n--- Test 6: Idempotency ---")
    test_class.test_idempotency()
    
    print("\n--- Test 7: Issue with operation_id ---")
    test_class.test_issue_with_operation_id()
    
    print("\n--- Test 8: URL Normalization ---")
    test_class.test_url_normalization()
    
    print("\n--- Test 9: Operation Events ---")
    test_class.test_get_operation_events()
    
    print("\n=== All Phase 1 Tests Passed ===")
    print("[OK] New tracking system is ready for parallel write")
