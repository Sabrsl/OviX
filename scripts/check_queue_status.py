import sqlite3

# Check what statuses exist in scheduler_queue
db_path = 'data/wikipedia_maintenance.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

cursor = conn.cursor()
cursor.execute("SELECT DISTINCT status, COUNT(*) as count FROM scheduler_queue GROUP BY status")
rows = cursor.fetchall()

print("Status distribution in scheduler_queue:")
for row in rows:
    print(f"  {row['status']}: {row['count']}")

conn.close()
