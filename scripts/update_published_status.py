import sqlite3
from pathlib import Path
from datetime import datetime

db_path = Path("data/wikipedia_maintenance.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== Updating 'Firdavs Abduxoliqov' status to published ===")

# Update the article status
cursor.execute("""
    UPDATE analysis_results 
    SET status = 'published',
        published_at = ?
    WHERE article_title = ?
""", (datetime.now().isoformat(), 'Firdavs Abduxoliqov'))

conn.commit()

# Verify
cursor.execute("SELECT article_title, status, published_at, revision_id FROM analysis_results WHERE article_title = ?", ('Firdavs Abduxoliqov',))
result = cursor.fetchone()
if result:
    print(f"  Title: {result[0]}")
    print(f"  Status: {result[1]}")
    print(f"  Published at: {result[2]}")
    print(f"  Revision ID: {result[3]}")
    print("✅ Status updated successfully")
else:
    print("❌ Article not found")

conn.close()
