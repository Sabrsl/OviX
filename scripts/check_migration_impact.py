"""
VALIDATION READ-ONLY AVANT MIGRATION
Compte et vérifie l'impact de la migration pending → awaiting_decision
NE MODIFIE PAS LES DONNÉES
"""

import sqlite3

conn = sqlite3.connect('data/wikipedia_maintenance.db')
cursor = conn.cursor()

print("=" * 80)
print("VALIDATION READ-ONLY AVANT MIGRATION")
print("=" * 80)

print("\n1. COMPTE DES LIGNES PAR STATUT DANS analysis_results")
print("-" * 80)
cursor.execute("""
    SELECT status, COUNT(*) as count 
    FROM analysis_results 
    GROUP BY status
""")
results = cursor.fetchall()
total = 0
for status, count in results:
    print(f"  {status}: {count}")
    total += count
print(f"\n  TOTAL: {total}")

print("\n2. LIGNES AVEC status='pending' DANS analysis_results")
print("-" * 80)
cursor.execute("""
    SELECT COUNT(*) as count 
    FROM analysis_results 
    WHERE status = 'pending'
""")
pending_count = cursor.fetchone()[0]
print(f"  Nombre de lignes à migrer: {pending_count}")

print("\n3. ÉCHANTILLON DE LIGNES AVEC status='pending'")
print("-" * 80)
cursor.execute("""
    SELECT article_title, analysis_date, changes_count, mode
    FROM analysis_results 
    WHERE status = 'pending'
    LIMIT 5
""")
sample = cursor.fetchall()
if sample:
    for title, date, changes, mode in sample:
        print(f"  - {title} ({date}): {changes} changements, mode={mode}")
else:
    print("  Aucune ligne trouvée")

print("\n4. VÉRIFICATION DES DOUBLONS")
print("-" * 80)
cursor.execute("""
    SELECT article_title, COUNT(*) as count 
    FROM analysis_results 
    WHERE status = 'pending'
    GROUP BY article_title 
    HAVING count > 1
""")
duplicates = cursor.fetchall()
if duplicates:
    print(f"  ⚠️  {len(duplicates)} articles avec plusieurs entrées pending:")
    for title, count in duplicates[:5]:
        print(f"    - {title}: {count} entrées")
else:
    print("  ✅ Aucun doublon détecté")

print("\n5. COMPTE PAR STATUT DANS TOUTES LES TABLES")
print("-" * 80)

# articles_to_analyze
print("\n  articles_to_analyze:")
cursor.execute("""
    SELECT status, COUNT(*) as count 
    FROM articles_to_analyze 
    GROUP BY status
""")
for status, count in cursor.fetchall():
    print(f"    {status}: {count}")

# analysis_jobs
print("\n  analysis_jobs:")
cursor.execute("""
    SELECT status, COUNT(*) as count 
    FROM analysis_jobs 
    GROUP BY status
""")
for status, count in cursor.fetchall():
    print(f"    {status}: {count}")

# manual_review_decisions
print("\n  manual_review_decisions:")
cursor.execute("""
    SELECT status, COUNT(*) as count 
    FROM manual_review_decisions 
    GROUP BY status
""")
for status, count in cursor.fetchall():
    print(f"    {status}: {count}")

# publication_jobs
print("\n  publication_jobs:")
try:
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM publication_jobs 
        GROUP BY status
    """)
    for status, count in cursor.fetchall():
        print(f"    {status}: {count}")
except sqlite3.OperationalError:
    print("    (table non existente)")

print("\n6. VÉRIFICATION DES DONNÉES HISTORIQUES")
print("-" * 80)
cursor.execute("""
    SELECT MIN(analysis_date) as oldest, MAX(analysis_date) as newest
    FROM analysis_results 
    WHERE status = 'pending'
""")
oldest, newest = cursor.fetchone()
if oldest and newest:
    print(f"  Plus ancien: {oldest}")
    print(f"  Plus récent: {newest}")
else:
    print("  Aucune donnée")

print("\n7. RÉSUMÉ DE L'IMPACT")
print("-" * 80)
print(f"  Lignes à migrer: {pending_count}")
print(f"  Pourcentage du total: {(pending_count/total*100):.2f}%" if total > 0 else "  Pourcentage du total: N/A")
print(f"  Doublons détectés: {len(duplicates)}")
print(f"  Risque estimé: {'FAIBLE' if pending_count < 1000 else 'MOYEN' if pending_count < 10000 else 'ÉLEVÉ'}")

conn.close()
