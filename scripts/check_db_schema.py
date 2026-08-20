import sqlite3
from pathlib import Path

db_path = Path("data/wikipedia_maintenance.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== Schema of analysis_results table ===")
cursor.execute("PRAGMA table_info(analysis_results);")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

print("\n=== Schema of publication_jobs table ===")
cursor.execute("PRAGMA table_info(publication_jobs);")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()
