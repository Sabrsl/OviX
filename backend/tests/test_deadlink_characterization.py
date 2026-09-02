"""
Tests de caractérisation pour Phase 0 - Étape 0.2

Ces tests capturent le comportement actuel du système DeadLink
sans modifier le code. Ils servent de baseline pour le refactoring.
"""

import pytest
from wikipedia_maintenance.utils.publisher import Corrector, Publisher, Correction
from wikipedia_maintenance.utils.analyzed_tracker import AnalyzedTracker, AnalysisStatus
from wikipedia_maintenance.utils.published_tracker import PublishedTracker
from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.analyzers.base import Issue
import json
from pathlib import Path


class TestDeadLinkCharacterization:
    """Tests pour caractériser le flux DeadLink → Issue → Correction."""

    def test_issue_structure_characterization(self):
        """
        Caractérise la structure de Issue et Issue.extra.
        Crée une Issue manuelle pour capturer sa structure sans exécuter DeadLinkAnalyzer.
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
        
        characterization = {
            'issue_type': issue.issue_type,
            'description': issue.description,
            'position': issue.position,
            'original_text': issue.original_text,
            'suggested_text': issue.suggested_text,
            'severity': issue.severity,
            'confidence': issue.confidence,
            'extra': issue.extra,
            'extra_keys': list(issue.extra.keys()) if issue.extra else [],
            'issue_keys': list(issue.__dict__.keys())
        }
        
        output_path = Path("test_results/issue_structure_characterization.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(characterization, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Caractérisation structure Issue ===")
        print(f"Type: {characterization['issue_type']}")
        print(f"Extra keys: {characterization['extra_keys']}")
        print(f"All keys: {characterization['issue_keys']}")
        print(f"Extra: {json.dumps(characterization['extra'], indent=4)}")

    def test_correction_flow_characterization(self):
        """
        Caractérise le flux Issue → Correction.
        Capture la structure de Correction.
        """
        content = """{{Lien web|url=https://example-site.com|titre=Test}}"""
        
        # Créer une issue manuelle pour tester Corrector sans dépendre de DeadLink
        from wikipedia_maintenance.analyzers.base import Issue
        issue = Issue(
            issue_type="test",
            description="Test issue",
            position=0,
            original_text="https://example-site.com",
            suggested_text="https://example-archived.com",
            severity="medium",
            confidence=1.0
        )
        
        corrector = Corrector(content)
        corrections = corrector.apply_corrections([issue])
        
        characterization = {
            'num_issues': 1,
            'num_corrections': len(corrections),
            'corrections': []
        }
        
        for correction in corrections:
            correction_data = {
                'type': type(correction).__name__,
                'applied': correction.applied if hasattr(correction, 'applied') else None,
                'issue_type': correction.issue.issue_type if hasattr(correction, 'issue') and correction.issue else None,
            }
            characterization['corrections'].append(correction_data)
        
        output_path = Path("test_results/correction_flow_characterization.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(characterization, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Caractérisation flux Correction ===")
        print(f"Nombre d'issues: {characterization['num_issues']}")
        print(f"Nombre de corrections: {characterization['num_corrections']}")
        for i, corr in enumerate(characterization['corrections']):
            print(f"\nCorrection {i}:")
            print(f"  Type: {corr['type']}")
            print(f"  Applied: {corr['applied']}")
            print(f"  Issue type: {corr['issue_type']}")


class TestTrackingCharacterization:
    """Tests pour caractériser le flux de tracking actuel."""

    def test_analyzed_tracker_characterization(self):
        """
        Caractérise ce qui est écrit dans AnalyzedTracker.
        """
        tracker = AnalyzedTracker("test_analyzed_articles.json")
        
        # Simuler un enregistrement
        tracker.record_analysis(
            title="Test Article",
            page_id=12345,
            revision_id=67890,
            status=AnalysisStatus.PENDING,
            score=0.8,
            decision="auto",
            mode="regex",
            changes_count=1,
            summary="Test summary",
            original_content="{{Lien web|url=https://example.com|titre=Test}}",
            corrected_content="{{Lien web|url=https://example.com|titre=Test|archive-url=https://archive.org/...}}",
            character_count=100,
            total_links=1,
            dead_links_count=1,
            corrected_links_count=1,
            human_verified=False,
            manual_review_urls=[]
        )
        
        # Lire et caractériser
        record = tracker.get_record("Test Article")
        
        characterization = {
            'record_exists': record is not None,
            'record_data': record.__dict__ if record else None
        }
        
        output_path = Path("test_results/analyzed_tracker_characterization.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(characterization, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n=== Caractérisation AnalyzedTracker ===")
        print(f"Record exists: {characterization['record_exists']}")
        if record:
            print(f"Status: {record.status}")
            print(f"Changes count: {record.changes_count}")
            print(f"Keys: {list(record.__dict__.keys())}")

    def test_published_tracker_characterization(self):
        """
        Caractérise ce qui est écrit dans PublishedTracker.
        """
        tracker = PublishedTracker("test_published_articles.json")
        
        # Simuler un enregistrement
        tracker.mark_as_published(
            article_title="Test Article",
            category="test",
            mode="regex",
            summary="Test summary",
            revision_id=67890
        )
        
        # Lire et caractériser
        entry = tracker.published_articles.get("Test Article")
        
        characterization = {
            'entry_exists': entry is not None,
            'entry_data': entry if entry else None
        }
        
        output_path = Path("test_results/published_tracker_characterization.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(characterization, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n=== Caractérisation PublishedTracker ===")
        print(f"Entry exists: {characterization['entry_exists']}")
        if entry:
            print(f"Keys: {list(entry.keys())}")


class TestSQLiteCharacterization:
    """Tests pour caractériser les écritures SQLite actuelles."""

    def test_database_tables_characterization(self):
        """
        Caractérise les tables existantes dans DatabaseManager.
        """
        db = DatabaseManager("test_wikipedia_maintenance.db")
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Pour chaque table, capturer le schéma
        schemas = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            schemas[table] = [
                {
                    'name': col[1],
                    'type': col[2],
                    'not_null': col[3],
                    'default_value': col[4],
                    'primary_key': col[5]
                }
                for col in columns
            ]
        
        characterization = {
            'tables': tables,
            'schemas': schemas
        }
        
        output_path = Path("test_results/database_tables_characterization.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(characterization, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== Caractérisation Database ===")
        print(f"Nombre de tables: {len(tables)}")
        print(f"Tables: {tables}")


if __name__ == "__main__":
    # Exécuter les tests manuellement pour caractérisation
    print("=== Exécution des tests de caractérisation ===\n")
    
    test_class = TestDeadLinkCharacterization()
    
    print("\n--- Test 1: Structure Issue ---")
    test_class.test_issue_structure_characterization()
    
    print("\n--- Test 2: Flux Correction ---")
    test_class.test_correction_flow_characterization()
    
    print("\n--- Test 3: AnalyzedTracker ---")
    test_tracking = TestTrackingCharacterization()
    test_tracking.test_analyzed_tracker_characterization()
    
    print("\n--- Test 4: PublishedTracker ---")
    test_tracking.test_published_tracker_characterization()
    
    print("\n--- Test 5: Database ---")
    test_sqlite = TestSQLiteCharacterization()
    test_sqlite.test_database_tables_characterization()
    
    print("\n=== Tests de caractérisation terminés ===")
    print("Résultats sauvegardés dans test_results/")
