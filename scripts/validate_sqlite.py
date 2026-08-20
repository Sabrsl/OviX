"""
Validation complete de la base SQLite OviX.

Verifie reellement les tables, les donnees et les relations.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.utils.database import DatabaseManager

def validate_database():
    """Validation complete de la base de donnees."""
    print("=" * 80)
    print("VALIDATION COMPLETE DE LA BASE SQLITE")
    print("=" * 80)
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    # 1. Verifier les tables
    print("\n1. TABLES EXISTANTES")
    print("-" * 80)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables trouvees: {tables}")
    
    expected_tables = ['analysis_jobs', 'analysis_results', 'articles_to_analyze', 
                      'manual_review_decisions', 'published_articles']
    
    for table in expected_tables:
        if table in tables:
            print(f"[OK] {table} existe")
        else:
            print(f"[ERROR] {table} MANQUANTE")
    
    # 2. Verifier la structure de chaque table
    print("\n2. STRUCTURE DES TABLES")
    print("-" * 80)
    
    for table in expected_tables:
        if table in tables:
            print(f"\n--- {table} ---")
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            for col in columns:
                pk_marker = "(PK)" if col[5] else ""
                print(f"  {col[1]}: {col[2]} {pk_marker}")
    
    # 3. Verifier les donnees analysis_jobs
    print("\n3. ANALYSIS_JOBS - DONNEES")
    print("-" * 80)
    cursor.execute("SELECT COUNT(*) FROM analysis_jobs")
    job_count = cursor.fetchone()[0]
    print(f"Nombre de jobs: {job_count}")
    
    if job_count > 0:
        cursor.execute("""
            SELECT id, article_title, mode, status, progress, created_at, started_at, completed_at
            FROM analysis_jobs
            LIMIT 5
        """)
        print("\nExemples de jobs:")
        for row in cursor.fetchall():
            print(f"  ID: {row[0][:20]}... | Article: {row[1][:30]}... | Mode: {row[2]} | Status: {row[3]} | Progress: {row[4]}")
    
    # 4. Verifier les donnees analysis_results
    print("\n4. ANALYSIS_RESULTS - DONNEES")
    print("-" * 80)
    cursor.execute("SELECT COUNT(*) FROM analysis_results")
    result_count = cursor.fetchone()[0]
    print(f"Nombre de resultats: {result_count}")
    
    if result_count > 0:
        cursor.execute("""
            SELECT id, job_id, article_title, status, mode, changes_count, analysis_date
            FROM analysis_results
            LIMIT 5
        """)
        print("\nExemples de resultats:")
        for row in cursor.fetchall():
            print(f"  ID: {row[0][:20]}... | Job: {row[1][:20]}... | Article: {row[2][:30]}... | Status: {row[3]} | Changes: {row[5]}")
    
    # 5. Verifier les relations jobs <-> results
    print("\n5. RELATIONS JOBS <-> RESULTS")
    print("-" * 80)
    cursor.execute("""
        SELECT COUNT(*) FROM analysis_results 
        WHERE job_id IN (SELECT id FROM analysis_jobs)
    """)
    linked_results = cursor.fetchone()[0]
    print(f"Resultats lies a un job: {linked_results}/{result_count}")
    
    # 6. Verifier articles_to_analyze
    print("\n6. ARTICLES_TO_ANALYZE - DONNEES")
    print("-" * 80)
    cursor.execute("SELECT COUNT(*) FROM articles_to_analyze")
    queue_count = cursor.fetchone()[0]
    print(f"Articles dans la file: {queue_count}")
    
    if queue_count > 0:
        cursor.execute("""
            SELECT id, title, source, status, priority, added_at
            FROM articles_to_analyze
            LIMIT 5
        """)
        print("\nExemples dans la file:")
        for row in cursor.fetchall():
            print(f"  ID: {row[0][:20]}... | Article: {row[1][:30]}... | Source: {row[2]} | Status: {row[3]} | Priority: {row[4]}")
    
    # 7. Verifier manual_review_decisions
    print("\n7. MANUAL_REVIEW_DECISIONS - DONNEES")
    print("-" * 80)
    cursor.execute("SELECT COUNT(*) FROM manual_review_decisions")
    decision_count = cursor.fetchone()[0]
    print(f"Decisions de revue: {decision_count}")
    
    if decision_count > 0:
        cursor.execute("""
            SELECT id, article_title, url, status, decision_date
            FROM manual_review_decisions
            LIMIT 5
        """)
        print("\nExemples de decisions:")
        for row in cursor.fetchall():
            print(f"  ID: {row[0][:30]}... | Article: {row[1][:30]}... | Status: {row[3]} | Date: {row[4]}")
    
    # 8. Verifier published_articles
    print("\n8. PUBLISHED_ARTICLES - DONNEES")
    print("-" * 80)
    if 'published_articles' in tables:
        cursor.execute("SELECT COUNT(*) FROM published_articles")
        published_count = cursor.fetchone()[0]
        print(f"Articles publies: {published_count}")
        
        if published_count > 0:
            cursor.execute("""
                SELECT title, revision_id, published_date
                FROM published_articles
                LIMIT 5
            """)
            print("\nExemples d'articles publies:")
            for row in cursor.fetchall():
                print(f"  Article: {row[0][:30]}... | Revision: {row[1]} | Date: {row[2]}")
    else:
        print("[WARNING] Table published_articles n'existe pas encore")
        print("Note: Les articles publies sont actuellement dans analysis_results avec status='published'")
    
    # 9. Verifier les indexes
    print("\n9. INDEXES")
    print("-" * 80)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = [row[0] for row in cursor.fetchall()]
    print(f"Indexes trouves: {len(indexes)}")
    for idx in indexes[:10]:  # Afficher les 10 premiers
        print(f"  - {idx}")
    
    # 10. Verifier l'integrite des donnees migrees
    print("\n10. INTEGRITE DES DONNEES MIGREES")
    print("-" * 80)
    
    # Verifier que les 518 articles migrés sont accessibles
    cursor.execute("SELECT COUNT(DISTINCT article_title) FROM analysis_results")
    distinct_articles = cursor.fetchone()[0]
    print(f"Articles distincts dans analysis_results: {distinct_articles}")
    
    # Verifier les statuts
    cursor.execute("SELECT status, COUNT(*) FROM analysis_results GROUP BY status")
    status_counts = cursor.fetchall()
    print("\nDistribution des statuts:")
    for status, count in status_counts:
        print(f"  {status}: {count}")
    
    # Verifier les modes
    cursor.execute("SELECT mode, COUNT(*) FROM analysis_results GROUP BY mode")
    mode_counts = cursor.fetchall()
    print("\nDistribution des modes:")
    for mode, count in mode_counts:
        print(f"  {mode}: {count}")
    
    # 11. Verifier les timestamps
    print("\n11. TIMESTAMPS")
    print("-" * 80)
    cursor.execute("""
        SELECT COUNT(*) FROM analysis_results 
        WHERE analysis_date IS NOT NULL
    """)
    with_date = cursor.fetchone()[0]
    print(f"Resultats avec date d'analyse: {with_date}/{result_count}")
    
    cursor.execute("""
        SELECT COUNT(*) FROM analysis_jobs 
        WHERE created_at IS NOT NULL
    """)
    jobs_with_date = cursor.fetchone()[0]
    print(f"Jobs avec date de creation: {jobs_with_date}/{job_count}")
    
    db.close()
    
    print("\n" + "=" * 80)
    print("VALIDATION SQLITE TERMINEE")
    print("=" * 80)

if __name__ == "__main__":
    validate_database()