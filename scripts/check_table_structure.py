import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.utils.database import DatabaseManager

db = DatabaseManager()
cursor = db.conn.cursor()

print("Structure de analysis_results:")
cursor.execute("PRAGMA table_info(analysis_results)")
for row in cursor.fetchall():
    print(f"  {row[1]}: {row[2]}")

print("\nStructure de articles_to_analyze:")
cursor.execute("PRAGMA table_info(articles_to_analyze)")
for row in cursor.fetchall():
    print(f"  {row[1]}: {row[2]}")

db.close()