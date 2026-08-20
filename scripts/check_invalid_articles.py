import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Check for filenames in article titles
cursor.execute("SELECT article_title FROM analysis_results WHERE article_title LIKE '%.ps1' OR article_title LIKE '%.py' OR article_title LIKE '%.md' OR article_title LIKE '%.json' OR article_title LIKE '%.txt' LIMIT 20")
rows = cursor.fetchall()

print('Fichiers dans la base de données:')
for row in rows:
    print(f'  - {row[0]}')

# Count total invalid entries
cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE article_title LIKE '%.ps1' OR article_title LIKE '%.py' OR article_title LIKE '%.md' OR article_title LIKE '%.json' OR article_title LIKE '%.txt'")
invalid_count = cursor.fetchone()[0]
print(f'\nTotal entrées invalides: {invalid_count}')

conn.close()
