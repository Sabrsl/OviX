import sqlite3
from pathlib import Path

db_path = Path("data/wikipedia_maintenance.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== Status of 'Firdavs Abduxoliqov' in analysis_results ===")
cursor.execute("SELECT article_title, status, published_at, revision_id FROM analysis_results WHERE article_title = ?", ('Firdavs Abduxoliqov',))
result = cursor.fetchone()
if result:
    print(f"  Title: {result[0]}")
    print(f"  Status: {result[1]}")
    print(f"  Published at: {result[2]}")
    print(f"  Revision ID: {result[3]}")
else:
    print("  Article not found in analysis_results")

print("\n=== All articles with status 'pending' or 'awaiting_decision' ===")
cursor.execute("SELECT article_title, status FROM analysis_results WHERE status IN ('pending', 'awaiting_decision') LIMIT 10")
results = cursor.fetchall()
for row in results:
    print(f"  {row[0]}: {row[1]}")

conn.close()
