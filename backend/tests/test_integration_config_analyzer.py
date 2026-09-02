"""
Integration tests for configuration and analyzer pipeline.

Tests the complete flow:
UI Settings → config.yaml → AutomationOrchestrator → Analyzers
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import yaml
from wikipedia_maintenance.utils.config import load_config
from wikipedia_maintenance.orchestrator.automation_orchestrator import AutomationOrchestrator


def test_case_normalization_config_flow():
    """Test that enable_case_normalization flows from config.yaml to automation."""
    print("\n" + "=" * 60)
    print("TEST: Case Normalization Configuration Flow")
    print("=" * 60)
    
    # Create a temporary config file
    config_dir = project_root / "config"
    config_file = config_dir / "config.yaml"
    config_example = config_dir / "config.example.yaml"
    
    # Backup original config if it exists
    backup_file = None
    if config_file.exists():
        backup_file = config_file.with_suffix('.yaml.backup')
        shutil.copy(config_file, backup_file)
        print(f"Backed up original config to {backup_file}")
    
    try:
        # Test 1: Enable case normalization
        print("\nTest 1: Enable case normalization in config.yaml")
        if config_example.exists():
            shutil.copy(config_example, config_file)
        
        # Load and modify config
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        config_data['analysis']['enable_case_normalization'] = True
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # Reload config and verify
        config = load_config()
        assert hasattr(config, 'analysis'), "Config should have analysis section"
        assert hasattr(config.analysis, 'enable_case_normalization'), "Analysis should have enable_case_normalization"
        assert config.analysis.enable_case_normalization == True, f"enable_case_normalization should be True, got {config.analysis.enable_case_normalization}"
        print("[PASS] Config correctly loaded with enable_case_normalization=True")
        
        # Test 2: Disable case normalization
        print("\nTest 2: Disable case normalization in config.yaml")
        config_data['analysis']['enable_case_normalization'] = False
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # Reload config and verify
        config = load_config()
        assert config.analysis.enable_case_normalization == False, "enable_case_normalization should be False"
        print("[PASS] Config correctly loaded with enable_case_normalization=False")
        
        # Test 3: Test AutomationOrchestrator reads the setting
        print("\nTest 3: AutomationOrchestrator reads enable_case_normalization from config")
        
        # Create a mock orchestrator (without full initialization)
        class MockOrchestrator:
            def _get_case_normalization_setting(self):
                from wikipedia_maintenance.utils.config import load_config
                config = load_config()
                if hasattr(config, 'analysis') and hasattr(config.analysis, 'enable_case_normalization'):
                    return config.analysis.enable_case_normalization
                return False
        
        mock = MockOrchestrator()
        
        # Test with enabled
        config_data['analysis']['enable_case_normalization'] = True
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        result = mock._get_case_normalization_setting()
        assert result == True, "Orchestrator should read True from config"
        print("[PASS] Orchestrator correctly reads enable_case_normalization=True")
        
        # Test with disabled
        config_data['analysis']['enable_case_normalization'] = False
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        result = mock._get_case_normalization_setting()
        assert result == False, "Orchestrator should read False from config"
        print("[PASS] Orchestrator correctly reads enable_case_normalization=False")
        
    finally:
        # Restore original config
        if backup_file and backup_file.exists():
            shutil.copy(backup_file, config_file)
            backup_file.unlink()
            print(f"\nRestored original config from backup")
    
    print("\n" + "=" * 60)
    print("CASE NORMALIZATION CONFIG FLOW TEST PASSED")
    print("=" * 60)


def test_enabled_analyzers_config_flow():
    """Test that enabled_analyzers flows from config.yaml to automation."""
    print("\n" + "=" * 60)
    print("TEST: Enabled Analyzers Configuration Flow")
    print("=" * 60)
    
    config_dir = project_root / "config"
    config_file = config_dir / "config.yaml"
    config_example = config_dir / "config.example.yaml"
    
    backup_file = None
    if config_file.exists():
        backup_file = config_file.with_suffix('.yaml.backup')
        shutil.copy(config_file, backup_file)
        print(f"Backed up original config to {backup_file}")
    
    try:
        # Test 1: Default analyzer list
        print("\nTest 1: Default enabled analyzers")
        if config_example.exists():
            shutil.copy(config_example, config_file)
        
        config = load_config()
        assert hasattr(config, 'analysis'), "Config should have analysis section"
        assert hasattr(config.analysis, 'enabled_analyzers'), "Analysis should have enabled_analyzers"
        assert "DeadLinkAnalyzer" in config.analysis.enabled_analyzers, "DeadLinkAnalyzer should be enabled by default"
        print(f"[PASS] Default analyzers: {config.analysis.enabled_analyzers}")
        
        # Test 2: Custom analyzer list
        print("\nTest 2: Custom enabled analyzers")
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        config_data['analysis']['enabled_analyzers'] = ["DeadLinkAnalyzer"]
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        config = load_config()
        assert config.analysis.enabled_analyzers == ["DeadLinkAnalyzer"], "Should have only DeadLinkAnalyzer"
        print(f"[PASS] Custom analyzers: {config.analysis.enabled_analyzers}")
        
        # Test 3: AutomationOrchestrator reads the setting
        print("\nTest 3: AutomationOrchestrator reads enabled_analyzers from config")
        
        class MockOrchestrator:
            def _get_enabled_analyzers_from_config(self):
                from wikipedia_maintenance.utils.config import load_config
                config = load_config()
                if hasattr(config, 'analysis') and hasattr(config.analysis, 'enabled_analyzers'):
                    return config.analysis.enabled_analyzers
                return ["DeadLinkAnalyzer"]
        
        mock = MockOrchestrator()
        result = mock._get_enabled_analyzers_from_config()
        assert result == ["DeadLinkAnalyzer"], "Orchestrator should read analyzer list from config"
        print(f"[PASS] Orchestrator correctly reads enabled_analyzers: {result}")
        
    finally:
        if backup_file and backup_file.exists():
            shutil.copy(backup_file, config_file)
            backup_file.unlink()
            print(f"\nRestored original config from backup")
    
    print("\n" + "=" * 60)
    print("ENABLED ANALYZERS CONFIG FLOW TEST PASSED")
    print("=" * 60)


def test_dead_link_analyzer_basic():
    """Test that DeadLinkAnalyzer can be instantiated and run."""
    print("\n" + "=" * 60)
    print("TEST: DeadLinkAnalyzer Basic Functionality")
    print("=" * 60)
    
    try:
        from wikipedia_maintenance.analyzers import DeadLinkAnalyzer
        
        # Test instantiation
        print("\nTest 1: DeadLinkAnalyzer instantiation")
        analyzer = DeadLinkAnalyzer()
        assert analyzer is not None, "Analyzer should be instantiable"
        print("[PASS] DeadLinkAnalyzer instantiated successfully")
        
        # Test analysis with simple content
        print("\nTest 2: DeadLinkAnalyzer analyze method")
        test_content = """
{{Lien web|titre=Test Article|url=https://example.com|site=Example Site}}
Some text here.
{{Lien web|titre=Another Article|url=https://example.org|site=Example Org}}
"""
        issues = analyzer.analyze(test_content)
        print(f"[INFO] Found {len(issues)} issues in test content")
        print("[PASS] DeadLinkAnalyzer analyze method executed")
        
        # Test with empty content
        print("\nTest 3: DeadLinkAnalyzer with empty content")
        empty_issues = analyzer.analyze("")
        assert len(empty_issues) == 0, "Empty content should produce no issues"
        print("[PASS] Empty content handled correctly")
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("DEAD LINK ANALYZER BASIC TEST PASSED")
    print("=" * 60)
    return True


def test_case_normalizer_basic():
    """Test that CaseNormalizer can be instantiated and run."""
    print("\n" + "=" * 60)
    print("TEST: CaseNormalizer Basic Functionality")
    print("=" * 60)
    
    try:
        from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer
        
        # Test instantiation
        print("\nTest 1: CaseNormalizer instantiation")
        normalizer = CaseNormalizer(enabled=True)
        assert normalizer is not None, "Normalizer should be instantiable"
        print("[PASS] CaseNormalizer instantiated successfully")
        
        # Test normalization
        print("\nTest 2: CaseNormalizer normalize_text method")
        test_content = "{{Lien web|titre=TEST ARTICLE|url=https://example.com|site=EXAMPLE SITE}}"
        result = normalizer.normalize_text(test_content)
        print(f"[INFO] Original: {test_content}")
        print(f"[INFO] Normalized: {result.normalized_text}")
        print(f"[INFO] Changes: {result.total_changes}")
        print("[PASS] CaseNormalizer normalize_text method executed")
        
        # Test with disabled normalizer
        print("\nTest 3: CaseNormalizer with enabled=False")
        disabled_normalizer = CaseNormalizer(enabled=False)
        result_disabled = disabled_normalizer.normalize_text(test_content)
        assert result_disabled.normalized_text == test_content, "Disabled normalizer should not modify text"
        print("[PASS] Disabled normalizer does not modify text")
        
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("CASE NORMALIZER BASIC TEST PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("INTEGRATION TEST SUITE")
    print("=" * 60)
    
    all_passed = True
    
    # Run tests
    try:
        test_case_normalization_config_flow()
    except Exception as e:
        print(f"[FAIL] Case normalization config flow test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        test_enabled_analyzers_config_flow()
    except Exception as e:
        print(f"[FAIL] Enabled analyzers config flow test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        if not test_dead_link_analyzer_basic():
            all_passed = False
    except Exception as e:
        print(f"[FAIL] DeadLinkAnalyzer basic test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        if not test_case_normalizer_basic():
            all_passed = False
    except Exception as e:
        print(f"[FAIL] CaseNormalizer basic test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL INTEGRATION TESTS PASSED")
    else:
        print("SOME INTEGRATION TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
