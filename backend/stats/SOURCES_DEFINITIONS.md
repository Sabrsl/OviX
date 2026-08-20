# Définitions officielles des sources de statistiques métier

## Principe fondamental

**Database SQLite = SEULE source de vérité pour les statistiques métier**

Les trackers JSON restent pour l'opérationnel mais ne sont plus une source statistique.

## 8 familles de statistiques métier - Sources officielles

### 1. Articles

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| articles_total | COUNT(analysis_results) | get_article_stats().total | get_article_stats() | /api/stats/v2/articles | Total des analyses |
| articles_analyzed | COUNT(analysis_results WHERE status IN ('published','rejected','ignored','error')) | get_article_stats().analyzed | get_article_stats() | /api/stats/v2/articles | Articles analysés |
| articles_published | COUNT(analysis_results WHERE status='published') | get_article_stats().published | get_article_stats() | /api/stats/v2/articles | Articles publiés |
| articles_pending | COUNT(analysis_results WHERE status='pending') | get_article_stats().pending | get_article_stats() | /api/stats/v2/articles | En attente |
| articles_rejected | COUNT(analysis_results WHERE status='rejected') | get_article_stats().rejected | get_article_stats() | /api/stats/v2/articles | Rejetés |
| articles_ignored | COUNT(analysis_results WHERE status='ignored') | get_article_stats().ignored | get_article_stats() | /api/stats/v2/articles | Ignorés |
| articles_error | COUNT(analysis_results WHERE status='error') | get_article_stats().error | get_article_stats() | /api/stats/v2/articles | Erreurs |
| articles_skipped | COUNT(analysis_results WHERE status='skipped') | get_article_stats().skipped | get_article_stats() | /api/stats/v2/articles | Sautés |

### 2. Analyses

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| analyses_total | COUNT(analysis_jobs) ou COUNT(analysis_results) | get_analysis_stats().total | get_analysis_stats() | /api/stats/v2/analysis | Total analyses |
| analyses_pending | COUNT(analysis_jobs WHERE status='pending') | get_analysis_stats().pending | get_analysis_stats() | /api/stats/v2/analysis | En attente |
| analyses_running | COUNT(analysis_jobs WHERE status='running') | get_analysis_stats().running | get_analysis_stats() | /api/stats/v2/analysis | En cours |
| analyses_completed | COUNT(analysis_jobs WHERE status='completed') | get_analysis_stats().completed | get_analysis_stats() | /api/stats/v2/analysis | Terminées |
| analyses_successful | COUNT(analysis_jobs WHERE status='completed' AND error IS NULL) | get_analysis_stats().successful | get_analysis_stats() | /api/stats/v2/analysis | Réussies |
| analyses_failed | COUNT(analysis_jobs WHERE status='failed') | get_analysis_stats().failed | get_analysis_stats() | /api/stats/v2/analysis | Échouées |
| analyses_cancelled | COUNT(analysis_jobs WHERE status='cancelled') | get_analysis_stats().cancelled | get_analysis_stats() | /api/stats/v2/analysis | Annulées |
| success_rate | (successful/completed)*100 | get_analysis_stats().success_rate | get_analysis_stats() | /api/stats/v2/analysis | Taux de succès |
| failure_rate | (failed/completed)*100 | get_analysis_stats().failure_rate | get_analysis_stats() | /api/stats/v2/analysis | Taux d'échec |
| average_duration | AVG(completed_at - started_at) | get_analysis_stats().average_duration | get_analysis_stats() | /api/stats/v2/analysis | Durée moyenne (s) |

### 3. Publications

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| publications_total | COUNT(analysis_results WHERE status='published') | get_publication_stats().total | get_publication_stats() | /api/stats/v2/publication | Total publications |
| publications_successful | COUNT(actions WHERE action_type='publish') | get_publication_stats().successful | get_publication_stats() | /api/stats/v2/publication | Réussies |
| publications_failed | COUNT(actions WHERE action_type='publish_failed') | get_publication_stats().failed | get_publication_stats() | /api/stats/v2/publication | Échouées |
| publications_pending | COUNT(analysis_results WHERE status='published' AND human_verified=0) | get_publication_stats().pending | get_publication_stats() | /api/stats/v2/publication | En attente |
| publications_cancelled | COUNT(actions WHERE action_type='cancel') | get_publication_stats().cancelled | get_publication_stats() | /api/stats/v2/publication | Annulées |
| publication_rate | (published/total)*100 | get_publication_stats().publication_rate | get_publication_stats() | /api/stats/v2/publication | Taux de publication |
| publication_success_rate | (successful/(successful+failed))*100 | get_publication_stats().success_rate | get_publication_stats() | /api/stats/v2/publication | Taux de succès |
| publications_recent_24h | COUNT(analysis_results WHERE status='published' AND analysis_date >= NOW-24h) | get_publication_stats().recent_24h | get_publication_stats() | /api/stats/v2/publication | 24 dernières heures |
| publications_recent_7d | COUNT(analysis_results WHERE status='published' AND analysis_date >= NOW-7d) | get_publication_stats().recent_7d | get_publication_stats() | /api/stats/v2/publication | 7 derniers jours |
| publications_recent_30d | COUNT(analysis_results WHERE status='published' AND analysis_date >= NOW-30d) | get_publication_stats().recent_30d | get_publication_stats() | /api/stats/v2/publication | 30 derniers jours |

