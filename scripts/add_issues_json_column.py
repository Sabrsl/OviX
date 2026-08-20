"""
Script pour ajouter la colonne issues_json à la table analysis_results
"""

import sqlite3

def add_issues_json_column():
    """Ajouter la colonne issues_json à analysis_results."""
    db_path = "data/wikipedia_maintenance.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("AJOUT COLONNE issues_json À analysis_results")
        print("=" * 80)
        
        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'issues_json' in column_names:
            print("La colonne issues_json existe déjà")
        else:
            print("Ajout de la colonne issues_json...")
            cursor.execute("""
                ALTER TABLE analysis_results
                ADD COLUMN issues_json TEXT
            """)
            conn.commit()
            print("Colonne issues_json ajoutée avec succès")
        
        # Vérifier le nouveau schéma
        cursor.execute("PRAGMA table_info(analysis_results)")
        columns = cursor.fetchall()
        
        print("\nNouveau schéma de analysis_results:")
        for col in columns:
            print(f"   {col[1]} ({col[2]})")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("OPÉRATION TERMINÉE")
        print("=" * 80)
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    add_issues_json_column()
