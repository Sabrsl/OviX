from pathlib import Path
import sys
import os

# Set up paths like the backend does
project_root = Path("C:/Users/badza/Desktop/Sabrsl_dead_linker_Bot")
os.environ['PYWIKIBOT_DIR'] = str(project_root)
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Import database manager
from wikipedia_maintenance.utils.database import DatabaseManager

db_path = str(project_root / "data" / "wikipedia_maintenance.db")
print(f"Database path: {db_path}")

try:
    db = DatabaseManager(db_path)
    print(f"Database initialized successfully")
    
    # Test connection
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM analysis_results")
    count = cursor.fetchone()[0]
    print(f"Analysis results count: {count}")
    
    cursor.execute("SELECT article_title FROM analysis_results LIMIT 5")
    titles = cursor.fetchall()
    print(f"Sample titles: {[t[0] for t in titles]}")
    
    # Check if Jean-Luc Balthazar exists
    cursor.execute("SELECT article_title FROM analysis_results WHERE article_title = ?", ("Jean-Luc Balthazar",))
    result = cursor.fetchone()
    print(f"Jean-Luc Balthazar found: {result is not None}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()