import sqlite3
import sys
sys.path.insert(0, '.')

# Test the database methods directly
db_path = 'data/wikipedia_maintenance.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("Testing database methods...")

# Test queue size calculation
cursor = conn.cursor()
cursor.execute("""
    SELECT COUNT(*) as count FROM scheduler_queue 
    WHERE status = 'queued'
""")
row = cursor.fetchone()
queued_count = row['count'] if row else 0
print(f"Queued articles: {queued_count}")

# Count analyzed articles with valid corrections
cursor.execute("""
    SELECT COUNT(*) as count FROM analysis_results ar
    WHERE ar.corrected_links_count > 0
    AND NOT EXISTS (
        SELECT 1 FROM scheduler_queue sq 
        WHERE sq.article_title = ar.article_title 
        AND sq.status NOT IN ('completed', 'error', 'published')
    )
""")
row = cursor.fetchone()
analyzed_count = row['count'] if row else 0
print(f"Analyzed articles with corrections (not in queue): {analyzed_count}")

total_count = queued_count + analyzed_count
print(f"Total queue size: {total_count}")

# Test statistics
cursor.execute("""
    SELECT COUNT(*) as count FROM analysis_results 
    WHERE corrected_links_count > 0
""")
row = cursor.fetchone()
analyzed_with_corrections = row['count'] if row else 0
print(f"Total analyzed with corrections: {analyzed_with_corrections}")

conn.close()
print("Database test completed successfully!")
