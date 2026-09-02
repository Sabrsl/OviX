"""
Phase 4 Validation Test Script

Tests the critical fixes made during Phase 4 audit:
1. Import path correction (api.main → backend.api.main)
2. Race condition prevention (launch lock)
3. ReadyToPublish synchronization with scheduler queue
4. Kill Switch verification in AutomationOrchestrator
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from fastapi.testclient import TestClient
from backend.api.main import app


class TestPhase4Corrections:
    """Test Phase 4 critical corrections."""
    
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
    
    def test_import_path_correction(self):
        """Test that import path was corrected."""
        print("\n=== Import Path Correction ===")
        
        try:
            with open("backend/api/routes/system.py", "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check that the import was corrected
            has_correct_import = "from backend.api.main import set_automation_orchestrator" in content
            has_wrong_import = "from api.main import" in content
            
            if has_correct_import and not has_wrong_import:
                self.log_result("Import Path", True, "Import path corrected to backend.api.main")
            else:
                if has_wrong_import:
                    self.log_result("Import Path", False, "Wrong import path still present")
                else:
                    self.log_result("Import Path", False, "Correct import not found")
                
        except Exception as e:
            self.log_result("Import Path", False, f"Exception: {e}")
    
    def test_launch_lock_implementation(self):
        """Test that launch lock was implemented."""
        print("\n=== Launch Lock Implementation ===")
        
        try:
            with open("backend/api/main.py", "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check for launch lock variable and functions
            has_lock_variable = "_automation_launch_lock" in content
            has_get_lock = "get_automation_launch_lock" in content
            has_set_lock = "set_automation_launch_lock" in content
            
            if has_lock_variable and has_get_lock and has_set_lock:
                self.log_result("Launch Lock", True, "Launch lock fully implemented")
            else:
                missing = []
                if not has_lock_variable: missing.append("lock variable")
                if not has_get_lock: missing.append("get function")
                if not has_set_lock: missing.append("set function")
                self.log_result("Launch Lock", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("Launch Lock", False, f"Exception: {e}")
    
    def test_launch_lock_usage_in_endpoint(self):
        """Test that launch lock is used in run-manual endpoint."""
        print("\n=== Launch Lock Usage in Endpoint ===")
        
        try:
            with open("backend/api/routes/system.py", "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check that the endpoint uses the launch lock
            has_lock_check = "get_automation_launch_lock()" in content
            has_lock_set = "set_automation_launch_lock(True)" in content
            has_lock_release = "set_automation_launch_lock(False)" in content
            has_finally_release = "finally:" in content and "set_automation_launch_lock(False)" in content
            
            if has_lock_check and has_lock_set and has_lock_release and has_finally_release:
                self.log_result("Lock Usage", True, "Launch lock properly used with finally block")
            else:
                missing = []
                if not has_lock_check: missing.append("lock check")
                if not has_lock_set: missing.append("lock set")
                if not has_lock_release: missing.append("lock release")
                if not has_finally_release: missing.append("finally block")
                self.log_result("Lock Usage", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("Lock Usage", False, f"Exception: {e}")
    
    def test_ready_to_publish_sync(self):
        """Test that ReadyToPublish synchronizes with scheduler queue."""
        print("\n=== ReadyToPublish Synchronization ===")
        
        try:
            # Check API method exists
            with open("frontend/src/api/articles.api.ts", "r", encoding="utf-8") as f:
                api_content = f.read()
            
            has_pending_queue_method = "getPendingSchedulerQueue" in api_content
            
            # Check React component uses it
            with open("frontend/src/pages/ReadyToPublish.tsx", "r", encoding="utf-8") as f:
                react_content = f.read()
            
            has_pending_queue_call = "getPendingSchedulerQueue()" in react_content
            has_pending_queue_filter = "isInSchedulerQueue" in react_content or "pendingQueueTitles" in react_content
            
            if has_pending_queue_method and has_pending_queue_call and has_pending_queue_filter:
                self.log_result("ReadyToPublish Sync", True, "Synchronization with scheduler queue implemented")
            else:
                missing = []
                if not has_pending_queue_method: missing.append("API method")
                if not has_pending_queue_call: missing.append("API call")
                if not has_pending_queue_filter: missing.append("filter logic")
                self.log_result("ReadyToPublish Sync", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("ReadyToPublish Sync", False, f"Exception: {e}")
    
    def test_kill_switch_verification(self):
        """Test that Kill Switch is verified in AutomationOrchestrator."""
        print("\n=== Kill Switch Verification ===")
        
        try:
            with open("src/wikipedia_maintenance/orchestrator/automation_orchestrator.py", "r", encoding="utf-8") as f:
                content = f.read()
            
            # Count kill switch checks
            kill_switch_checks = content.count("_check_kill_switch()")
            
            # Check that it's checked at critical points
            has_check_in_startup = "_check_kill_switch()" in content and "startup" in content
            has_check_method = "def _check_kill_switch" in content
            
            if kill_switch_checks >= 5 and has_check_method:
                self.log_result("Kill Switch", True, f"Kill Switch verified at {kill_switch_checks} points in AutomationOrchestrator")
            else:
                self.log_result("Kill Switch", False, f"Insufficient checks: {kill_switch_checks} found")
                
        except Exception as e:
            self.log_result("Kill Switch", False, f"Exception: {e}")
    
    def test_double_launch_prevention_api(self):
        """Test that API prevents double launch."""
        print("\n=== Double Launch Prevention API ===")
        
        try:
            # Check that the endpoint checks for existing automation
            with open("backend/api/routes/system.py", "r", encoding="utf-8") as f:
                content = f.read()
            
            has_automation_state_check = "automation_state" in content and "current_state.status in ['running', 'paused']" in content
            has_scheduler_check = "scheduler.is_running()" in content
            has_launch_lock_check = "get_automation_launch_lock()" in content
            
            if has_automation_state_check and has_scheduler_check and has_launch_lock_check:
                self.log_result("Double Launch API", True, "Multiple checks prevent double launch")
            else:
                missing = []
                if not has_automation_state_check: missing.append("automation state check")
                if not has_scheduler_check: missing.append("scheduler check")
                if not has_launch_lock_check: missing.append("launch lock check")
                self.log_result("Double Launch API", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("Double Launch API", False, f"Exception: {e}")
    
    def test_api_endpoints_respond(self):
        """Test that critical API endpoints respond correctly."""
        print("\n=== API Endpoints Response ===")
        
        try:
            # Test health endpoint
            health_response = self.client.get("/api/health")
            health_ok = health_response.status_code == 200
            
            # Test system status
            status_response = self.client.get("/api/system/status")
            status_ok = status_response.status_code == 200
            
            # Test automation status
            automation_response = self.client.get("/api/system/automation")
            automation_ok = automation_response.status_code == 200
            
            # Test scheduler status
            scheduler_response = self.client.get("/api/system/scheduler")
            scheduler_ok = scheduler_response.status_code == 200
            
            if health_ok and status_ok and automation_ok and scheduler_ok:
                self.log_result("API Endpoints", True, "All critical endpoints respond")
            else:
                failed = []
                if not health_ok: failed.append("health")
                if not status_ok: failed.append("status")
                if not automation_ok: failed.append("automation")
                if not scheduler_ok: failed.append("scheduler")
                self.log_result("API Endpoints", False, f"Failed: {failed}")
                
        except Exception as e:
            self.log_result("API Endpoints", False, f"Exception: {e}")
    
    def test_automation_status_contract(self):
        """Test that automation status has required fields."""
        print("\n=== Automation Status Contract ===")
        
        try:
            response = self.client.get("/api/system/automation")
            
            if response.status_code == 200:
                data = response.json()
                required_fields = [
                    "success", "status", "session_id", "current_step",
                    "articles_processed", "articles_published", "articles_error"
                ]
                
                missing = [f for f in required_fields if f not in data]
                
                if not missing:
                    self.log_result("Automation Contract", True, "All required fields present")
                else:
                    self.log_result("Automation Contract", False, f"Missing fields: {missing}")
            else:
                self.log_result("Automation Contract", False, f"Status code: {response.status_code}")
                
        except Exception as e:
            self.log_result("Automation Contract", False, f"Exception: {e}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("PHASE 4 CORRECTIONS TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            print("\n✓ ALL PHASE 4 CORRECTIONS VERIFIED")
        else:
            print("\n✗ SOME PHASE 4 CORRECTIONS FAILED")
            print("\nFailed tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")


def main():
    """Run all Phase 4 correction tests."""
    print("=" * 60)
    print("PHASE 4 CORRECTIONS VALIDATION")
    print("=" * 60)
    
    tester = TestPhase4Corrections()
    
    # Run all tests
    tester.test_import_path_correction()
    tester.test_launch_lock_implementation()
    tester.test_launch_lock_usage_in_endpoint()
    tester.test_ready_to_publish_sync()
    tester.test_kill_switch_verification()
    tester.test_double_launch_prevention_api()
    tester.test_api_endpoints_respond()
    tester.test_automation_status_contract()
    
    # Print summary
    tester.print_summary()


if __name__ == "__main__":
    main()
