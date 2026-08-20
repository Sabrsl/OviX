"""
Script pour vérifier le schéma de la base de données
"""

import sqlite3

def check_db_schema():
    """Vérifier le schéma de la base de données."""
    db_path = "data/wikipedia_maintenance.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 80)
        print("SCHÉMA BASE DE DONNÉES")
        print("=" * 80)
        
        # Lister toutes les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("\nTables dans la base de données:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Pour chaque table, afficher le schéma
        for table in tables:
            table_name = table[0]
            print(f"\n{'=' * 80}")
            print(f"Table: {table_name}")
            print(f"{'=' * 80}")
            
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print("Colonnes:")
            for col in columns:
                print(f"   {col[1]} ({col[2]}) - nullable: {col[3]}, default: {col[4]}, pk: {col[5]}")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("VÉRIFICATION TERMINÉE")
        print("=" * 80)
        
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_db_schema()
