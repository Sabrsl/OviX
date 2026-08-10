"""
Tests unitaires pour le système de sélection des analyseurs

Ce test vérifie que :
1. Un analyseur décoché n'est jamais exécuté
2. Les résultats correspondent exactement aux analyseurs sélectionnés
3. Le comportement est identique après redémarrage si les préférences sont sauvegardées
"""

import sys
from pathlib import Path

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.utils.ui_settings import UISettings, UISettingsManager
from wikipedia_maintenance.analyzers import (
    LinkAnalyzer, WhitespaceAnalyzer, TypographyAnalyzer,
    TemplateAnalyzer, CategoryAnalyzer, HTMLAnalyzer,
    ReferenceAnalyzer, StructureAnalyzer, WorksListAnalyzer,
    HttpLinksAnalyzer
)


def test_analyzer_disabled_by_default():
    """Test que tous les analyseurs sont désactivés par défaut"""
    # Utiliser le constructeur normal avec defaults
    from wikipedia_maintenance.utils.ui_settings import UISettings
    settings = UISettings()
    
    # Vérifier que HttpLinksAnalyzer est dans les defaults
    assert "HttpLinksAnalyzer" in settings.enabled_analyzers, \
        "HttpLinksAnalyzer devrait être dans les analyseurs par défaut"
    
    # Vérifier que tous les analyseurs sont désactivés par défaut
    for analyzer_name in settings.enabled_analyzers.keys():
        result = settings.is_analyzer_enabled(analyzer_name)
        assert result == False, \
            f"{analyzer_name} devrait être désactivé par défaut mais est {result}"
    
    print("[OK] Tous les analyseurs sont désactivés par défaut")


def test_enable_single_analyzer():
    """Test l'activation d'un seul analyseur"""
    settings = UISettings()
    
    # Activer TypographyAnalyzer
    settings.set_analyzer_enabled("TypographyAnalyzer", True)
    
    assert settings.is_analyzer_enabled("TypographyAnalyzer") == True
    assert settings.is_analyzer_enabled("LinkAnalyzer") == False
    assert len(settings.get_enabled_analyzers()) == 1
    
    print("[OK] Activation d'un seul analyseur fonctionne correctement")


def test_disable_analyzer():
    """Test la désactivation d'un analyseur"""
    settings = UISettings()
    
    # Activer puis désactiver
    settings.set_analyzer_enabled("TypographyAnalyzer", True)
    assert settings.is_analyzer_enabled("TypographyAnalyzer") == True
    
    settings.set_analyzer_enabled("TypographyAnalyzer", False)
    assert settings.is_analyzer_enabled("TypographyAnalyzer") == False
    
    print("[OK] Désactivation d'un analyseur fonctionne correctement")


def test_enable_all_analyzers():
    """Test l'activation de tous les analyseurs"""
    settings = UISettings()
    
    # Activer tous les analyseurs
    for analyzer_name in settings.enabled_analyzers.keys():
        settings.set_analyzer_enabled(analyzer_name, True)
    
    enabled_analyzers = settings.get_enabled_analyzers()
    assert len(enabled_analyzers) == len(settings.enabled_analyzers)
    
    for analyzer_name in settings.enabled_analyzers.keys():
        assert settings.is_analyzer_enabled(analyzer_name) == True
    
    print("[OK] Activation de tous les analyseurs fonctionne correctement")


def test_disable_all_analyzers():
    """Test la désactivation de tous les analyseurs"""
    settings = UISettings()
    
    # D'abord activer tous les analyseurs
    for analyzer_name in settings.enabled_analyzers.keys():
        settings.set_analyzer_enabled(analyzer_name, True)
    
    # Puis tout désactiver
    for analyzer_name in settings.enabled_analyzers.keys():
        settings.set_analyzer_enabled(analyzer_name, False)
    
    enabled_analyzers = settings.get_enabled_analyzers()
    assert len(enabled_analyzers) == 0
    
    print("[OK] Désactivation de tous les analyseurs fonctionne correctement")


def test_get_enabled_analyzers():
    """Test la récupération de la liste des analyseurs activés"""
    settings = UISettings()
    
    # Activer quelques analyseurs
    settings.set_analyzer_enabled("TypographyAnalyzer", True)
    settings.set_analyzer_enabled("LinkAnalyzer", True)
    settings.set_analyzer_enabled("WhitespaceAnalyzer", False)
    
    enabled_analyzers = settings.get_enabled_analyzers()
    
    assert "TypographyAnalyzer" in enabled_analyzers
    assert "LinkAnalyzer" in enabled_analyzers
    assert "WhitespaceAnalyzer" not in enabled_analyzers
    assert len(enabled_analyzers) == 2
    
    print("[OK] Récupération des analyseurs activés fonctionne correctement")


