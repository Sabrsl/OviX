from wikipedia_maintenance.utils.database import DatabaseManager
import os
from pathlib import Path

db = DatabaseManager(str(Path(os.environ.get('PROJECT_ROOT', '.')) / 'data' / 'wikipedia_maintenance.db'))
cursor = db.conn.cursor()

cursor.execute('SELECT COUNT(*) FROM articles_to_analyze')
total = cursor.fetchone()[0]
print(f'Total articles in queue: {total}')

cursor.execute('SELECT title, status, source FROM articles_to_analyze LIMIT 10')
rows = cursor.fetchall()
print('Sample articles:')
for r in rows:
    print(f'  - {r[0]} (status: {r[1]}, source: {r[2]})')

# Check status distribution
cursor.execute('SELECT status, COUNT(*) FROM articles_to_analyze GROUP BY status')
status_counts = cursor.fetchall()
print('\nStatus distribution:')
for status, count in status_counts:
    print(f'  - {status}: {count}')
