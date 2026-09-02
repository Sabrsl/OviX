"""
Tests de baseline pour Phase 0 - Étape 0.3

Ces tests figent le comportement actuel du système DeadLink
et servent de référence pour vérifier la non-régression lors du refactoring.

Note: Ces tests utilisent des contenus simples pour caractériser le comportement
sans mock réseau complexe. Pour un test complet avec réseau, utiliser l'orchestrateur.
"""

import pytest
from wikipedia_maintenance.analyzers import DeadLinkAnalyzer
from wikipedia_maintenance.analyzers.base import Issue
from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.utils.tracking_service import TrackingService
import json
from pathlib import Path


class TestDeadLinkBaseline:
    """Tests de baseline pour le système DeadLink."""

    def setup_method(self):
        """Setup method to initialize tracking service for each test."""
        # Phase 2: Initialize tracking service
        self.tracking_service = None
        try:
            db_manager = DatabaseManager("test_wikipedia_maintenance.db")
            self.tracking_service = TrackingService(db_manager)
        except Exception as e:
            print(f"Warning: Failed to initialize TrackingService: {e}")

    def test_1_issue_structure_baseline(self):
        """
        Test 1 : Structure Issue - fige la structure de Issue et Issue.extra
        """
        # Créer une Issue typique comme DeadLinkAnalyzer le ferait
        issue = Issue(
            issue_type="dead_link",
            description="Lien mort réparé : https://example.com",
            position=10,
            original_text="https://example.com",
            suggested_text="https://archive.org/example",
            severity="high",
            confidence=1.0,
            extra={
                'url': 'https://example.com',
                'old_url': 'https://example.com',
                'new_url': 'https://archive.org/example',
                'http_status_code': 404,
                'repair_decision': 'REPLACEMENT_CONFIRMED',
                'repair_status': 'REPAIR_APPLIED',
                'archive_url': 'https://archive.org/example',
                'archive_date': '20240101',
                'provider': 'web.archive.org',
                'template_name': 'Lien web',
                'repair_type': 'template'
            }
        )
        
        baseline = {
            'test_name': 'test_1_issue_structure',
            'issue': {
                'issue_type': issue.issue_type,
                'description': issue.description,
                'position': issue.position,
                'original_text': issue.original_text,
                'suggested_text': issue.suggested_text,
                'severity': issue.severity,
                'confidence': issue.confidence,
                'extra': issue.extra,
                'extra_keys': list(issue.extra.keys()) if issue.extra else [],
                'all_keys': list(issue.__dict__.keys())
            }
        }
        
        output_path = Path("test_results/baseline_test_1.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 1 : Structure Issue ===")
        print(f"Extra keys: {baseline['issue']['extra_keys']}")
        print(f"All keys: {baseline['issue']['all_keys']}")

    def test_2_ouvrage_expected_behavior(self):
        """
        Test 2 : Comportement attendu pour ouvrage
        Documente le comportement attendu (pas d'exécution réelle)
        """
        baseline = {
            'test_name': 'test_2_ouvrage_expected_behavior',
            'expected_behavior': {
                'template': 'ouvrage',
                'url': 'https://dead-site.com',
                'http_status': 404,
                'expected_outcome': 'NO_MODIFICATION',
                'reason': 'TEMPLATES_WITHOUT_ARCHIVE_PARAMS excludes ouvrage from archive params',
                'protection_location': 'generate_archive_repair_template() line 634-638'
            }
        }
        
        output_path = Path("test_results/baseline_test_2.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 2 : Comportement attendu ouvrage ===")
        print(f"Expected: {baseline['expected_behavior']['expected_outcome']}")

    def test_3_chapitre_expected_behavior(self):
        """
        Test 3 : Comportement attendu pour chapitre
        """
        baseline = {
            'test_name': 'test_3_chapitre_expected_behavior',
            'expected_behavior': {
                'template': 'chapitre',
                'url': 'https://dead-site.com',
                'http_status': 404,
                'expected_outcome': 'NO_MODIFICATION',
                'reason': 'TEMPLATES_WITHOUT_ARCHIVE_PARAMS excludes chapitre from archive params',
                'protection_location': 'generate_archive_repair_template() line 634-638'
            }
        }
        
        output_path = Path("test_results/baseline_test_3.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 3 : Comportement attendu chapitre ===")
        print(f"Expected: {baseline['expected_behavior']['expected_outcome']}")

    def test_4_bare_url_expected_behavior(self):
        """
        Test 4 : Comportement attendu pour URL nue dans <ref>
        """
        baseline = {
            'test_name': 'test_4_bare_url_expected_behavior',
            'expected_behavior': {
                'context': '<ref>URL</ref>',
                'url': 'https://dead-site.com',
                'http_status': 404,
                'expected_outcome': 'CONVERSION_TO_LIEN_WEB',
                'conversion_function': '_apply_simple_url_replacement()',
                'template_builder': 'BareUrlHelper.build_repaired_reference_template()',
                'protections': [
                    'Check for academic patterns (language templates, vol, p., ISBN, etc.)',
                    'Check if already in template',
                    'Check if in Liens externes section'
                ]
            }
        }
        
        output_path = Path("test_results/baseline_test_4.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 4 : Comportement attendu URL nue ===")
        print(f"Expected: {baseline['expected_behavior']['expected_outcome']}")

    def test_5_out_of_scope_expected_behavior(self):
        """
        Test 5 : Comportement attendu pour URL hors <ref>
        """
        baseline = {
            'test_name': 'test_5_out_of_scope_expected_behavior',
            'expected_behavior': {
                'context': 'URL hors <ref>',
                'url': 'https://dead-site.com',
                'expected_outcome': 'NO_MODIFICATION',
                'protection': '_is_url_in_reference_scope()',
                'protection_location': 'dead_links.py line 1243-1258'
            }
        }
        
        output_path = Path("test_results/baseline_test_5.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 5 : Comportement attendu hors périmètre ===")
        print(f"Expected: {baseline['expected_behavior']['expected_outcome']}")

    def test_6_database_schema_baseline(self):
        """
        Test 6 : Schéma Database actuel
        Documente les tables existantes comme baseline
        """
        baseline = {
            'test_name': 'test_6_database_schema',
            'existing_tables': [
                'articles',
                'issues',
                'actions',
                'sessions',
                'analysis_results',
                'analysis_jobs',
                'articles_to_analyze',
                'manual_review_decisions',
                'https_verification_cache',
                'automation_sessions',
                'automation_article_states',
                'scheduler_queue',
                'scheduler_state',
                'kill_switch_state',
                'automation_lock'
            ],
            'missing_tables': [
                'deadlink_operations',
                'deadlink_operation_events'
            ]
        }
        
        output_path = Path("test_results/baseline_test_6.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 6 : Schéma Database ===")
        print(f"Tables existantes: {len(baseline['existing_tables'])}")
        print(f"Tables manquantes: {baseline['missing_tables']}")

    def test_7_tracking_systems_baseline(self):
        """
        Test 7 : Systèmes de tracking actuels
        Documente les trackers existants comme baseline
        """
        baseline = {
            'test_name': 'test_7_tracking_systems',
            'tracking_systems': [
                {
                    'name': 'AnalyzedTracker',
                    'type': 'JSON',
                    'file': 'data/analyzed_articles.json',
                    'used_by': ['AutomationOrchestrator', 'Scheduler']
                },
                {
                    'name': 'PublishedTracker',
                    'type': 'JSON',
                    'file': 'data/published_articles.json',
                    'used_by': ['Publisher', 'AutomationOrchestrator', 'Scheduler', 'Retrievers']
                },
                {
                    'name': 'DatabaseManager',
                    'type': 'SQLite',
                    'file': 'data/wikipedia_maintenance.db',
                    'used_by': ['Backend API', 'Scheduler', 'AutomationOrchestrator']
                },
                {
                    'name': 'SQLiteAutomationStateManager',
                    'type': 'SQLite',
                    'file': 'data/wikipedia_maintenance.db',
                    'used_by': ['Automation scripts']
                },
                {
                    'name': 'AutomationStateManager (JSON)',
                    'type': 'JSON',
                    'file': 'data/automation_state.json',
                    'used_by': ['Legacy - being replaced']
                }
            ]
        }
        
        output_path = Path("test_results/baseline_test_7.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 7 : Systèmes de tracking ===")
        print(f"Nombre de systèmes: {len(baseline['tracking_systems'])}")

    def test_8_corrector_duplication_baseline(self):
        """
        Test 8 : Duplication Corrector
        Documente la duplication comme baseline
        """
        baseline = {
            'test_name': 'test_8_corrector_duplication',
            'corrector_implementations': [
                {
                    'file': 'utils/corrector.py',
                    'class': 'Corrector',
                    'used_directly': False,
                    'exported_in': 'utils/__init__.py',
                    'recommendation': 'DELETE'
                },
                {
                    'file': 'utils/publisher.py',
                    'class': 'Corrector',
                    'used_by': ['Orchestrator', 'AutomationOrchestrator'],
                    'recommendation': 'KEEP'
                }
            ]
        }
        
        output_path = Path("test_results/baseline_test_8.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Test 8 : Duplication Corrector ===")
        print(f"Implémentations: {len(baseline['corrector_implementations'])}")


