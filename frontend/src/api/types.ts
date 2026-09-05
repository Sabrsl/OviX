/**
 * OVIX API Types
 * TypeScript types corresponding to FastAPI response models
 */

// ================================
// System & Health
// ================================

export interface HealthResponse {
  status: 'healthy' | 'unhealthy'
  services: {
    api: string
    throttler: string
    kill_switch: string
    published_tracker: string
    analyzed_tracker: string
    database: string
    scheduler_state: string
    automation_state: string
    config: string
  }
}

export interface SystemStatus {
  wikipedia: {
    connected: boolean
    username?: string
    language?: string
    family?: string
    site?: string
  }
  scheduler: {
    is_active: boolean
    is_paused: boolean  // NEW: Track pause state
    current_task?: string
    next_execution?: string
    queue_size?: number
    total_articles?: number
    published_articles?: number
    articles_with_changes?: number
  }
  kill_switch: {
    enabled: boolean
    reason?: string
    requested_by?: string
    requested_at?: string
  }
  database_stats?: {
    total_articles: number
    published_articles: number
    articles_with_changes: number
    pending_articles: number
  }
}

// ================================
// Authentication
// ================================

export interface WikipediaLoginRequest {
  username: string
  password: string
  lang?: string
  family?: string
  remember?: boolean
}

export interface WikipediaLoginResponse {
  success: boolean
  authenticated: boolean
  username?: string
  lang?: string
  family?: string
  error?: string
}

export interface AuthStatus {
  authenticated: boolean
  username?: string
  lang?: string
  family?: string
}

// ================================
// Articles
// ================================

export interface Article {
  title: string
  pageid?: number
  exists: boolean
  is_redirect?: boolean
  redirect_target?: string
  last_revision_id?: number
  last_revision_timestamp?: string
  length?: number
}

export interface ArticleInfo {
  title: string
  page_id: number
  revision_id: number
  url: string
  content?: string
  length?: number
  total_links?: number
  dead_links_count?: number
  corrected_links_count?: number
  human_verified?: boolean
}

export interface ArticleStatus {
  title: string
  page_id?: number
  revision_id?: number
  status: 'pending' | 'analyzing' | 'analyzed' | 'published' | 'rejected' | 'ignored' | 'error'
  analysis_date?: string
  changes_count?: number
  summary?: string
  corrected_content?: string
  character_count?: number
  score?: number
  decision?: string
  mode?: string
  // Progress tracking fields
  progress?: number
  current_step?: string
  analyzers_status?: Record<string, string>
  elapsed_time_seconds?: number
}

export interface ArticleHistoryItem {
  title: string
  page_id?: number
  revision_id?: number
  status: string
  analysis_date?: string
  changes_count?: number
  summary?: string
  published_date?: string
  published_revision_id?: number
}

export interface ArticleAnalysisRequest {
  title: string
  mode?: string
}

export interface CategorySearchRequest {
  category: string
  limit?: number
  lang?: string
  recursive?: boolean
  exclude_published?: boolean
  include_analyzed?: boolean
}

export interface ArticleSearchRequest {
  titles: string[]
  lang?: string
  exclude_published?: boolean
  include_analyzed?: boolean
}

export interface ArticleContent {
  title: string
  content: string
  revision_id?: number
  timestamp?: string
}

// ================================
// Analysis
// ================================

export interface AnalysisRequest {
  article_title: string
  mode?: 'regex' | 'full' | 'ia'
  analysis_type?: 'article' | 'category'
  max_checks?: number
  max_candidates?: number
  same_domain_only?: boolean
  require_archive_evidence?: boolean
  min_candidate_confidence?: number
  ai_provider?: 'gemini' | 'ollama'
  ai_character_limit?: number
  gemini_api_key?: string
  gemini_project_id?: string
}

export interface AnalysisJob {
  job_id: string
  article_title: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  created_at: string
  started_at?: string
  completed_at?: string
  error?: string
  progress?: number
  message?: string
  results?: any
}

export interface AnalysisProgress {
  current_step: string
  total_articles?: number
  current_article?: string
  current_article_index?: number
  articles_analyzed?: number
  articles_with_dead_links?: number
  dead_links_found?: number
}

export interface AnalysisResult {
  job_id: string
  article_title: string
  original_content: string
  corrected_content: string
  issues: IssueInfo[]
  dead_links_count: number
  attempted_repairs: number
  successful_repairs: number
  status: 'completed' | 'failed'
  error?: string
  stats?: {
    total_issues?: number
    dead_links_count?: number
    corrected_links_count?: number
    high_severity?: number
    medium_severity?: number
    low_severity?: number
  }
  normalization_changes_count?: number
  normalization_ignored_count?: number
  normalization_reports?: string
}

export interface IssueInfo {
  issue_type: string
  description: string
  severity: string
  position?: number
  original_text?: string
  suggested_text?: string
  context?: string
  // DeadLink compatibility fields
  url?: string
  status?: string
  anchor?: string
  candidates?: ReplacementCandidate[]
}

