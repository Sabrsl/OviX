import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM analysis_results WHERE status = "published"')
print('Published:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM analysis_results WHERE status = "pending"')
print('Pending:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM analysis_results')
print('Total:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM manual_review_decisions')
print('Decisions:', cursor.fetchone()[0])

conn.close()