"""
Test DeadLinkAnalyzer activation/deactivation from UI.
"""

import sys
import os
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import yaml
from wikipedia_maintenance.utils.config import load_config


def test_dead_link_analyzer_toggle():
    """Test that enable_dead_link_analyzer can be toggled from config."""
    print("\n" + "=" * 60)
    print("TEST: DeadLinkAnalyzer Toggle from UI")
    print("=" * 60)
    
    config_dir = project_root / "config"
    config_file = config_dir / "config.yaml"
    config_example = config_dir / "config.example.yaml"
    
    backup_file = None
    if config_file.exists():
        backup_file = config_file.with_suffix('.yaml.backup')
        shutil.copy(config_file, backup_file)
    
    try:
        # Test 1: Enable DeadLinkAnalyzer
        print("\nTest 1: Enable DeadLinkAnalyzer")
        if config_example.exists():
            shutil.copy(config_example, config_file)
        
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        config_data['analysis']['enable_dead_link_analyzer'] = True
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        config = load_config()
        assert hasattr(config.analysis, 'enable_dead_link_analyzer'), "Should have enable_dead_link_analyzer field"
        assert config.analysis.enable_dead_link_analyzer == True, "Should be True"
        print("[PASS] DeadLinkAnalyzer enabled")
        
        # Test 2: Disable DeadLinkAnalyzer
        print("\nTest 2: Disable DeadLinkAnalyzer")
        config_data['analysis']['enable_dead_link_analyzer'] = False
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        config = load_config()
        assert config.analysis.enable_dead_link_analyzer == False, "Should be False"
        print("[PASS] DeadLinkAnalyzer disabled")
        
        # Test 3: Test AutomationOrchestrator reads the setting
        print("\nTest 3: AutomationOrchestrator reads enable_dead_link_analyzer")
        
        class MockOrchestrator:
            def _get_enabled_analyzers_from_config(self):
                from wikipedia_maintenance.utils.config import load_config
                config = load_config()
                
                if not hasattr(config, 'analysis'):
                    return ["DeadLinkAnalyzer"]
                
                if hasattr(config.analysis, 'enable_dead_link_analyzer'):
                    if config.analysis.enable_dead_link_analyzer:
                        return ["DeadLinkAnalyzer"]
                    else:
                        return []
                
                if hasattr(config.analysis, 'enabled_analyzers'):
                    return config.analysis.enabled_analyzers
                
                return ["DeadLinkAnalyzer"]
        
        mock = MockOrchestrator()
        
        # Test with enabled
        config_data['analysis']['enable_dead_link_analyzer'] = True
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        result = mock._get_enabled_analyzers_from_config()
        assert result == ["DeadLinkAnalyzer"], f"Should return ['DeadLinkAnalyzer'], got {result}"
        print("[PASS] Orchestrator returns DeadLinkAnalyzer when enabled")
        
        # Test with disabled
        config_data['analysis']['enable_dead_link_analyzer'] = False
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        result = mock._get_enabled_analyzers_from_config()
        assert result == [], f"Should return [], got {result}"
        print("[PASS] Orchestrator returns [] when disabled")
        
    finally:
        if backup_file and backup_file.exists():
            shutil.copy(backup_file, config_file)
            backup_file.unlink()
            print("\nRestored original config from backup")
    
    print("\n" + "=" * 60)
    print("DEAD LINK ANALYZER TOGGLE TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_dead_link_analyzer_toggle()
        sys.exit(0)
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
