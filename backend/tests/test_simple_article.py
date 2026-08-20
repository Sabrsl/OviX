import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Find a simple article title
cursor.execute("SELECT article_title FROM analysis_results WHERE article_title NOT LIKE '%[^a-zA-Z0-9 .%-]%' LIMIT 5")
simple_articles = cursor.fetchall()
print("Simple article titles:")
for row in simple_articles:
    print(f"  - '{row[0]}'")

if simple_articles:
    test_title = simple_articles[0][0]
    print(f"\nTesting with: '{test_title}'")
    
    cursor.execute("""
        SELECT article_title, page_id, revision_id, status, analysis_date, changes_count, 
               summary, corrected_content, character_count, mode, human_verified, 
               original_content, total_links, dead_links_count, corrected_links_count
        FROM analysis_results
        WHERE article_title = ?
        ORDER BY analysis_date DESC
        LIMIT 1
    """, (test_title,))
    
    row = cursor.fetchone()
    if row:
        print(f"Found: {row[0]}")
        print(f"Status: {row[3]}")
        print(f"Has corrected_content: {row[7] is not None}")
        print(f"Has original_content: {row[11] is not None}")

conn.close()