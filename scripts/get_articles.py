import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Get first few articles
cursor.execute("SELECT article_title FROM analysis_results LIMIT 10")
articles = cursor.fetchall()
print("Articles in database:")
for i, (title,) in enumerate(articles, 1):
    print(f"{i}. {title}")

conn.close()