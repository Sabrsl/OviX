"""
Audit complet des statuts dans OviX
Identifie toutes les utilisations de statuts dans backend, frontend, database, etc.
"""

import os
import re
from pathlib import Path

# Répertoires à analyser
directories = [
    "backend",
    "frontend/src",
    "src/wikipedia_maintenance",
]

# Statuts à rechercher
status_values = [
    "pending",
    "analyzing", 
    "running",
    "completed",
    "published",
    "rejected",
    "ignored",
    "error",
    "failed",
    "cancelled",
    "paused",
    "analyzed"
]

# Extensions de fichiers à analyser
extensions = [".py", ".tsx", ".ts", ".js"]

def find_status_usage():
    """Trouve toutes les utilisations de statuts dans le codebase."""
    results = {}
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
            
        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for status in status_values:
                        # Cherche les patterns comme status='pending', status="pending", etc.
                        patterns = [
                            rf"status\s*=\s*['\"]{status}['\"]",
                            rf"['\"]{status}['\"].*status",
                            rf"status.*{status}",
                            rf"{status}.*status",
                        ]
                        
                        for pattern in patterns:
                            matches = re.finditer(pattern, content, re.IGNORECASE)
                            for match in matches:
                                line_num = content[:match.start()].count('\n') + 1
                                line_content = content.split('\n')[line_num - 1].strip()
                                
                                key = f"{file_path.relative_to(Path.cwd())}:{line_num}"
                                if key not in results:
                                    results[key] = {
                                        'file': str(file_path.relative_to(Path.cwd())),
                                        'line': line_num,
                                        'content': line_content,
                                        'statuses': []
                                    }
                                
                                if status not in results[key]['statuses']:
                                    results[key]['statuses'].append(status)
                except Exception as e:
                    print(f"Erreur lecture {file_path}: {e}")
    
    return results

def analyze_by_table():
    """Analyse les statuts par table SQLite."""
    table_status_mapping = {
        "articles_to_analyze": ["pending", "analyzing", "analyzed", "error", "cancelled"],
        "analysis_jobs": ["pending", "running", "completed", "failed", "cancelled"],
        "analysis_results": ["pending", "published", "rejected", "ignored", "error"],
        "manual_review_decisions": ["pending", "approved", "rejected"],
        "publication_jobs": ["pending", "running", "completed", "failed"],
    }
    
    return table_status_mapping

if __name__ == "__main__":
    print("=" * 80)
    print("AUDIT COMPLET DES STATUTS OviX")
    print("=" * 80)
    
    print("\n1. UTILISATIONS DANS LE CODE")
    print("-" * 80)
    results = find_status_usage()
    
    for key, info in sorted(results.items()):
        print(f"\n{info['file']}:{info['line']}")
        print(f"  {info['content']}")
        print(f"  Statuts: {', '.join(info['statuses'])}")
    
    print(f"\nTotal: {len(results)} occurrences trouvées")
    
    print("\n2. MAPPING STATUTS PAR TABLE")
    print("-" * 80)
    table_mapping = analyze_by_table()
    for table, statuses in table_mapping.items():
        print(f"\n{table}:")
        for status in statuses:
            print(f"  - {status}")
    
    print("\n3. AMBIGUÏTÉS IDENTIFIÉES")
    print("-" * 80)
    print("\n⚠️  'pending' utilisé dans plusieurs contextes:")
    print("   - articles_to_analyze.status='pending' → Article en attente d'analyse")
    print("   - analysis_jobs.status='pending' → Job en attente d'exécution")
    print("   - analysis_results.status='pending' → Analyse terminée, en attente de décision")
    print("   - manual_review_decisions.status='pending' → Review en attente")
    print("   - publication_jobs.status='pending' → Publication en attente")
    
    print("\n⚠️  'analyzing' utilisé dans plusieurs contextes:")
    print("   - articles_to_analyze.status='analyzing' → Article en cours d'analyse")
    print("   - analysis_jobs.status='running' → Job en cours d'exécution")
    print("   - API retourne 'analyzing' pour les jobs en cours")
    
    print("\n4. RECOMMANDATIONS")
    print("-" * 80)
    print("Séparer les statuts par domaine:")
    print("  - analysis_status: pending, analyzing, completed, failed")
    print("  - review_status: not_required, pending, approved, rejected, ignored")
    print("  - publication_status: not_published, pending, publishing, published, failed")