### 4. Corrections

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| total_corrections | SUM(changes_count) | get_correction_stats().total_corrections | get_correction_stats() | /api/stats/v2/corrections | Total corrections |
| typos_fixed | COUNT(issues WHERE issue_type LIKE '%typo%') | get_correction_stats().typos_fixed | get_correction_stats() | /api/stats/v2/corrections | Fautes corrigées |
| formatting_fixed | COUNT(issues WHERE issue_type LIKE '%format%') | get_correction_stats().formatting_fixed | get_correction_stats() | /api/stats/v2/corrections | Formatage corrigé |
| dead_links_detected | SUM(dead_links_count) | get_correction_stats().dead_links_detected | get_correction_stats() | /api/stats/v2/corrections | Liens morts détectés |
| dead_links_corrected | SUM(corrected_links_count) | get_correction_stats().dead_links_corrected | get_correction_stats() | /api/stats/v2/corrections | Liens morts corrigés |
| http_links_corrected | COUNT(issues WHERE issue_type LIKE '%http%' AND suggested_text LIKE 'https%') | get_correction_stats().http_links_corrected | get_correction_stats() | /api/stats/v2/corrections | HTTP→HTTPS |

### 5. Queue

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| queue_total | COUNT(articles_to_analyze) | get_queue_stats().total | get_queue_stats() | /api/stats/v2/queue | Total dans queue |
| queue_pending | COUNT(articles_to_analyze WHERE status='pending') | get_queue_stats().pending | get_queue_stats() | /api/stats/v2/queue | En attente |
| queue_processing | COUNT(articles_to_analyze WHERE status='analyzing') | get_queue_stats().processing | get_queue_stats() | /api/stats/v2/queue | En traitement |
| queue_completed | COUNT(articles_to_analyze WHERE status='analyzed') | get_queue_stats().completed | get_queue_stats() | /api/stats/v2/queue | Terminés |
| queue_failed | COUNT(articles_to_analyze WHERE status='error') | get_queue_stats().failed | get_queue_stats() | /api/stats/v2/queue | Échoués |
| queue_cancelled | COUNT(articles_to_analyze WHERE status='cancelled') | get_queue_stats().cancelled | get_queue_stats() | /api/stats/v2/queue | Annulés |
| queue_success_rate | (completed/(completed+failed))*100 | get_queue_stats().success_rate | get_queue_stats() | /api/stats/v2/queue | Taux de succès |
| average_wait_time | AVG(started_at - added_at) | get_queue_stats().average_wait_time | get_queue_stats() | /api/stats/v2/queue | Temps d'attente moyen (s) |

### 6. Qualité

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| articles_with_issues | COUNT(analysis_results WHERE changes_count > 0) | get_quality_stats().articles_with_issues | get_quality_stats() | /api/stats/v2/quality | Avec issues |
| articles_without_issues | COUNT(analysis_results WHERE changes_count = 0) | get_quality_stats().articles_without_issues | get_quality_stats() | /api/stats/v2/quality | Sans issues |
| issues_by_severity | GROUP BY severity FROM issues | get_quality_stats().issues_by_severity | get_quality_stats() | /api/stats/v2/quality | Par sévérité |
| errors_by_type | GROUP BY issue_type FROM issues WHERE severity='error' | get_quality_stats().errors_by_type | get_quality_stats() | /api/stats/v2/quality | Erreurs par type |
| issue_rate | (articles_with_issues/total)*100 | get_quality_stats().issue_rate | get_quality_stats() | /api/stats/v2/quality | Taux d'issues |
| dead_link_rate | (dead_links/total_links)*100 | get_quality_stats().dead_link_rate | get_quality_stats() | /api/stats/v2/quality | Taux de liens morts |
| correction_rate | (corrected/detected)*100 | get_quality_stats().correction_rate | get_quality_stats() | /api/stats/v2/quality | Taux de correction |

