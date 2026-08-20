"""
Script pour vérifier les données Ashkan Sahihi dans la base de données
"""

import sqlite3
import json
from datetime import datetime

def check_ashkan_in_db():
    """Vérifier les données Ashkan Sahihi dans la base de données."""
    db_path = "data/wikipedia_maintenance.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("VÉRIFICATION BASE DE DONNÉES - Ashkan Sahihi")
        print("=" * 80)
        
        # Vérifier la table analysis_jobs
        print("\n1. Table analysis_jobs:")
        cursor.execute("""
            SELECT id, article_title, status, progress, message, started_at, completed_at
            FROM analysis_jobs
            WHERE article_title LIKE '%Ashkan%'
            ORDER BY started_at DESC
            LIMIT 5
        """)
        jobs = cursor.fetchall()
        
        if jobs:
            for job in jobs:
                print(f"   id: {job[0]}")
                print(f"   article_title: {job[1]}")
                print(f"   status: {job[2]}")
                print(f"   progress: {job[3]}")
                print(f"   message: {job[4]}")
                print(f"   started_at: {job[5]}")
                print(f"   completed_at: {job[6]}")
                print()
        else:
            print("   Aucun job trouvé pour Ashkan Sahihi")
        
        # Vérifier la table analysis_results
        print("\n2. Table analysis_results:")
        cursor.execute("""
            SELECT id, job_id, article_title, status, changes_count,
                   dead_links_count, corrected_links_count, total_links, analysis_date
            FROM analysis_results
            WHERE article_title LIKE '%Ashkan%'
            ORDER BY analysis_date DESC
            LIMIT 5
        """)
        results = cursor.fetchall()

        if results:
            for result in results:
                print(f"   id: {result[0]}")
                print(f"   job_id: {result[1]}")
                print(f"   article_title: {result[2]}")
                print(f"   status: {result[3]}")
                print(f"   changes_count: {result[4]}")
                print(f"   dead_links_count: {result[5]}")
                print(f"   corrected_links_count: {result[6]}")
                print(f"   total_links: {result[7]}")
                print(f"   analysis_date: {result[8]}")
                print()
        else:
            print("   Aucun résultat trouvé pour Ashkan Sahihi")
        
        # Vérifier les résultats JSON si présents
        print("\n3. Vérification des résultats JSON dans analysis_jobs:")
        cursor.execute("""
            SELECT id, article_title, results
            FROM analysis_jobs
            WHERE article_title LIKE '%Ashkan%' AND results IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 1
        """)
        job_with_results = cursor.fetchone()
        
        if job_with_results:
            job_id, article_title, results_json = job_with_results
            print(f"   id: {job_id}")
            print(f"   article_title: {article_title}")
            
            if results_json:
                try:
                    results = json.loads(results_json)
                    print(f"   results keys: {results.keys()}")
                    
                    if 'issues' in results:
                        issues = results['issues']
                        print(f"   issues count: {len(issues)}")
                        if issues:
                            print(f"   Premier issue: {issues[0]}")
                    
                    if 'stats' in results:
                        stats = results['stats']
                        print(f"   stats: {stats}")
                except json.JSONDecodeError as e:
                    print(f"   Erreur parsing JSON: {e}")
            else:
                print("   results_json est None")
        else:
            print("   Aucun job avec results trouvé pour Ashkan Sahihi")
        
        # Vérifier tous les jobs récents pour comprendre le pattern
        print("\n4. Jobs récents (tous articles):")
        cursor.execute("""
            SELECT job_id, article_title, status, completed_at
            FROM analysis_jobs
            ORDER BY completed_at DESC
            LIMIT 10
        """)
        recent_jobs = cursor.fetchall()
        
        for job in recent_jobs:
            print(f"   {job[1]} - {job[2]} - {job[3]}")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("VÉRIFICATION TERMINÉE")
        print("=" * 80)
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_ashkan_in_db()
