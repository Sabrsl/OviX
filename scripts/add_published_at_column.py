import sqlite3
from pathlib import Path

db_path = Path("data/wikipedia_maintenance.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== Adding published_at column to analysis_results ===")

try:
    cursor.execute("ALTER TABLE analysis_results ADD COLUMN published_at TIMESTAMP")
    conn.commit()
    print("✅ Column 'published_at' added successfully")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("⚠️ Column 'published_at' already exists")
    else:
        print(f"❌ Error: {e}")
        conn.close()
        exit(1)

# Verify
print("\n=== Updated schema of analysis_results table ===")
cursor.execute("PRAGMA table_info(analysis_results);")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()
print("\n✅ Migration completed")
