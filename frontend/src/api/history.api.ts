/**
 * History API - Published history, analyzed history, statistics
 */

import apiClient from './client'
import type { PublishedHistory, AnalyzedHistory, Statistics } from './types'

export const historyApi = {
  /**
   * Get published history
   */
  async getPublishedHistory(page?: number, page_size?: number): Promise<PublishedHistory> {
    const params: any = {}
    if (page) params.page = page
    if (page_size) params.page_size = page_size
    
    const response = await apiClient.get<PublishedHistory>('/api/history/published', { params })
    return response.data
  },

  /**
   * Get analyzed history
   */
  async getAnalyzedHistory(filters?: {
    limit?: number;
    offset?: number;
    status_filter?: string;
    mode_filter?: string;
    search_query?: string;
    date_filter?: string;
  }): Promise<AnalyzedHistory> {
    const params: any = {}
    if (filters) {
      if (filters.limit) params.limit = filters.limit
      if (filters.offset) params.offset = filters.offset
      if (filters.status_filter) params.status_filter = filters.status_filter
      if (filters.mode_filter) params.mode_filter = filters.mode_filter
      if (filters.search_query) params.search_query = filters.search_query
      if (filters.date_filter) params.date_filter = filters.date_filter
    }
    
    const response = await apiClient.get<AnalyzedHistory>('/api/history/analyzed', { params })
    return response.data
  },

  /**
   * Get article-specific history
   */
  async getArticleHistory(title: string): Promise<{ success: boolean; history: any }> {
    const response = await apiClient.get(`/api/history/${encodeURIComponent(title)}`)
    return response.data
  },

  /**
   * Get statistics (now using centralized StatsService V2)
   */
  async getStatistics(): Promise<Statistics> {
    const response = await apiClient.get<Statistics>('/api/stats/v2/legacy')
    return response.data
  }
}