### 7. Pipeline

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| pipeline_runs | COUNT(sessions) | get_pipeline_stats().runs | get_pipeline_stats() | /api/stats/v2/pipeline | Exécutions totales |
| pipeline_success | COUNT(sessions WHERE ended_at IS NOT NULL) | get_pipeline_stats().success | get_pipeline_stats() | /api/stats/v2/pipeline | Réussies |
| pipeline_failed | COUNT(sessions WHERE ended_at IS NULL AND started_at < NOW-1h) | get_pipeline_stats().failed | get_pipeline_stats() | /api/stats/v2/pipeline | Échouées |
| pipeline_running | COUNT(sessions WHERE ended_at IS NULL AND started_at >= NOW-1h) | get_pipeline_stats().running | get_pipeline_stats() | /api/stats/v2/pipeline | En cours |
| articles_processed | SUM(articles_analyzed) FROM sessions | get_pipeline_stats().articles_processed | get_pipeline_stats() | /api/stats/v2/pipeline | Articles traités |
| articles_remaining | COUNT(articles_to_analyze WHERE status='pending') | get_pipeline_stats().articles_remaining | get_pipeline_stats() | /api/stats/v2/pipeline | Articles restants |
| analyses_completed | COUNT(analysis_jobs WHERE status='completed') | get_pipeline_stats().analyses_completed | get_pipeline_stats() | /api/stats/v2/pipeline | Analyses terminées |
| publications_completed | COUNT(analysis_results WHERE status='published') | get_pipeline_stats().publications_completed | get_pipeline_stats() | /api/stats/v2/pipeline | Publications terminées |
| pipeline_duration | AVG(ended_at - started_at) FROM sessions | get_pipeline_stats().pipeline_duration | get_pipeline_stats() | /api/stats/v2/pipeline | Durée moyenne (s) |
| average_processing_time | AVG(completed_at - started_at) FROM analysis_jobs | get_pipeline_stats().average_processing_time | get_pipeline_stats() | /api/stats/v2/pipeline | Temps/article moyen (s) |

### 8. Temporel (Time-based)

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| articles_published_today | COUNT(analysis_results WHERE status='published' AND analysis_date >= TODAY) | get_temporal_stats().articles_published_today | get_temporal_stats() | /api/stats/v2/temporal | Aujourd'hui |
| analyses_today | COUNT(analysis_jobs WHERE created_at >= TODAY) | get_temporal_stats().analyses_today | get_temporal_stats() | /api/stats/v2/temporal | Analyses aujourd'hui |
| corrections_today | SUM(changes_count) WHERE analysis_date >= TODAY | get_temporal_stats().corrections_today | get_temporal_stats() | /api/stats/v2/temporal | Corrections aujourd'hui |
| errors_today | COUNT(analysis_jobs WHERE status='failed' AND created_at >= TODAY) | get_temporal_stats().errors_today | get_temporal_stats() | /api/stats/v2/temporal | Erreurs aujourd'hui |
| articles_published_7d | COUNT(analysis_results WHERE status='published' AND analysis_date >= NOW-7d) | get_temporal_stats().articles_published_7d | get_temporal_stats() | /api/stats/v2/temporal | 7 derniers jours |
| analyses_7d | COUNT(analysis_jobs WHERE created_at >= NOW-7d) | get_temporal_stats().analyses_7d | get_temporal_stats() | /api/stats/v2/temporal | Analyses 7j |
| corrections_7d | SUM(changes_count) WHERE analysis_date >= NOW-7d | get_temporal_stats().corrections_7d | get_temporal_stats() | /api/stats/v2/temporal | Corrections 7j |
| errors_7d | COUNT(analysis_jobs WHERE status='failed' AND created_at >= NOW-7d) | get_temporal_stats().errors_7d | get_temporal_stats() | /api/stats/v2/temporal | Erreurs 7j |
| articles_published_30d | COUNT(analysis_results WHERE status='published' AND analysis_date >= NOW-30d) | get_temporal_stats().articles_published_30d | get_temporal_stats() | /api/stats/v2/temporal | 30 derniers jours |
| analyses_30d | COUNT(analysis_jobs WHERE created_at >= NOW-30d) | get_temporal_stats().analyses_30d | get_temporal_stats() | /api/stats/v2/temporal | Analyses 30j |
| corrections_30d | SUM(changes_count) WHERE analysis_date >= NOW-30d | get_temporal_stats().corrections_30d | get_temporal_stats() | /api/stats/v2/temporal | Corrections 30j |
| errors_30d | COUNT(analysis_jobs WHERE status='failed' AND created_at >= NOW-30d) | get_temporal_stats().errors_30d | get_temporal_stats() | /api/stats/v2/temporal | Erreurs 30j |

