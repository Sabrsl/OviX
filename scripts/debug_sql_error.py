import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.utils.database import DatabaseManager

db = DatabaseManager()
cursor = db.conn.cursor()

print("Test direct SELECT sur analysis_results:")
try:
    cursor.execute("SELECT article_title FROM analysis_results LIMIT 1")
    print("  [OK] article_title fonctionne")
except Exception as e:
    print(f"  [ERROR] article_title: {e}")

try:
    cursor.execute("SELECT title FROM analysis_results LIMIT 1")
    print("  [OK] title fonctionne")
except Exception as e:
    print(f"  [ERROR] title: {e}")

print("\nTest direct SELECT sur articles_to_analyze:")
try:
    cursor.execute("SELECT title FROM articles_to_analyze LIMIT 1")
    print("  [OK] title fonctionne")
except Exception as e:
    print(f"  [ERROR] title: {e}")

db.close()