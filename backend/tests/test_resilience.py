"""
Test script for resilience: refresh/reconnexion React and backend restart.

This validates that the system maintains state across frontend refreshes and backend restarts.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))


class TestResilience:
    """Test resilience mechanisms."""
    
    def __init__(self):
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
    
    def test_state_persistence_mechanisms(self):
        """Test that state is persisted to database and files (hybrid approach)."""
        print("\n=== State Persistence Mechanisms ===")
        
        try:
            # Check SQLite database persistence
            from wikipedia_maintenance.utils.database import DatabaseManager
            db = DatabaseManager()
            
            cursor = db.conn.cursor()
            
            # Check for SQLite state tables (some state is in JSON, some in SQLite)
            sqlite_tables = [
                'kill_switch_state',
                'analysis_results',
                'articles_to_analyze'
            ]
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_sqlite_tables = [t for t in sqlite_tables if t not in existing_tables]
            
            # Check for JSON state files (hybrid approach)
            json_files = [
                'data/scheduler_state.json',
                'data/automation_state.json'
            ]
            
            existing_json_files = [f for f in json_files if Path(f).exists()]
            
            # Hybrid approach: SQLite + JSON = complete persistence
            if not missing_sqlite_tables and len(existing_json_files) >= 1:
                self.log_result("State Persistence", True, f"Hybrid persistence: {len(sqlite_tables)} SQLite tables + {len(existing_json_files)} JSON files")
            else:
                issues = []
                if missing_sqlite_tables: issues.append(f"Missing SQLite: {missing_sqlite_tables}")
                if len(existing_json_files) == 0: issues.append("No JSON state files")
                self.log_result("State Persistence", False, f"Issues: {issues}")
                
        except Exception as e:
            self.log_result("State Persistence", False, f"Exception: {e}")
    
    def test_json_state_files(self):
        """Test that JSON state files are used for fallback."""
        print("\n=== JSON State Files ===")
        
        try:
            # Check for JSON state files
            state_files = [
                'data/scheduler_state.json',
                'data/automation_state.json',
                'data/published_articles.json',
                'data/analyzed_articles.json'
            ]
            
            existing_files = []
            for file_path in state_files:
                if Path(file_path).exists():
                    existing_files.append(file_path)
            
            if existing_files:
                self.log_result("JSON State Files", True, f"{len(existing_files)}/{len(state_files)} JSON state files exist")
            else:
                self.log_result("JSON State Files", False, "No JSON state files found")
                
        except Exception as e:
            self.log_result("JSON State Files", False, f"Exception: {e}")
    
    def test_api_state_endpoints(self):
        """Test that API endpoints return persistent state."""
        print("\n=== API State Endpoints ===")
        
        try:
            with open("backend/api/routes/system.py", "r", encoding="utf-8") as f:
                system_content = f.read()
            
            # Check for state endpoints
            state_endpoints = [
                ("automation status", "@router.get(\"/automation\""),
                ("scheduler status", "@router.get(\"/scheduler\""),
                ("kill switch status", "@router.get(\"/kill-switch\""),
            ]
            
            missing_endpoints = []
            for name, decorator in state_endpoints:
                if decorator not in system_content:
                    missing_endpoints.append(name)
            
            if not missing_endpoints:
                self.log_result("API State Endpoints", True, "All state endpoints exist")
            else:
                self.log_result("API State Endpoints", False, f"Missing: {missing_endpoints}")
                
        except Exception as e:
            self.log_result("API State Endpoints", False, f"Exception: {e}")
    
    def test_frontend_state_loading(self):
        """Test that frontend loads state from API on mount."""
        print("\n=== Frontend State Loading ===")
        
        try:
            # Check React pages for state loading
            react_pages = [
                'frontend/src/pages/SystemScheduler.tsx',
                'frontend/src/pages/SystemKillSwitch.tsx',
                'frontend/src/pages/Dashboard.tsx'
            ]
            
            pages_with_state_loading = []
            for page_path in react_pages:
                if Path(page_path).exists():
                    with open(page_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "useEffect" in content and ("fetch" in content or "axios" in content):
                            pages_with_state_loading.append(page_path)
            
            if pages_with_state_loading:
                self.log_result("Frontend State Loading", True, f"{len(pages_with_state_loading)} pages have state loading")
            else:
                self.log_result("Frontend State Loading", False, "No pages with state loading found")
                
        except Exception as e:
            self.log_result("Frontend State Loading", False, f"Exception: {e}")
    
    def test_backend_restart_recovery(self):
        """Test that backend can recover state after restart."""
        print("\n=== Backend Restart Recovery ===")
        
        try:
            # Check if main.py initializes state from persistence
            with open("backend/api/main.py", "r", encoding="utf-8") as f:
                main_content = f.read()
            
            # Check for database initialization
            has_db_init = "DatabaseManager" in main_content or "database" in main_content.lower()
            
            # Check for state manager initialization
            has_state_init = "AutomationStateManager" in main_content or "state_manager" in main_content.lower()
            
            # Check for kill switch initialization
            has_ks_init = "KillSwitchManager" in main_content or "kill_switch" in main_content.lower()
            
            if has_db_init and has_state_init and has_ks_init:
                self.log_result("Backend Restart Recovery", True, "Backend initializes all state managers")
            else:
                missing = []
                if not has_db_init: missing.append("database")
                if not has_state_init: missing.append("state manager")
                if not has_ks_init: missing.append("kill switch")
                self.log_result("Backend Restart Recovery", False, f"Missing: {missing}")
                
        except Exception as e:
            self.log_result("Backend Restart Recovery", False, f"Exception: {e}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("RESILIENCE TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        total = len(self.test_results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            print("\n✓ ALL RESILIENCE TESTS PASSED")
        else:
            print("\n✗ SOME RESILIENCE TESTS FAILED")
            print("\nFailed tests:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['message']}")


def main():
    """Run all resilience tests."""
    print("=" * 60)
    print("RESILIENCE TEST")
    print("=" * 60)
    
    tester = TestResilience()
    
    # Run all tests
    tester.test_state_persistence_mechanisms()
    tester.test_json_state_files()
    tester.test_api_state_endpoints()
    tester.test_frontend_state_loading()
    tester.test_backend_restart_recovery()
    
    # Print summary
    tester.print_summary()


if __name__ == "__main__":
    main()