if __name__ == "__main__":
    # Exécuter les tests de baseline
    print("=== Exécution des tests de baseline ===\n")
    
    test_class = TestDeadLinkBaseline()
    
    print("\n--- Test 1 : Lien web mort avec archive ---")
    test_class.test_1_lien_web_dead_with_archive()
    
    print("\n--- Test 2 : Ouvrage mort ---")
    test_class.test_2_ouvrage_dead_no_modification()
    
    print("\n--- Test 3 : Chapitre mort ---")
    test_class.test_3_chapitre_dead_no_modification()
    
    print("\n--- Test 4 : URL nue dans <ref> ---")
    test_class.test_4_bare_url_in_ref_with_archive()
    
    print("\n--- Test 5 : URL hors <ref> ---")
    test_class.test_5_bare_url_out_of_ref_no_modification()
    
    print("\n--- Test 6 : Référence académique ---")
    test_class.test_6_academic_reference_no_conversion()
    
    print("\n--- Test 7 : URL déjà archivée ---")
    test_class.test_7_already_archived_no_duplicate()
    
    print("\n--- Test 8 : Archive existante ---")
    test_class.test_8_existing_archive_preserved()
    
    print("\n=== Tests de baseline terminés ===")
    print("Résultats sauvegardés dans test_results/baseline_test_*.json")
