"""
Test script for Phase 3 corrections (P0, P1, P2 fixes).

This script validates:
- P0-1: Unified AutomationStatus contract between frontend and backend
- P0-2: Scheduler start verification with await
- P0-3: True pause vs stop distinction
- P1-1: Kill Switch synchronization with scheduler state
- P1-2: Double launch prevention
- P1-3: Automatic polling in React (manual verification)
- P1-4: Unified publication queue (SQLite as single source of truth)
- P2-1: Resume endpoint implementation

Full workflow test:
Lancement → Récupération → Analyse → Correction → Queue → Publication → Historique
"""

import sys
import asyncio
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from fastapi.testclient import TestClient
from backend.api.main import app


class TestCorrectionsPhase3:
    """Test Phase 3 corrections."""
    
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
    
    def test_p0_1_automation_status_contract(self):
        """P0-1: Test AutomationStatus contract unification."""
        print("\n=== P0-1: AutomationStatus Contract ===")
        
        try:
            # Test automation status endpoint (correct path: /api/system/automation)
            response = self.client.get("/api/system/automation")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for required fields from frontend contract
                required_fields = [
                    'success', 'status', 'session_id', 'current_step',
                    'articles_processed', 'articles_published', 'articles_error',
                    'category_name', 'started_at'
                ]
                
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    self.log_result("P0-1", True, "All required fields present in AutomationStatus")
                else:
                    self.log_result("P0-1", False, f"Missing fields: {missing_fields}")
            else:
                self.log_result("P0-1", False, f"Status code: {response.status_code}")
                
        except Exception as e:
            self.log_result("P0-1", False, f"Exception: {e}")
    
    def test_p0_2_scheduler_start_verification(self):
        """P0-2: Test scheduler start with verification (code inspection)."""
        print("\n=== P0-2: Scheduler Start Verification ===")
        
        try:
            # Verify the code change by inspecting the system.py file
            with open("backend/api/routes/system.py", "r", encoding="utf-8") as f:
                content = f.read()
                
                # Check if the start endpoint uses await and verification
                if "await scheduler.start()" in content:
                    self.log_result("P0-2", True, "Scheduler start uses await for verification")
                else:
                    self.log_result("P0-2", False, "Scheduler start does not use await")
                
        except Exception as e:
            self.log_result("P0-2", False, f"Exception: {e}")
    
    def test_p0_3_pause_vs_stop_distinction(self):
        """P0-3: Test pause vs stop distinction (code inspection)."""
        print("\n=== P0-3: Pause vs Stop Distinction ===")
        
        try:
            # Verify the code change by inspecting the scheduler.py file
            with open("src/wikipedia_maintenance/orchestrator/scheduler.py", "r", encoding="utf-8") as f:
                content = f.read()
                
                # Check if pause and stop have different implementations
                has_pause = "async def pause" in content and "set_paused(True)" in content
                has_stop = "async def stop" in content and "set_active(False)" in content
                
                if has_pause and has_stop:
                    self.log_result("P0-3", True, "Pause and stop have distinct implementations")
                else:
                    self.log_result("P0-3", False, "Pause and stop implementations not distinct")
                
        except Exception as e:
            self.log_result("P0-3", False, f"Exception: {e}")
    
    def test_p1_1_kill_switch_synchronization(self):
        """P1-1: Test Kill Switch synchronization with scheduler (code inspection)."""
        print("\n=== P1-1: Kill Switch Synchronization ===")
        
        try:
            # Verify the code change by inspecting the scheduler.py file
            with open("src/wikipedia_maintenance/orchestrator/scheduler.py", "r", encoding="utf-8") as f:
                content = f.read()
                
                # Check if scheduler loop checks kill switch from database
                has_kill_switch_check = "kill_switch_manager.is_enabled()" in content
                has_state_file_check = "state.is_active" in content
                
                if has_kill_switch_check and has_state_file_check:
                    self.log_result("P1-1", True, "Scheduler checks Kill Switch from both database and state file")
                else:
                    self.log_result("P1-1", False, "Scheduler does not check Kill Switch from both sources")
                
        except Exception as e:
            self.log_result("P1-1", False, f"Exception: {e}")
    
    def test_p1_2_double_launch_prevention(self):
        """P1-2: Test double launch prevention (code inspection)."""
        print("\n=== P1-2: Double Launch Prevention ===")
        
        try:
            # Verify the code change by inspecting the automation_orchestrator.py file
            with open("src/wikipedia_maintenance/orchestrator/automation_orchestrator.py", "r", encoding="utf-8") as f:
                content = f.read()
                
                # Check if there's a check for running automation before starting
                has_double_launch_check = "is_running" in content or "_running" in content
                
                if has_double_launch_check:
                    self.log_result("P1-2", True, "Automation orchestrator has running state checks")
                else:
                    self.log_result("P1-2", False, "Automation orchestrator lacks running state checks")
                
        except Exception as e:
            self.log_result("P1-2", False, f"Exception: {e}")
    
    def test_p1_4_unified_publication_queue(self):
        """P1-4: Test unified publication queue (SQLite as single source of truth)."""
        print("\n=== P1-4: Unified Publication Queue ===")
        
        try:
            # Check if database exists and has analysis_results table
            from wikipedia_maintenance.utils.database import DatabaseManager
            
            db = DatabaseManager()
            
            # Check if analysis_results table exists
            cursor = db.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_results'")
            
            if cursor.fetchone():
                # Check for pending articles
                cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE status='pending'")
                count = cursor.fetchone()[0]
                
                self.log_result("P1-4", True, f"SQLite queue exists with {count} pending articles")
            else:
                self.log_result("P1-4", False, "analysis_results table not found")
                
        except Exception as e:
            self.log_result("P1-4", False, f"Exception: {e}")
    
    def test_p2_1_resume_endpoint(self):
        """P2-1: Test resume endpoint implementation."""
        print("\n=== P2-1: Resume Endpoint ===")
        
        try:
            # Test resume endpoint exists and is async
            response = self.client.post("/api/system/automation/resume")
            
            if response.status_code == 200:
                data = response.json()
                
                # Should have success field
                if "success" in data:
                    self.log_result("P2-1", True, "Resume endpoint implemented and returns success field")
                else:
                    self.log_result("P2-1", False, "Resume endpoint missing success field")
            else:
                # 404 or other error might mean endpoint doesn't exist
                self.log_result("P2-1", False, f"Resume endpoint error: {response.status_code}")
                
        except Exception as e:
            self.log_result("P2-1", False, f"Exception: {e}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            print("\n✓ ALL TESTS PASSED")
        else:
            print("\n✗ SOME TESTS FAILED")
            print("\nFailed tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("PHASE 3 CORRECTIONS TEST")
    print("=" * 60)
    
    tester = TestCorrectionsPhase3()
    
    # Run all tests
    tester.test_p0_1_automation_status_contract()
    tester.test_p0_2_scheduler_start_verification()
    tester.test_p0_3_pause_vs_stop_distinction()
    tester.test_p1_1_kill_switch_synchronization()
    tester.test_p1_2_double_launch_prevention()
    tester.test_p1_4_unified_publication_queue()
    tester.test_p2_1_resume_endpoint()
    
    # Print summary
    tester.print_summary()


if __name__ == "__main__":
    main()
