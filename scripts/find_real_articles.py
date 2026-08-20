import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Find articles with actual content
cursor.execute("""
    SELECT article_title, corrected_content, original_content, status
    FROM analysis_results
    WHERE corrected_content IS NOT NULL
    AND article_title NOT LIKE '%.%'
    AND article_title NOT LIKE '%\\%'
    LIMIT 10
""")

articles = cursor.fetchall()
print("Articles with content:")
for row in articles:
    title, corrected, original, status = row
    print(f"  - '{title}' (status: {status})")
    print(f"    Has corrected: {corrected is not None}")
    print(f"    Has original: {original is not None}")

if articles:
    test_title = articles[0][0]
    print(f"\n\nTesting API with: '{test_title}'")
    
    # Test if it would match in SQL
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
        print(f"SQL query found: {row[0]}")
    else:
        print("SQL query found nothing")

conn.close()