def test_unknown_analyzer():
    """Test la gestion des analyseurs inconnus"""
    settings = UISettings()
    
    # Essayer d'activer un analyseur inexistant
    settings.set_analyzer_enabled("NonExistentAnalyzer", True)
    
    # Ne devrait pas planter mais ne devrait rien faire
    assert "NonExistentAnalyzer" not in settings.enabled_analyzers
    
    print("[OK] Gestion des analyseurs inconnus fonctionne correctement")


def test_analyzer_execution_respects_settings():
    """Test que seuls les analyseurs activés sont exécutés"""
    # Créer des settings manuellement
    settings = UISettings()
    
    # Désactiver tous les analyseurs
    for analyzer_name in settings.enabled_analyzers.keys():
        settings.set_analyzer_enabled(analyzer_name, False)
    
    # Activer uniquement TypographyAnalyzer
    settings.set_analyzer_enabled("TypographyAnalyzer", True)
    
    enabled_analyzers = settings.get_enabled_analyzers()
    
    # Vérifier que seul TypographyAnalyzer est activé
    assert len(enabled_analyzers) == 1
    assert "TypographyAnalyzer" in enabled_analyzers
    assert "LinkAnalyzer" not in enabled_analyzers
    
    # Simuler l'instanciation des analyseurs selon les settings
    analyzer_classes = {
        "LinkAnalyzer": LinkAnalyzer,
        "WhitespaceAnalyzer": WhitespaceAnalyzer,
        "TypographyAnalyzer": TypographyAnalyzer,
        "TemplateAnalyzer": TemplateAnalyzer,
        "CategoryAnalyzer": CategoryAnalyzer,
        "HTMLAnalyzer": HTMLAnalyzer,
        "ReferenceAnalyzer": ReferenceAnalyzer,
        "StructureAnalyzer": StructureAnalyzer,
        "WorksListAnalyzer": WorksListAnalyzer,
        "HttpLinksAnalyzer": HttpLinksAnalyzer
    }
    
    analyzers = []
    for analyzer_name in enabled_analyzers:
        if analyzer_name in analyzer_classes:
            analyzers.append(analyzer_classes[analyzer_name]())
    
    # Vérifier que seul TypographyAnalyzer est instancié
    assert len(analyzers) == 1
    assert isinstance(analyzers[0], TypographyAnalyzer)
    
    print("[OK] L'exécution respecte les paramètres des analyseurs")


def test_settings_persistence():
    """Test la persistance des paramètres"""
    # Note: Ce test nécessite une base de données, donc nous simulons la logique
    settings1 = UISettings()
    
    # Modifier les paramètres
    settings1.set_analyzer_enabled("TypographyAnalyzer", True)
    settings1.set_analyzer_enabled("LinkAnalyzer", True)
    
    # Simuler la sauvegarde (en mémoire)
    saved_analyzers = settings1.enabled_analyzers.copy()
    
    # Créer une nouvelle instance avec les paramètres sauvegardés
    settings2 = UISettings(enabled_analyzers=saved_analyzers)
    
    # Vérifier que les paramètres sont conservés
    assert settings2.is_analyzer_enabled("TypographyAnalyzer") == True
    assert settings2.is_analyzer_enabled("LinkAnalyzer") == True
    assert settings2.is_analyzer_enabled("WhitespaceAnalyzer") == False
    
    print("[OK] La persistance des paramètres fonctionne correctement")


