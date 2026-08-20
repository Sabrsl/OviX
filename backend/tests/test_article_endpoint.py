import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Test the exact query used in the endpoint
article_title = "24H Series 2025"
cursor.execute("""
    SELECT article_title, page_id, revision_id, status, analysis_date, changes_count, 
           summary, corrected_content, character_count, mode, human_verified, 
           original_content, total_links, dead_links_count, corrected_links_count
    FROM analysis_results
    WHERE article_title = ?
    ORDER BY analysis_date DESC
    LIMIT 1
""", (article_title,))

row = cursor.fetchone()
if row:
    print(f"Found article: {row[0]}")
    print(f"Status: {row[3]}")
    print(f"Has corrected_content: {row[7] is not None}")
    print(f"Has original_content: {row[11] is not None}")
else:
    print("Article not found in database")

# Check all article titles
cursor.execute("SELECT article_title FROM analysis_results LIMIT 5")
print("\nFirst 5 article titles:")
for row in cursor.fetchall():
    print(f"  - '{row[0]}'")

conn.close()