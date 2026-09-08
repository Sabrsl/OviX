/**
 * Domain Enrichment API - Enrich domain_to_site_name from Wikidata
 */

import apiClient from './client'

export interface CategoryConfig {
  wiki: string
  category: string
  priority: number
}

export interface StartEnrichmentRequest {
  categories: CategoryConfig[]
  dry_run: boolean
  max_pages?: number
  keep_www?: boolean
}

export interface EnrichmentStatus {
  state: string
  current_category: string | null
  pages_analyzed: number
  total_pages: number
  skipped: number
  p856_found: number
  new_domains: number
  already_present: number
  conflicts: number
  review_required: number
  errors: number
  started_at: string | null
  completed_at: string | null
  recent_activity: string[]
}

export interface PreviewEntry {
  domain: string
  site_name: string
  original_url: string
  page_title: string
  qid: string
}

export interface PreviewResponse {
  new_entries: PreviewEntry[]
  summary: {
    total: number
    already_present: number
    conflicts: number
    review_required: number
    errors: number
  }
}

export interface WriteYamlRequest {
  entries: PreviewEntry[]
}

export const domainEnrichmentApi = {
  /**
   * Get current enrichment status and progress
   */
  async getStatus(): Promise<EnrichmentStatus> {
    const response = await apiClient.get<EnrichmentStatus>('/api/domain-enrichment/status')
    return response.data
  },

  /**
   * Start the enrichment process
   */
  async startEnrichment(request: StartEnrichmentRequest): Promise<{ success: boolean; message: string; dry_run: boolean; categories_count: number }> {
    const response = await apiClient.post('/api/domain-enrichment/start', request)
    return response.data
  },

  /**
   * Pause the enrichment process
   */
  async pauseEnrichment(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post('/api/domain-enrichment/pause')
    return response.data
  },

  /**
   * Resume a paused enrichment process
   */
  async resumeEnrichment(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post('/api/domain-enrichment/resume')
    return response.data
  },

  /**
   * Cancel the enrichment process
   */
  async cancelEnrichment(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post('/api/domain-enrichment/cancel')
    return response.data
  },

  /**
   * Get a preview of changes that would be made
   */
  async getPreview(): Promise<PreviewResponse> {
    const response = await apiClient.get<PreviewResponse>('/api/domain-enrichment/preview')
    return response.data
  },

  /**
   * Write approved entries to case_normalization_data.yaml
   */
  async writeToYaml(request: WriteYamlRequest): Promise<{ success: boolean; message: string; entries_count: number }> {
    const response = await apiClient.post('/api/domain-enrichment/write', request)
    return response.data
  },

  /**
   * Reset the enrichment service to initial state
   */
  async resetEnrichment(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post('/api/domain-enrichment/reset')
    return response.data
  },
}