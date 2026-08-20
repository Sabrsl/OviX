import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Check for NULL article_title in analysis_results
cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE article_title IS NULL")
null_count = cursor.fetchone()[0]
print(f"Records with NULL article_title: {null_count}")

# Fix NULL article_title by using job information
cursor.execute("""
    UPDATE analysis_results 
    SET article_title = (
        SELECT article_title 
        FROM analysis_jobs 
        WHERE analysis_jobs.job_id = analysis_results.job_id
    )
    WHERE article_title IS NULL
""")
fixed_count = cursor.rowcount
print(f"Fixed {fixed_count} records")

conn.commit()

# Check again
cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE article_title IS NULL")
null_count_after = cursor.fetchone()[0]
print(f"Records with NULL article_title after fix: {null_count_after}")

conn.close()