import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Total dans scheduler_queue
cursor.execute('SELECT COUNT(*) FROM scheduler_queue')
total_queue = cursor.fetchone()[0]
print(f'Total dans scheduler_queue: {total_queue}')

# Par status
cursor.execute('SELECT status, COUNT(*) FROM scheduler_queue GROUP BY status')
status_counts = cursor.fetchall()
print('\nPar status:')
for status, count in status_counts:
    print(f'  {status}: {count}')

# Voir quelques entrées
cursor.execute('SELECT title, status, added_at FROM scheduler_queue LIMIT 5')
print('\n5 premières entrées:')
for row in cursor.fetchall():
    print(f'  {row[0]} - {row[1]} - {row[2]}')

conn.close()
