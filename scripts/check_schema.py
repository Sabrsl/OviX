import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Check analysis_results structure
cursor.execute("PRAGMA table_info(analysis_results)")
print("analysis_results columns:")
for row in cursor.fetchall():
    print(row)

# Check analysis_jobs structure  
cursor.execute("PRAGMA table_info(analysis_jobs)")
print("\nanalysis_jobs columns:")
for row in cursor.fetchall():
    print(row)

# Check for NULL article_title in analysis_results
cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE article_title IS NULL")
null_count = cursor.fetchone()[0]
print(f"\nRecords with NULL article_title: {null_count}")

conn.close()