import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()
cursor.execute('UPDATE kill_switch_state SET enabled = 0, reason = "", trigger_source = "", requested_by = "", requested_at = NULL WHERE id = 1')
conn.commit()
print('Kill switch désactivé')
conn.close()
