# Analyse du schéma DB pour les 8 familles de statistiques

## Tables disponibles

### 1. articles
- id, title, page_id, retrieved_at, last_revision_id, source_type, source_info, status
- **Pour** : Articles (total, par status)

### 2. issues
- id, article_id, issue_type, description, position, original_text, suggested_text, severity, created_at
- **Pour** : Qualité (issues_by_severity, errors_by_type), Corrections (par issue_type)

### 3. actions
- id, article_id, action_type, edit_summary, revision_id, performed_at
- **Pour** : Publications (par action_type), Corrections (par action_type)

### 4. sessions
- id, started_at, ended_at, articles_analyzed, articles_approved, articles_ignored, source_type, notes
- **Pour** : Pipeline (runs, articles_processed), Analyses (duration)

### 5. analysis_jobs
- id, article_title, mode, status, progress, message, started_at, completed_at, error, created_at, ai_provider, ai_character_limit, gemini_api_key, gemini_project_id
- **Pour** : Analyses (total, par status, duration), Pipeline (runs)

### 6. analysis_results
- id, job_id, article_title, page_id, revision_id, status, mode, changes_count, summary, original_content, corrected_content, character_count, total_links, dead_links_count, corrected_links_count, human_verified, analysis_date
- **Pour** : Articles (analysés, par status), Analyses (completed), Publications (par status), Corrections (dead_links, changes), Qualité (articles_with_issues)

### 7. articles_to_analyze
- id, title, page_id, revision_id, source, source_details, priority, added_at, started_at, analyzed_at, status, job_id
- **Pour** : Queue (total, par status), Pipeline (articles_remaining)

### 8. manual_review_decisions
- id, article_title, url, status, decision_date, reviewer_id, decision_reason, article_id, url_hash, created_at, updated_at
- **Pour** : Qualité (manual_review stats)

## Mapping 8 familles → Tables

### 1. Articles
- **total** : COUNT(analysis_results)
- **analysés** : COUNT(analysis_results WHERE status IN ('published','rejected','ignored','error'))
- **publiés** : COUNT(analysis_results WHERE status='published')
- **pending** : COUNT(analysis_results WHERE status='pending')
- **rejetés** : COUNT(analysis_results WHERE status='rejected')
- **ignorés** : COUNT(analysis_results WHERE status='ignored')
- **error** : COUNT(analysis_results WHERE status='error')
- **skipped** : COUNT(analysis_results WHERE status='skipped') (si existe)

### 2. Analyses
- **total** : COUNT(analysis_jobs)
- **pending** : COUNT(analysis_jobs WHERE status='pending')
- **running** : COUNT(analysis_jobs WHERE status='running')
- **completed** : COUNT(analysis_jobs WHERE status='completed')
- **successful** : COUNT(analysis_jobs WHERE status='completed' AND error IS NULL)
- **failed** : COUNT(analysis_jobs WHERE status='failed')
- **cancelled** : COUNT(analysis_jobs WHERE status='cancelled')
- **success_rate** : successful / completed * 100
- **failure_rate** : failed / completed * 100
- **average_duration** : AVG(completed_at - started_at) WHERE status='completed'

### 3. Publications
- **total** : COUNT(analysis_results WHERE status='published')
- **successful** : COUNT(actions WHERE action_type='publish')
- **failed** : COUNT(actions WHERE action_type='publish_failed')
- **pending** : COUNT(analysis_results WHERE status='published' AND published_at IS NULL)
- **cancelled** : COUNT(actions WHERE action_type='cancel')
- **publication_rate** : published / analyzed * 100
- **success_rate** : successful / (successful + failed) * 100

### 4. Corrections
- **typos_fixed** : COUNT(issues WHERE issue_type LIKE '%typo%')
- **formatting_fixed** : COUNT(issues WHERE issue_type LIKE '%format%')
- **dead_links_detected** : SUM(dead_links_count) FROM analysis_results
- **dead_links_corrected** : SUM(corrected_links_count) FROM analysis_results
- **http_links_corrected** : COUNT(issues WHERE issue_type LIKE '%http%' AND suggested_text LIKE 'https%')
- **total_corrections** : SUM(changes_count) FROM analysis_results

