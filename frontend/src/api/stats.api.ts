/**
 * Stats API - Centralized statistics V2
 */

import apiClient from './client'

// Types for individual stats families
export interface ArticleStats {
  total: number
  analyzed: number
  published: number
  pending: number
  rejected: number
  ignored: number
  error: number
  skipped: number
}

export interface AnalysisStats {
  total: number
  pending: number
  running: number
  completed: number
  successful: number
  failed: number
  cancelled: number
  success_rate: number
  failure_rate: number
  average_duration: number
  dead_links_detected: number
  dead_links_corrected: number
  total_links: number
  changes_count: number
  character_count: number
}

export interface PublicationStats {
  total: number
  successful: number
  failed: number
  pending: number
  cancelled: number
  publication_rate: number
  success_rate: number
  recent_24h: number
  recent_7d: number
  recent_30d: number
}

export interface CorrectionStats {
  total_corrections: number
  typos_fixed: number
  formatting_fixed: number
  dead_links_detected: number
  dead_links_corrected: number
  http_links_corrected: number
}

export interface QueueStats {
  total: number
  pending: number
  processing: number
  completed: number
  failed: number
  cancelled: number
  success_rate: number
  average_wait_time: number
}

export interface QualityStats {
  articles_with_issues: number
  articles_without_issues: number
  issues_by_severity: Record<string, number>
  errors_by_type: Record<string, number>
  issue_rate: number
  dead_link_rate: number
  correction_rate: number
}

export interface PipelineStats {
  runs: number
  success: number
  failed: number
  running: number
  articles_processed: number
  articles_remaining: number
  analyses_completed: number
  publications_completed: number
  pipeline_duration: number
  average_processing_time: number
}

export interface TemporalStats {
  articles_published_today: number
  analyses_today: number
  corrections_today: number
  errors_today: number
  articles_published_7d: number
  analyses_7d: number
  corrections_7d: number
  errors_7d: number
  articles_published_30d: number
  analyses_30d: number
  corrections_30d: number
  errors_30d: number
}

export interface ErrorStats {
  total: number
  today: number
  by_type: Record<string, number>
  by_module: Record<string, number>
  by_stage: Record<string, number>
}

export interface DatabaseStats {
  articles_total: number
  issues_total: number
  actions_total: number
  articles_with_changes: number
}

export const statsApi = {
  /**
   * Get article statistics
   */
  async getArticleStats(): Promise<ArticleStats> {
    const response = await apiClient.get<ArticleStats>('/api/stats/v2/articles')
    return response.data
  },

  /**
   * Get analysis statistics
   */
  async getAnalysisStats(): Promise<AnalysisStats> {
    const response = await apiClient.get<AnalysisStats>('/api/stats/v2/analysis')
    return response.data
  },

  /**
   * Get publication statistics
   */
  async getPublicationStats(): Promise<PublicationStats> {
    const response = await apiClient.get<PublicationStats>('/api/stats/v2/publication')
    return response.data
  },

  /**
   * Get correction statistics
   */
  async getCorrectionStats(): Promise<CorrectionStats> {
    const response = await apiClient.get<CorrectionStats>('/api/stats/v2/corrections')
    return response.data
  },

  /**
   * Get queue statistics
   */
  async getQueueStats(): Promise<QueueStats> {
    const response = await apiClient.get<QueueStats>('/api/stats/v2/queue')
    return response.data
  },

  /**
   * Get quality statistics
   */
  async getQualityStats(): Promise<QualityStats> {
    const response = await apiClient.get<QualityStats>('/api/stats/v2/quality')
    return response.data
  },

  /**
   * Get pipeline statistics
   */
  async getPipelineStats(): Promise<PipelineStats> {
    const response = await apiClient.get<PipelineStats>('/api/stats/v2/pipeline')
    return response.data
  },

  /**
   * Get temporal statistics
   */
  async getTemporalStats(): Promise<TemporalStats> {
    const response = await apiClient.get<TemporalStats>('/api/stats/v2/temporal')
    return response.data
  },

  /**
   * Get error statistics
   */
  async getErrorStats(): Promise<ErrorStats> {
    const response = await apiClient.get<ErrorStats>('/api/stats/v2/errors')
    return response.data
  },

  /**
   * Get database statistics
   */
  async getDatabaseStats(): Promise<DatabaseStats> {
    const response = await apiClient.get<DatabaseStats>('/api/stats/v2/database')
    return response.data
  }
}
