"""
Script pour vérifier si la colonne results existait avant dans analysis_jobs
"""

import sqlite3

def check_results_column():
    """Vérifier si la colonne results existe dans analysis_jobs."""
    db_path = "data/wikipedia_maintenance.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("VÉRIFICATION COLONNE results DANS analysis_jobs")
        print("=" * 80)
        
        cursor.execute("PRAGMA table_info(analysis_jobs)")
        columns = cursor.fetchall()
        
        print("\nColonnes actuelles dans analysis_jobs:")
        for col in columns:
            print(f"   {col[1]} ({col[2]})")
        
        # Vérifier si results existe
        column_names = [col[1] for col in columns]
        if 'results' in column_names:
            print("\n✅ La colonne results existe")
        else:
            print("\n❌ La colonne results N'EXISTE PAS")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("VÉRIFICATION TERMINÉE")
        print("=" * 80)
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_results_column()
