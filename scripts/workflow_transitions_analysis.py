"""
ANALYSE DU WORKFLOW COMPLET OviX
Identifie toutes les transitions et leurs sources
"""

import re
from pathlib import Path

# Transitions identifiées dans le code
workflow_transitions = [
    {
        "transition": "Queue → Analysis Job",
        "table_from": "articles_to_analyze",
        "status_from": "pending",
        "table_to": "analysis_jobs",
        "status_to": "pending",
        "backend_file": "backend/api/routes/analysis.py",
        "endpoint": "POST /api/articles/{title}/analyze",
        "frontend": "AnalysisNew.tsx, ArticlesToAnalyze.tsx"
    },
    {
        "transition": "Analysis Job → Running",
        "table_from": "analysis_jobs",
        "status_from": "pending",
        "table_to": "analysis_jobs",
        "status_to": "running",
        "backend_file": "backend/api/routes/analysis.py",
        "endpoint": "execute_analysis()",
        "frontend": "AnalysisResults.tsx (polling)"
    },
    {
        "transition": "Analysis Job → Completed",
        "table_from": "analysis_jobs",
        "status_from": "running",
        "table_to": "analysis_jobs",
        "status_to": "completed",
        "backend_file": "backend/api/routes/analysis.py",
        "endpoint": "execute_analysis()",
        "frontend": "AnalysisResults.tsx (polling)"
    },
    {
        "transition": "Analysis Job → Analysis Result",
        "table_from": "analysis_jobs",
        "status_from": "completed",
        "table_to": "analysis_results",
        "status_to": "pending (→ awaiting_decision)",
        "backend_file": "backend/api/routes/analysis.py:452",
        "endpoint": "execute_analysis()",
        "frontend": "AnalysisResults.tsx"
    },
    {
        "transition": "Analysis Result → Published",
        "table_from": "analysis_results",
        "status_from": "pending (→ awaiting_decision)",
        "table_to": "analysis_results",
        "status_to": "published",
        "backend_file": "backend/api/routes/publication.py:268",
        "endpoint": "POST /api/publication/publish",
        "frontend": "PublicationReview.tsx, ArticleDetail.tsx"
    },
    {
        "transition": "Analysis Result → Rejected",
        "table_from": "analysis_results",
        "status_from": "pending (→ awaiting_decision)",
        "table_to": "analysis_results",
        "status_to": "rejected",
        "backend_file": "backend/api/routes/articles.py",
        "endpoint": "POST /api/articles/{title}/reject",
        "frontend": "ArticleDetail.tsx"
    },
    {
        "transition": "Analysis Result → Ignored",
        "table_from": "analysis_results",
        "status_from": "pending (→ awaiting_decision)",
        "table_to": "analysis_results",
        "status_to": "ignored",
        "backend_file": "backend/api/routes/articles.py",
        "endpoint": "POST /api/articles/{title}/ignore",
        "frontend": "ArticleDetail.tsx"
    },
    {
        "transition": "Manual Review → Approved",
        "table_from": "manual_review_decisions",
        "status_from": "pending",
        "table_to": "manual_review_decisions",
        "status_to": "approved",
        "backend_file": "backend/api/routes/manual_review.py",
        "endpoint": "POST /api/manual-review/approve",
        "frontend": "ManualReview.tsx"
    },
    {
        "transition": "Manual Review → Rejected",
        "table_from": "manual_review_decisions",
        "status_from": "pending",
        "table_to": "manual_review_decisions",
        "status_to": "rejected",
        "backend_file": "backend/api/routes/manual_review.py",
        "endpoint": "POST /api/manual-review/reject",
        "frontend": "ManualReview.tsx"
    }
]

print("=" * 80)
print("MATRICE DES TRANSITIONS DU WORKFLOW OviX")
print("=" * 80)

print("\n| Transition | Table From | Status From | Table To | Status To | Backend | Frontend |")
print("| ---------- | ---------- | ----------- | -------- | --------- | ------- | -------- |")

for t in workflow_transitions:
    print(f"| {t['transition']:<30} | {t['table_from']:<20} | {t['status_from']:<20} | {t['table_to']:<20} | {t['status_to']:<25} | {t['backend_file']:<40} | {t['frontend']:<30} |")

print("\n" + "=" * 80)
print("POINTS CRITIQUES POUR LA MIGRATION")
print("=" * 80)

print("\n1. Transition Analysis Job → Analysis Result")
print("   - backend/api/routes/analysis.py:452")
print("   - Actuel: status='pending'")
print("   - Après migration: status='awaiting_decision'")
print("   - Impact: CRITIQUE - C'est le point principal de la migration")

print("\n2. Endpoints qui lisent analysis_results.status")
print("   - GET /api/articles/results (filtre status)")
print("   - GET /api/articles/{title}/result")
print("   - GET /api/articles/{title}/status")
print("   - GET /api/articles/history")
print("   - GET /api/history/analyzed")
print("   - GET /api/history/published")
print("   - GET /api/manual-review")

print("\n3. Composants React qui affichent le statut")
print("   - AnalyzedHistory.tsx → STATUS_META")
print("   - ArticleHistory.tsx → getStatusText()")
print("   - ArticleStatusCard.tsx → getStatusText()")
print("   - AnalysisResults.tsx → STATUS_META (jobs)")

print("\n4. Polling")
print("   - ArticleStatusCard.tsx:33")
print("   - Condition: status === 'analyzing' || status === 'pending'")
print("   - Après migration: awaiting_decision ne doit PAS déclencher le polling")
print("   - Seuls analysis_jobs.running/analyzing doivent déclencher le polling")

print("\n5. Statistics")
print("   - backend/stats/repository.py:43")
print("   - Compteur: COUNT(analysis_results WHERE status='pending')")
print("   - Après migration: COUNT(analysis_results WHERE status='awaiting_decision')")

print("\n" + "=" * 80)
print("RISQUES IDENTIFIÉS")
print("=" * 80)

risks = [
    "CRITIQUE: ArticleStatusCard.tsx polling condition inclut 'pending'",
    "MOYEN: Statistics compteur 'pending' doit être mis à jour",
    "MOYEN: Tous les filtres 'status=pending' doivent être mis à jour",
    "FAIBLE: Libellés UI doivent afficher 'En attente de décision'",
    "FAIBLE: Fallback trackers doivent être vérifiés"
]

for i, risk in enumerate(risks, 1):
    print(f"\n{i}. {risk}")
