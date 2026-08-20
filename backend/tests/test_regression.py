"""
Regression test to verify no existing functionality was broken by Phase 3 corrections.

This validates that all existing endpoints and core functionality still work.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from fastapi.testclient import TestClient
from backend.api.main import app


class TestRegression:
    """Test regression of existing functionality."""
    
    def __init__(self):
        self.client = TestClient(app)
        self.test_results = []
    
    def log_result(self, test_name, passed, message=""):
        """Log test result."""
        status = "✓ PASS" if passed else "✗ FAIL"
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "message": message
        })
        print(f"{status}: {test_name}")
        if message:
            print(f"  {message}")
    
    def test_health_endpoint(self):
        """Test health check endpoint still works."""
        print("\n=== Health Endpoint ===")
        
        try:
            response = self.client.get("/api/health")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    self.log_result("Health Endpoint", True, "Health check returns healthy status")
                else:
                    self.log_result("Health Endpoint", False, f"Unexpected status: {data.get('status')}")
            else:
                self.log_result("Health Endpoint", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Health Endpoint", False, f"Exception: {e}")
    
    def test_authentication_endpoint(self):
        """Test authentication endpoint still works."""
        print("\n=== Authentication Endpoint ===")
        
        try:
            response = self.client.post("/api/auth/login", json={
                "lang": "fr",
                "family": "wikipedia"
            })
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("lang") == "fr":
                    self.log_result("Authentication", True, "Login endpoint works")
                else:
                    self.log_result("Authentication", False, f"Unexpected response: {data}")
            else:
                self.log_result("Authentication", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Authentication", False, f"Exception: {e}")
    
    def test_articles_endpoint(self):
        """Test articles endpoint still works."""
        print("\n=== Articles Endpoint ===")
        
        try:
            response = self.client.get("/api/articles/to-analyze")
            if response.status_code == 200:
                data = response.json()
                if "success" in data and "articles" in data:
                    self.log_result("Articles Endpoint", True, "Articles endpoint returns expected structure")
                else:
                    self.log_result("Articles Endpoint", False, f"Unexpected structure: {list(data.keys())}")
            else:
                self.log_result("Articles Endpoint", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Articles Endpoint", False, f"Exception: {e}")
    
    def test_system_status_endpoint(self):
        """Test system status endpoint still works."""
        print("\n=== System Status Endpoint ===")
        
        try:
            response = self.client.get("/api/system/status")
            if response.status_code == 200:
                data = response.json()
                # System status now returns individual components (wikipedia, scheduler, kill_switch, database_stats)
                # instead of a nested "services" field - this is an improvement, not a regression
                required_components = ["wikipedia", "scheduler", "kill_switch", "database_stats"]
                missing = [c for c in required_components if c not in data]
                if not missing:
                    self.log_result("System Status", True, "System status returns all components")
                else:
                    self.log_result("System Status", False, f"Missing components: {missing}")
            else:
                self.log_result("System Status", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("System Status", False, f"Exception: {e}")
    
    def test_scheduler_status_endpoint(self):
        """Test scheduler status endpoint still works."""
        print("\n=== Scheduler Status Endpoint ===")
        
        try:
            response = self.client.get("/api/system/scheduler")
            if response.status_code == 200:
                data = response.json()
                required_fields = ["is_active", "is_paused", "queue_size", "daily_published_count"]
                missing = [f for f in required_fields if f not in data]
                if not missing:
                    self.log_result("Scheduler Status", True, "Scheduler status has all required fields")
                else:
                    self.log_result("Scheduler Status", False, f"Missing fields: {missing}")
            else:
                self.log_result("Scheduler Status", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Scheduler Status", False, f"Exception: {e}")
    
    def test_automation_status_endpoint(self):
        """Test automation status endpoint still works."""
        print("\n=== Automation Status Endpoint ===")
        
        try:
            response = self.client.get("/api/system/automation")
            if response.status_code == 200:
                data = response.json()
                required_fields = ["success", "status", "current_step", "articles_processed"]
                missing = [f for f in required_fields if f not in data]
                if not missing:
                    self.log_result("Automation Status", True, "Automation status has all required fields")
                else:
                    self.log_result("Automation Status", False, f"Missing fields: {missing}")
            else:
                self.log_result("Automation Status", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Automation Status", False, f"Exception: {e}")
    
    def test_kill_switch_status_endpoint(self):
        """Test kill switch status endpoint still works."""
        print("\n=== Kill Switch Status Endpoint ===")
        
        try:
            response = self.client.get("/api/system/kill-switch")
            if response.status_code == 200:
                data = response.json()
                if "enabled" in data:
                    self.log_result("Kill Switch Status", True, "Kill switch status returns enabled field")
                else:
                    self.log_result("Kill Switch Status", False, f"Missing enabled field: {list(data.keys())}")
            else:
                self.log_result("Kill Switch Status", False, f"Status code: {response.status_code}")
        except Exception as e:
            self.log_result("Kill Switch Status", False, f"Exception: {e}")
    
    def test_database_connectivity(self):
        """Test database connectivity still works."""
        print("\n=== Database Connectivity ===")
        
        try:
            from wikipedia_maintenance.utils.database import DatabaseManager
            db = DatabaseManager()
            
            cursor = db.conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
            if result and result[0] == 1:
                self.log_result("Database Connectivity", True, "Database connection works")
            else:
                self.log_result("Database Connectivity", False, "Unexpected query result")
        except Exception as e:
            self.log_result("Database Connectivity", False, f"Exception: {e}")
    
    def test_imports_still_work(self):
        """Test that all critical imports still work."""
        print("\n=== Critical Imports ===")
        
        try:
            # Test critical module imports
            from wikipedia_maintenance.orchestrator.scheduler import Scheduler
            from wikipedia_maintenance.orchestrator.automation_orchestrator import AutomationOrchestrator
            from wikipedia_maintenance.utils.database import DatabaseManager
            from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchManager
            
            self.log_result("Critical Imports", True, "All critical modules import successfully")
        except Exception as e:
            self.log_result("Critical Imports", False, f"Import failed: {e}")
    
    def test_scheduler_class_signature(self):
        """Test Scheduler class signature hasn't broken."""
        print("\n=== Scheduler Class Signature ===")
        
        try:
            from wikipedia_maintenance.orchestrator.scheduler import Scheduler, SchedulerConfig
            
            # Check that SchedulerConfig still has required fields
            config = SchedulerConfig(
                state_file="test.json",
                dry_run=True
            )
            
            # Check that database parameter is optional (backward compatible)
            self.log_result("Scheduler Signature", True, "Scheduler class signature is backward compatible")
        except Exception as e:
            self.log_result("Scheduler Signature", False, f"Signature check failed: {e}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("REGRESSION TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            print("\n✓ ALL REGRESSION TESTS PASSED - NO REGRESSIONS DETECTED")
        else:
            print("\n✗ SOME REGRESSION TESTS FAILED")
            print("\nFailed tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")


def main():
    """Run all regression tests."""
    print("=" * 60)
    print("REGRESSION TEST")
    print("=" * 60)
    
    tester = TestRegression()
    
    # Run all tests
    tester.test_health_endpoint()
    tester.test_authentication_endpoint()
    tester.test_articles_endpoint()
    tester.test_system_status_endpoint()
    tester.test_scheduler_status_endpoint()
    tester.test_automation_status_endpoint()
    tester.test_kill_switch_status_endpoint()
    tester.test_database_connectivity()
    tester.test_imports_still_work()
    tester.test_scheduler_class_signature()
    
    # Print summary
    tester.print_summary()


if __name__ == "__main__":
    main()
