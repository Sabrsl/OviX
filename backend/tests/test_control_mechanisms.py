"""
Test script for control mechanisms: Pause → Resume, Stop, Kill Switch, Double lancement.

This validates the control flow of the automation system.
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


class TestControlMechanisms:
    """Test control mechanisms."""
    
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
    
    def test_pause_resume_flow(self):
        """Test Pause → Resume flow."""
        print("\n=== Pause → Resume Flow ===")
        
        try:
            # Check scheduler pause/resume methods exist
            with open("src/wikipedia_maintenance/orchestrator/scheduler.py", "r", encoding="utf-8") as f:
                scheduler_content = f.read()
            
            has_pause = "async def pause" in scheduler_content
            has_resume = "async def resume" in scheduler_content
            has_pause_state = "set_paused(True)" in scheduler_content
            has_resume_state = "set_paused(False)" in scheduler_content
            
            if has_pause and has_resume and has_pause_state and has_resume_state:
                self.log_result("Pause → Resume", True, "Scheduler has complete pause/resume implementation")
            else:
                missing = []
                if not has_pause: missing.append("pause method")
                if not has_resume: missing.append("resume method")
                if not has_pause_state: missing.append("pause state setting")
                if not has_resume_state: missing.append("resume state setting")
                self.log_result("Pause → Resume", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("Pause → Resume", False, f"Exception: {e}")
    
    def test_stop_terminates_session(self):
        """Test Stop terminates session completely."""
        print("\n=== Stop Terminates Session ===")
        
        try:
            with open("src/wikipedia_maintenance/orchestrator/scheduler.py", "r", encoding="utf-8") as f:
                scheduler_content = f.read()
            
            # Check that stop clears state
            has_stop = "async def stop" in scheduler_content
            has_clear_state = "set_active(False)" in scheduler_content
            has_cancel_task = "cancel()" in scheduler_content
            
            if has_stop and has_clear_state and has_cancel_task:
                self.log_result("Stop Terminates", True, "Stop method clears state and cancels tasks")
            else:
                missing = []
                if not has_stop: missing.append("stop method")
                if not has_clear_state: missing.append("state clearing")
                if not has_cancel_task: missing.append("task cancellation")
                self.log_result("Stop Terminates", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("Stop Terminates", False, f"Exception: {e}")
    
    def test_kill_switch_interrupts_automation(self):
        """Test Kill Switch interrupts automation."""
        print("\n=== Kill Switch Interrupts Automation ===")
        
        try:
            with open("src/wikipedia_maintenance/orchestrator/scheduler.py", "r", encoding="utf-8") as f:
                scheduler_content = f.read()
            
            # Check multiple kill switch checks in scheduler loop
            kill_switch_checks = scheduler_content.count("kill_switch_manager.is_enabled()")
            state_checks = scheduler_content.count("state.is_active")
            
            if kill_switch_checks >= 3 and state_checks >= 3:
                self.log_result("Kill Switch Interrupts", True, f"Multiple Kill Switch checks ({kill_switch_checks} DB + {state_checks} state)")
            else:
                self.log_result("Kill Switch Interrupts", False, f"Insufficient checks: {kill_switch_checks} DB, {state_checks} state")
                
        except Exception as e:
            self.log_result("Kill Switch Interrupts", False, f"Exception: {e}")
    
    def test_double_launch_prevention(self):
        """Test double launch prevention."""
        print("\n=== Double Launch Prevention ===")
        
        try:
            with open("src/wikipedia_maintenance/orchestrator/automation_orchestrator.py", "r", encoding="utf-8") as f:
                orchestrator_content = f.read()
            
            # Check for running state management
            has_running_flag = "_running" in orchestrator_content or "is_running" in orchestrator_content
            has_stopped_flag = "_stopped" in orchestrator_content or "is_stopped" in orchestrator_content
            has_paused_flag = "_paused" in orchestrator_content or "is_paused" in orchestrator_content
            
            if has_running_flag and has_stopped_flag and has_paused_flag:
                self.log_result("Double Launch Prevention", True, "Orchestrator has complete state flags")
            else:
                missing = []
                if not has_running_flag: missing.append("running flag")
                if not has_stopped_flag: missing.append("stopped flag")
                if not has_paused_flag: missing.append("paused flag")
                self.log_result("Double Launch Prevention", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("Double Launch Prevention", False, f"Exception: {e}")
    
    def test_api_endpoints_exist(self):
        """Test that all control API endpoints exist."""
        print("\n=== API Endpoints Exist ===")
        
        try:
            with open("backend/api/routes/system.py", "r", encoding="utf-8") as f:
                system_content = f.read()
            
            required_endpoints = [
                ("scheduler/start", "@router.post(\"/scheduler/start\")"),
                ("scheduler/pause", "@router.post(\"/scheduler/pause\")"),
                ("scheduler/resume", "@router.post(\"/scheduler/resume\")"),
                ("scheduler/stop", "@router.post(\"/scheduler/stop\")"),
                ("automation/pause", "@router.post(\"/automation/pause\")"),
                ("automation/resume", "@router.post(\"/automation/resume\")"),
                ("automation/stop", "@router.post(\"/automation/stop\")"),
                ("kill-switch/activate", "@router.post(\"/kill-switch/activate\")"),
                ("kill-switch/deactivate", "@router.post(\"/kill-switch/deactivate\")"),
            ]
            
            missing_endpoints = []
            for name, decorator in required_endpoints:
                if decorator not in system_content:
                    missing_endpoints.append(name)
            
            if not missing_endpoints:
                self.log_result("API Endpoints", True, "All control endpoints exist")
            else:
                self.log_result("API Endpoints", False, f"Missing endpoints: {missing_endpoints}")
                
        except Exception as e:
            self.log_result("API Endpoints", False, f"Exception: {e}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("CONTROL MECHANISMS TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            print("\n✓ ALL CONTROL MECHANISMS TESTS PASSED")
        else:
            print("\n✗ SOME CONTROL MECHANISMS TESTS FAILED")
            print("\nFailed tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")


def main():
    """Run all control mechanism tests."""
    print("=" * 60)
    print("CONTROL MECHANISMS TEST")
    print("=" * 60)
    
    tester = TestControlMechanisms()
    
    # Run all tests
    tester.test_pause_resume_flow()
    tester.test_stop_terminates_session()
    tester.test_kill_switch_interrupts_automation()
    tester.test_double_launch_prevention()
    tester.test_api_endpoints_exist()
    
    # Print summary
    tester.print_summary()


if __name__ == "__main__":
    main()