def test_analyzer_selection_in_pipeline():
    """Test que le pipeline n'utilise que les analyseurs sélectionnés"""
    settings = UISettings()
    
    # Activer uniquement TypographyAnalyzer et WhitespaceAnalyzer
    settings.set_analyzer_enabled("TypographyAnalyzer", True)
    settings.set_analyzer_enabled("WhitespaceAnalyzer", True)
    
    # Instancier uniquement les analyseurs activés
    enabled_analyzers = settings.get_enabled_analyzers()
    
    analyzer_classes = {
        "LinkAnalyzer": LinkAnalyzer,
        "WhitespaceAnalyzer": WhitespaceAnalyzer,
        "TypographyAnalyzer": TypographyAnalyzer,
        "TemplateAnalyzer": TemplateAnalyzer,
        "CategoryAnalyzer": CategoryAnalyzer,
        "HTMLAnalyzer": HTMLAnalyzer,
        "ReferenceAnalyzer": ReferenceAnalyzer,
        "StructureAnalyzer": StructureAnalyzer,
        "WorksListAnalyzer": WorksListAnalyzer,
        "HttpLinksAnalyzer": HttpLinksAnalyzer
    }
    
    analyzers = []
    for analyzer_name in enabled_analyzers:
        if analyzer_name in analyzer_classes:
            if analyzer_name in ["LinkAnalyzer", "WhitespaceAnalyzer", "ReferenceAnalyzer", "StructureAnalyzer", "WorksListAnalyzer"]:
                analyzers.append(analyzer_classes[analyzer_name](language='fr'))
            else:
                analyzers.append(analyzer_classes[analyzer_name]())
    
    # Vérifier que seuls les analyseurs attendus sont instanciés
    assert len(analyzers) == 2
    analyzer_names = [a.__class__.__name__ for a in analyzers]
    assert "TypographyAnalyzer" in analyzer_names
    assert "WhitespaceAnalyzer" in analyzer_names
    assert "LinkAnalyzer" not in analyzer_names
    
    print("[OK] Le pipeline n'utilise que les analyseurs sélectionnés")


def test_no_analyzer_enabled():
    """Test le comportement quand aucun analyseur n'est activé"""
    settings = UISettings()
    
    # S'assurer que tous sont désactivés
    for analyzer_name in settings.enabled_analyzers.keys():
        settings.set_analyzer_enabled(analyzer_name, False)
    
    enabled_analyzers = settings.get_enabled_analyzers()
    assert len(enabled_analyzers) == 0
    
    # Simuler l'instanciation des analyseurs
    analyzer_classes = {
        "LinkAnalyzer": LinkAnalyzer,
        "WhitespaceAnalyzer": WhitespaceAnalyzer,
        "TypographyAnalyzer": TypographyAnalyzer,
        "TemplateAnalyzer": TemplateAnalyzer,
        "CategoryAnalyzer": CategoryAnalyzer,
        "HTMLAnalyzer": HTMLAnalyzer,
        "ReferenceAnalyzer": ReferenceAnalyzer,
        "StructureAnalyzer": StructureAnalyzer,
        "WorksListAnalyzer": WorksListAnalyzer,
        "HttpLinksAnalyzer": HttpLinksAnalyzer
    }
    
    analyzers = []
    for analyzer_name in enabled_analyzers:
        if analyzer_name in analyzer_classes:
            analyzers.append(analyzer_classes[analyzer_name]())
    
    # Vérifier qu'aucun analyseur n'est instancié
    assert len(analyzers) == 0
    
    print("[OK] Le comportement sans analyseur activé est correct")


def run_all_tests():
    """Exécute tous les tests"""
    print("=== DÉBUT DES TESTS DU SYSTÈME DE SÉLECTION DES ANALYSEURS ===\n")
    
    print("Test 1: Analyseurs désactivés par défaut")
    test_analyzer_disabled_by_default()
    print()
    
    print("Test 2: Activation d'un seul analyseur")
    test_enable_single_analyzer()
    print()
    
    print("Test 3: Désactivation d'un analyseur")
    test_disable_analyzer()
    print()
    
    print("Test 4: Activation de tous les analyseurs")
    test_enable_all_analyzers()
    print()
    
    print("Test 5: Désactivation de tous les analyseurs")
    test_disable_all_analyzers()
    print()
    
    print("Test 6: Récupération des analyseurs activés")
    test_get_enabled_analyzers()
    print()
    
    print("Test 7: Gestion des analyseurs inconnus")
    test_unknown_analyzer()
    print()
    
    print("Test 8: L'exécution respecte les paramètres")
    test_analyzer_execution_respects_settings()
    print()
    
    print("Test 9: Persistance des paramètres")
    test_settings_persistence()
    print()
    
    print("Test 10: Pipeline avec sélection")
    test_analyzer_selection_in_pipeline()
    print()
    
    print("Test 11: Aucun analyseur activé")
    test_no_analyzer_enabled()
    print()
    
    print("=== TOUS LES TESTS PASSÉS [OK] ===")


if __name__ == "__main__":
    run_all_tests()