export interface DeadLink {
  url: string
  anchor: string
  status: 'dead' | 'uncertain' | 'alive'
  detected_at: string
  context?: string
  candidates: ReplacementCandidate[]
}

export interface ReplacementCandidate {
  url: string
  source: string
  confidence: number
  archive_url?: string
  reason?: string
  same_domain: boolean
}

// ================================
// Diff
// ================================

export interface DiffRequest {
  original: string
  corrected: string
  diff_type?: 'html' | 'unified' | 'inline'
}

export interface DiffResponse {
  success: boolean
  diff_id: string
  diff: string
  html_diff?: string
  diff_type: string
  stats: {
    original_length: number
    corrected_length: number
    changes_count: number
    additions: number
    deletions: number
  }
}

export interface DiffValidationRequest {
  article_title: string
  corrected_content: string
  summary: string
  dry_run: boolean
}

export interface DiffValidationResponse {
  success: boolean
  valid: boolean
  warnings?: string[]
  errors?: string[]
  current_revision?: number
  requires_new_analysis?: boolean
}

// ================================
// Publication
// ================================

export interface PublicationRequest {
  article_title: string
  corrected_content: string
  original_content: string
  summary: string
  dry_run: boolean
  edit_comment?: string
}

export interface PublicationResponse {
  success: boolean
  publication_id: string
  status: string
  message: string
}

export interface PublicationStatus {
  publication_id: string
  status: string
  message: string
  started_at?: string
  completed_at?: string
  error?: string
  revision_id?: string
  diff?: string
}

// ================================
// History
// ================================

export interface PublishedHistory {
  items: PublishedItem[]
  total: number
  page?: number
  page_size?: number
}

export interface PublishedItem {
  title: string
  article_title?: string // Legacy field for backward compatibility
  published_at: string
  timestamp?: string // Legacy field for backward compatibility
  category: string
  mode: string
  summary: string
  revision_id?: number
  dry_run?: boolean // Computed from mode === 'dry_run'
  changes_count?: number // Not provided by backend, default to 0
  // Additional fields from database if available
  total_links?: number
  dead_links_count?: number
  corrected_links_count?: number
  character_count?: number
  job_id?: string
  page_id?: number
}

export interface AnalyzedHistory {
  success: boolean
  items: AnalyzedItem[]
  count: number
}

export interface AnalyzedItem {
  title: string
  article_title?: string
  analyzed_at?: string
  analysis_date?: string
  dead_links_count?: number
  corrections_count?: number
  changes_count?: number
  status: string
  job_id?: string
  character_count?: number
  total_links?: number
  corrected_links_count?: number
  human_verified?: boolean
  mode?: string
}

export interface Statistics {
  stats: {
    total_analyses: number
    total_dead_links: number
    total_corrections: number
    total_publications: number
    success_rate: number
    failure_rate: number
    pending_publications: number
    analyzed_total?: number
    analyzed_published?: number
    analyzed_pending?: number
    analyzed_rejected?: number
    analyzed_ignored?: number
    analyzed_error?: number
    publication_rate?: number
    dead_links_detected?: number
    dead_links_corrected?: number
  }
}

// ================================
// Logs
// ================================

export interface LogsResponse {
  success: boolean
  logs: LogEntry[]
  total: number
}

export interface LogEntry {
  timestamp: string
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
  module: string
  message: string
}

export interface RecentLogsResponse {
  success: boolean
  logs: LogEntry[]
  count: number
}

export interface LogStatsResponse {
  success: boolean
  stats: {
    total_logs: number
    debug_count: number
    info_count: number
    warning_count: number
    error_count: number
    critical_count: number
  }
}

// ================================
// Automation
// ================================

export interface AutomationStatus {
  success: boolean
  status: string
  session_id: string
  current_step: string
  articles_processed: number
  articles_published: number
  articles_error: number
  category_name: string
  started_at: string
  article_states: ArticleState[]
}

export interface ArticleState {
  title?: string
  status?: string
  progress?: number
  current_step?: string
  started_at?: string
  elapsed_time_seconds?: number
}

// ================================
// Settings
// ================================

export interface SettingsResponse {
  success: boolean
  settings: AppSettings
}

export interface AppSettings {
  wikipedia: {
    username: string
    lang: string
    family: string
  }
  analysis: {
    max_checks: number
    max_candidates: number
    same_domain_only: boolean
    require_archive_evidence: boolean
    min_candidate_confidence: number
  }
  publication: {
    dry_run: boolean
    confirmation_required: boolean
    max_batch_size: number
  }
  scheduler: {
    daily_limit: number
    working_hours_start: string
    working_hours_end: string
  }
  throttling: {
    min_delay: number
    max_requests_per_minute: number
  }
}

// ================================
// Error Responses
// ================================

export interface ErrorResponse {
  success: false
  error: {
    code: string
    message: string
    details?: any
  }
}