### 5. Queue
- **total** : COUNT(articles_to_analyze)
- **pending** : COUNT(articles_to_analyze WHERE status='pending')
- **processing** : COUNT(articles_to_analyze WHERE status='analyzing')
- **completed** : COUNT(articles_to_analyze WHERE status='analyzed')
- **failed** : COUNT(articles_to_analyze WHERE status='error')
- **cancelled** : COUNT(articles_to_analyze WHERE status='cancelled')
- **success_rate** : completed / (completed + failed) * 100
- **average_wait_time** : AVG(started_at - added_at) WHERE status IN ('analyzed','error')

### 6. Qualité
- **articles_with_issues** : COUNT(analysis_results WHERE changes_count > 0)
- **articles_without_issues** : COUNT(analysis_results WHERE changes_count = 0)
- **issues_by_severity** : SELECT severity, COUNT(*) FROM issues GROUP BY severity
- **errors_by_type** : SELECT issue_type, COUNT(*) FROM issues WHERE severity='error' GROUP BY issue_type
- **issue_rate** : articles_with_issues / total * 100
- **dead_link_rate** : dead_links_detected / total_links * 100
- **correction_rate** : dead_links_corrected / dead_links_detected * 100

### 7. Pipeline
- **runs** : COUNT(sessions)
- **success** : COUNT(sessions WHERE ended_at IS NOT NULL)
- **failed** : COUNT(sessions WHERE ended_at IS NULL AND started_at < NOW - 1h)
- **running** : COUNT(sessions WHERE ended_at IS NULL AND started_at >= NOW - 1h)
- **articles_processed** : SUM(articles_analyzed) FROM sessions
- **articles_remaining** : COUNT(articles_to_analyze WHERE status='pending')
- **analyses_completed** : COUNT(analysis_jobs WHERE status='completed')
- **publications_completed** : COUNT(analysis_results WHERE status='published')
- **pipeline_duration** : AVG(ended_at - started_at) FROM sessions WHERE ended_at IS NOT NULL
- **average_processing_time** : AVG(completed_at - started_at) FROM analysis_jobs WHERE status='completed'

### 8. Temps/Performance
- **articles_published_today** : COUNT(analysis_results WHERE status='published' AND analysis_date >= TODAY)
- **analyses_today** : COUNT(analysis_jobs WHERE created_at >= TODAY)
- **corrections_today** : SUM(changes_count) FROM analysis_results WHERE analysis_date >= TODAY
- **errors_today** : COUNT(analysis_jobs WHERE status='failed' AND created_at >= TODAY)
- **articles_published_7d** : COUNT(analysis_results WHERE status='published' AND analysis_date >= NOW - 7d)
- **articles_published_30d** : COUNT(analysis_results WHERE status='published' AND analysis_date >= NOW - 30d)

## Données manquantes ou à déduire

### Corrections spécifiques
- **typos_fixed** : Pas de champ direct, déduit de issue_type
- **formatting_fixed** : Pas de champ direct, déduit de issue_type
- **http_links_corrected** : Pas de champ direct, déduit de issue_type + suggested_text

### Erreurs détaillées
- **errors_by_module** : Pas de champ module, déduit de context
- **errors_by_stage** : Pas de champ stage, déduit de job_id

## Index existants (vérifiés)

- idx_analysis_results_status ✅
- idx_analysis_results_analysis_date ✅
- idx_analysis_jobs_status ✅
- idx_issues_severity ✅
- idx_issues_type ✅
- idx_articles_to_analyze_status ✅

## Index suggérés pour nouvelles stats

- idx_analysis_results_changes_count (pour articles_with_issues)
- idx_analysis_jobs_started_at (pour average_duration)
- idx_analysis_jobs_completed_at (pour average_duration)
- idx_articles_to_analyze_added_at (pour average_wait_time)
- idx_issues_severity (déjà existe ✅)
