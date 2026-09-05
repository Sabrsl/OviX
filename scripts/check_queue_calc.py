import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

# 1. Articles dans scheduler_queue avec status 'queued', non publiés, et avec corrections valides
cursor.execute("""
    SELECT COUNT(*) as count FROM scheduler_queue sq
    WHERE sq.status = 'queued'
    AND EXISTS (
        SELECT 1 FROM analysis_results ar
        WHERE ar.article_title = sq.article_title
        AND ar.corrected_links_count > 0
        AND ar.status != 'published'
    )
""")
queued_count = cursor.fetchone()[0]
print(f'Articles dans scheduler_queue (queued): {queued_count}')

# 2. Articles dans analysis_results avec corrections qui ne sont pas dans scheduler_queue et non publiés
cursor.execute("""
    SELECT COUNT(*) as count FROM analysis_results ar
    WHERE ar.corrected_links_count > 0
    AND ar.status != 'published'
    AND NOT EXISTS (
        SELECT 1 FROM scheduler_queue sq 
        WHERE sq.article_title = ar.article_title 
        AND sq.status NOT IN ('completed', 'error', 'published')
    )
""")
analyzed_count = cursor.fetchone()[0]
print(f'Articles dans analysis_results avec corrections non dans scheduler_queue: {analyzed_count}')

total = queued_count + analyzed_count
print(f'Total calculé: {total}')

# Vérification manuelle : articles avec corrections non publiés
cursor.execute('SELECT COUNT(*) FROM analysis_results WHERE corrected_links_count > 0 AND status != "published"')
ready_to_publish = cursor.fetchone()[0]
print(f'Articles avec corrections non publiés: {ready_to_publish}')

conn.close()
