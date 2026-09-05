import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# Total articles with corrections
cursor.execute('SELECT COUNT(*) FROM analysis_results WHERE corrected_links_count > 0')
total_with_corrections = cursor.fetchone()[0]
print(f'Total articles avec corrections: {total_with_corrections}')

# Published articles with corrections
cursor.execute('SELECT COUNT(*) FROM analysis_results WHERE corrected_links_count > 0 AND status = "published"')
published_with_corrections = cursor.fetchone()[0]
print(f'Articles publiés avec corrections: {published_with_corrections}')

# Ready to publish (with corrections, not published)
cursor.execute('SELECT COUNT(*) FROM analysis_results WHERE corrected_links_count > 0 AND status != "published"')
ready_to_publish = cursor.fetchone()[0]
print(f'Articles prêts à publier: {ready_to_publish}')

print(f'Vérification: {total_with_corrections} = {published_with_corrections} + {ready_to_publish} = {published_with_corrections + ready_to_publish}')

conn.close()
