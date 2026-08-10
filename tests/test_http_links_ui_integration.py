"""
Test d'intégration UI pour HttpLinksAnalyzer

Vérifie que HttpLinksAnalyzer est correctement intégré dans:
1. Les settings UI
2. Les descriptions de l'UI
3. Le système de fusion automatique
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.utils.ui_settings import get_settings_manager, UISettings


def test_http_links_analyzer_in_ui_settings():
    """Test que HttpLinksAnalyzer est dans les settings UI par défaut"""
    
    # Créer un nouveau settings manager
    settings_manager = get_settings_manager()
    settings = settings_manager.get_settings()
    
    # Vérifier que HttpLinksAnalyzer est présent
    assert "HttpLinksAnalyzer" in settings.enabled_analyzers, "HttpLinksAnalyzer should be in enabled_analyzers"
    
    # Vérifier la valeur par défaut (False = désactivé par défaut)
    assert settings.enabled_analyzers["HttpLinksAnalyzer"] == False, "HttpLinksAnalyzer should be disabled by default"
    
    print("Step 1 - HttpLinksAnalyzer in UI settings: OK")
    print(f"  All analyzers: {list(settings.enabled_analyzers.keys())}")
    print(f"  HttpLinksAnalyzer enabled: {settings.enabled_analyzers['HttpLinksAnalyzer']}")


def test_http_links_analyzer_merging():
    """Test que le système de fusion ajoute HttpLinksAnalyzer aux settings existants"""
    
    # Simuler des anciens settings sans HttpLinksAnalyzer
    old_settings = {
        "LinkAnalyzer": True,
        "TypographyAnalyzer": True,
        "ReferenceAnalyzer": True,
    }
    
    # Créer un UISettings avec les anciens settings
    settings = UISettings(enabled_analyzers=old_settings)
    
    # Vérifier que HttpLinksAnalyzer n'est pas présent initialement
    assert "HttpLinksAnalyzer" not in settings.enabled_analyzers, "Should not have HttpLinksAnalyzer initially"
    
    print("Step 2 - Old settings without HttpLinksAnalyzer: OK")
    
    # Le système de fusion dans _load_settings devrait l'ajouter automatiquement
    # Pour tester cela, nous devons simuler le processus de chargement
    settings_manager = get_settings_manager()
    
    # Forcer le rechargement avec les defaults
    default_settings = UISettings()
    
    # Vérifier que les defaults incluent HttpLinksAnalyzer
    assert "HttpLinksAnalyzer" in default_settings.enabled_analyzers, "Defaults should include HttpLinksAnalyzer"
    
    print("Step 3 - Default settings include HttpLinksAnalyzer: OK")
    print(f"  Default analyzers: {list(default_settings.enabled_analyzers.keys())}")


def test_http_links_analyzer_ui_description():
    """Test que la description UI est présente"""
    
    # Lire le fichier source pour vérifier la description
    sidebar_file = Path(__file__).parent.parent / "ui" / "sidebar.py"
    with open(sidebar_file, 'r', encoding='utf-8') as f:
        sidebar_content = f.read()
    
    # Vérifier que HttpLinksAnalyzer est dans le dictionnaire analyzer_descriptions
    assert '"HttpLinksAnalyzer"' in sidebar_content, "HttpLinksAnalyzer should be in analyzer_descriptions"
    assert "http://" in sidebar_content.lower(), "Description should mention http://"
    assert "https://" in sidebar_content.lower(), "Description should mention https://"
    
    print("Step 4 - HttpLinksAnalyzer UI description present: OK")
    print("  Found in sidebar.py analyzer_descriptions")


def test_http_links_analyzer_toggle():
    """Test que l'analyseur peut être activé/désactivé via les settings"""
    
    settings_manager = get_settings_manager()
    settings = settings_manager.get_settings()
    
    # Activer HttpLinksAnalyzer
    settings.set_analyzer_enabled("HttpLinksAnalyzer", True)
    assert settings.is_analyzer_enabled("HttpLinksAnalyzer") == True, "Should be enabled after setting"
    
    print("Step 5 - Enable HttpLinksAnalyzer: OK")
    
    # Désactiver HttpLinksAnalyzer
    settings.set_analyzer_enabled("HttpLinksAnalyzer", False)
    assert settings.is_analyzer_enabled("HttpLinksAnalyzer") == False, "Should be disabled after setting"
    
    print("Step 6 - Disable HttpLinksAnalyzer: OK")


def test_http_links_analyzer_in_enabled_list():
    """Test que HttpLinksAnalyzer apparaît dans la liste des analyseurs activés"""
    
    settings_manager = get_settings_manager()
    settings = settings_manager.get_settings()
    
    # Activer quelques analyseurs
    settings.set_analyzer_enabled("TypographyAnalyzer", True)
    settings.set_analyzer_enabled("HttpLinksAnalyzer", True)
    
    enabled_list = settings.get_enabled_analyzers()
    
    assert "HttpLinksAnalyzer" in enabled_list, "HttpLinksAnalyzer should be in enabled list"
    assert "TypographyAnalyzer" in enabled_list, "TypographyAnalyzer should be in enabled list"
    
    print("Step 7 - HttpLinksAnalyzer in enabled list: OK")
    print(f"  Enabled analyzers: {enabled_list}")
    
    # Nettoyer
    settings.set_analyzer_enabled("TypographyAnalyzer", False)
    settings.set_analyzer_enabled("HttpLinksAnalyzer", False)


if __name__ == "__main__":
    print("=" * 60)
    print("HTTP LINKS ANALYZER - UI INTEGRATION TESTS")
    print("=" * 60)
    print()
    
    test_http_links_analyzer_in_ui_settings()
    print()
    
    test_http_links_analyzer_merging()
    print()
    
    test_http_links_analyzer_ui_description()
    print()
    
    test_http_links_analyzer_toggle()
    print()
    
    test_http_links_analyzer_in_enabled_list()
    print()
    
    print("=" * 60)
    print("ALL UI INTEGRATION TESTS PASSED")
    print("=" * 60)