### 9. Erreurs (Errors)

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| errors_total | COUNT(analysis_jobs WHERE status='failed') | get_error_stats().total | get_error_stats() | /api/stats/v2/errors | Total erreurs |
| errors_today | COUNT(analysis_jobs WHERE status='failed' AND created_at >= TODAY) | get_error_stats().today | get_error_stats() | /api/stats/v2/errors | Erreurs aujourd'hui |
| errors_by_type | GROUP BY error FROM analysis_jobs WHERE status='failed' | get_error_stats().by_type | get_error_stats() | /api/stats/v2/errors | Par type |
| errors_by_module | GROUP BY mode FROM analysis_jobs WHERE status='failed' | get_error_stats().by_module | get_error_stats() | /api/stats/v2/errors | Par module |
| errors_by_stage | GROUP BY status FROM analysis_jobs WHERE status='failed' | get_error_stats().by_stage | get_error_stats() | /api/stats/v2/errors | Par étape |

### 10. Database

| Statistique | Source DB | Repository | Service | Endpoint | Notes |
|-------------|-----------|------------|---------|----------|-------|
| db_articles_total | COUNT(articles) | get_database_stats().articles_total | get_database_stats() | /api/stats/v2/database | Articles dans DB |
| db_issues_total | COUNT(issues) | get_database_stats().issues_total | get_database_stats() | /api/stats/v2/database | Issues totales |
| db_actions_total | COUNT(actions) | get_database_stats().actions_total | get_database_stats() | /api/stats/v2/database | Actions totales |
| articles_with_changes | COUNT(analysis_results WHERE changes_count > 0) | get_database_stats().articles_with_changes | get_database_stats() | /api/stats/v2/database | Avec modifications |

## Règles strictes

1. **UNIQUE source** : Chaque statistique a exactement 1 source DB
2. **PAS de recalcul** : Les valeurs sont agrégées, pas recalculées
3. **PAS de fallback JSON** : Les trackers ne sont plus source statistique
4. **Centralisation** : Tout passe par StatsRepository → StatsService
5. **Type safety** : Pydantic schemas garantissent la cohérence
6. **Fallback gracieux** : Si une table/colonne n'existe pas, retourne 0 ou {}

## Trackers JSON - Rôle opérationnel uniquement

| Tracker | Usage opérationnel | Source statistique ? |
|---------|-------------------|---------------------|
| analyzed_articles.json | Détection articles déjà traités, pipeline d'analyse | **NON** |
| published_articles.json | Détection articles récemment publiés, éviter republication | **NON** |
| manual_review_decisions.json | Décisions de revue manuelle | **NON** |

**Les trackers JSON ne sont plus utilisés comme source de statistiques métier.**

## Frontière stricte - Ce qui N'EST PAS centralisé

### ❌ Articles individuels
- GET /api/articles (liste d'articles)
- GET /api/articles/{id} (détail d'un article)
- Ces endpoints métier restent indépendants

### ❌ Logs bruts
- GET /api/logs (logs bruts)
- GET /api/logs/stats (statistiques de logs, si applicables)
- Logs sont du monitoring technique, pas des stats métier

### ❌ État opérationnel
- Worker actuellement en train de traiter article X
- Queue opérationnelle en temps réel
- Orchestration et orchestrateur

### ⚠️ Queue et Pipeline - Séparation de responsabilité

**IMPORTANT** : Queue et Pipeline ne sont PAS uniquement des statistiques.

```
QueueService / Orchestrator
    ↓
État réel de la queue/pipeline
    ↓
StatsService (MESURE SEULEMENT)
    ↓
queue_total, queue_pending, pipeline_runs, pipeline_success
```

**StatsService mesure** mais ne devient pas responsable de la queue ou du pipeline. Les endpoints `/api/stats/v2/queue` et `/api/stats/v2/pipeline` fournissent des **statistiques agrégées** basées sur l'état réel, mais ne remplacent pas les services opérationnels.

## Architecture recommandée

```
Database (SQLite) = SEULE source de vérité
    ↓
StatsRepository (accès DB centralisé)
    ↓
StatsService (logique métier centralisée)
    ↓
Stats API (/api/stats/v2/*)
    ↓
Frontend (Dashboard, Analytics, Monitoring)
```

**ET parallèlement :**

```
Database
    ↓
    ├── ArticleRepository (pour articles individuels)
    ├── AnalysisRepository (pour analyses individuelles)
    ├── PublicationRepository (pour publications individuelles)
    └── StatsRepository (pour agrégations statistiques UNIQUEMENT)
```

