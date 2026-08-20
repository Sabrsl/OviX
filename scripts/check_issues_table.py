"""
Script pour vérifier les issues dans la table issues pour Ashkan Sahihi
"""

import sqlite3

def check_issues_for_ashkan():
    """Vérifier les issues pour Ashkan Sahihi."""
    db_path = "data/wikipedia_maintenance.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("VÉRIFICATION TABLE ISSUES - Ashkan Sahihi")
        print("=" * 80)
        
        # D'abord trouver l'article_id pour Ashkan Sahihi
        cursor.execute("""
            SELECT id FROM articles WHERE title LIKE '%Ashkan%'
        """)
        article_row = cursor.fetchone()
        
        if article_row:
            article_id = article_row[0]
            print(f"article_id trouvé: {article_id}")
            
            # Vérifier les issues pour cet article
            cursor.execute("""
                SELECT id, article_id, issue_type, description, severity, position, 
                       original_text, suggested_text
                FROM issues
                WHERE article_id = ?
            """, (article_id,))
            
            issues = cursor.fetchall()
            print(f"\nIssues trouvées: {len(issues)}")
            
            for issue in issues:
                print(f"\n   Issue ID: {issue[0]}")
                print(f"   Type: {issue[2]}")
                print(f"   Description: {issue[3]}")
                print(f"   Severity: {issue[4]}")
                print(f"   Position: {issue[5]}")
                print(f"   Original: {issue[6]}")
                print(f"   Suggested: {issue[7]}")
        else:
            print("Aucun article Ashkan Sahihi trouvé dans la table articles")
        
        # Vérifier tous les articles récents
        print("\n" + "=" * 80)
        print("Articles récents dans la table articles:")
        print("=" * 80)
        
        cursor.execute("""
            SELECT id, title, last_revision_id, status
            FROM articles
            ORDER BY retrieved_at DESC
            LIMIT 5
        """)
        
        articles = cursor.fetchall()
        for article in articles:
            print(f"   ID: {article[0]}, Title: {article[1]}, Revision: {article[2]}, Status: {article[3]}")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("VÉRIFICATION TERMINÉE")
        print("=" * 80)
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_issues_for_ashkan()
