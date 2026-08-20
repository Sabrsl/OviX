"""
Script pour ajouter la colonne results à analysis_jobs (la bonne correction)
"""

import sqlite3

def add_results_column():
    """Ajouter la colonne results à analysis_jobs."""
    db_path = "data/wikipedia_maintenance.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("AJOUT COLONNE results À analysis_jobs")
        print("=" * 80)
        
        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(analysis_jobs)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'results' in column_names:
            print("La colonne results existe déjà")
        else:
            print("Ajout de la colonne results...")
            cursor.execute("""
                ALTER TABLE analysis_jobs
                ADD COLUMN results TEXT
            """)
            conn.commit()
            print("Colonne results ajoutée avec succès")
        
        # Vérifier le nouveau schéma
        cursor.execute("PRAGMA table_info(analysis_jobs)")
        columns = cursor.fetchall()
        
        print("\nNouveau schéma de analysis_jobs:")
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
    add_results_column()
