/**
 * Articles API - Category search, manual search, article retrieval, status tracking
 */

import apiClient from './client'
import type { Article, CategorySearchRequest, ArticleSearchRequest, ArticleContent, ArticleStatus, ArticleHistoryItem, ArticleAnalysisRequest } from './types'

export const articlesApi = {
  /**
   * Search articles by category
   */
  async searchByCategory(request: CategorySearchRequest): Promise<{ success: boolean; articles: Article[] }> {
    const response = await apiClient.post('/api/articles/category', request)
    return response.data
  },

  /**
   * Search articles manually by titles
   */
  async searchManual(request: ArticleSearchRequest): Promise<{ success: boolean; articles: Article[] }> {
    const response = await apiClient.post('/api/articles/manual', request)
    return response.data
  },

  /**
   * Search articles from PetScan
   */
  async searchPetScan(request: { psid: string; limit?: number; exclude_published?: boolean; include_analyzed?: boolean }): Promise<{ success: boolean; articles: Article[] }> {
    const response = await apiClient.post('/api/articles/petscan', request)
    return response.data
  },

  /**
   * Search articles from file
   */
  async searchFile(request: { file_path: string; limit?: number; include_analyzed?: boolean }): Promise<{ success: boolean; articles: Article[] }> {
    const response = await apiClient.post('/api/articles/file', request)
    return response.data
  },

  /**
   * Search articles from user contributions
   */
  async searchUserContribs(request: { username: string; limit?: number; exclude_published?: boolean; include_analyzed?: boolean }): Promise<{ success: boolean; articles: Article[] }> {
    const response = await apiClient.post('/api/articles/user-contribs', request)
    return response.data
  },

  /**
   * Get predefined categories for a language
   */
  async getPredefinedCategories(lang: string = 'fr'): Promise<{ success: boolean; lang: string; categories: string[] }> {
    const response = await apiClient.get('/api/articles/categories/predefined', { params: { lang } })
    return response.data
  },

  /**
   * Get article content
   */
  async getArticle(title: string): Promise<ArticleContent> {
    const response = await apiClient.get<ArticleContent>(`/api/articles/${encodeURIComponent(title)}`)
    return response.data
  },

  /**
   * Get article content (alias for getArticle)
   */
  async getArticleContent(title: string): Promise<ArticleContent> {
    return this.getArticle(title)
  },

  /**
   * Check if article exists
   */
  async articleExists(title: string): Promise<{ success: boolean; exists: boolean }> {
    const response = await apiClient.get(`/api/articles/${encodeURIComponent(title)}/exists`)
    return response.data
  },

  /**
   * Get article status (analysis status, publication status, processing state)
   */
  async getArticleStatus(title: string): Promise<ArticleStatus> {
    const response = await apiClient.get<ArticleStatus>(`/api/articles/${encodeURIComponent(title)}/status`)
    return response.data
  },

  /**
   * Get article history (list of analyzed articles)
   */
  async getArticleHistory(limit: number = 50, offset: number = 0): Promise<ArticleHistoryItem[]> {
    const response = await apiClient.get<ArticleHistoryItem[]>('/api/articles/history', { params: { limit, offset } })
    return response.data
  },

  /**
   * Trigger analysis of a specific article
   */
  async analyzeArticle(title: string, mode: string = 'regex'): Promise<{ success: boolean; message: string; title: string; mode: string; status: string; job_id?: string }> {
    const response = await apiClient.post(`/api/articles/${encodeURIComponent(title)}/analyze`, { mode })
    return response.data
  },

  /**
   * Ignore an article
   */
  async ignoreArticle(title: string) {
    const response = await apiClient.post(`/api/articles/${encodeURIComponent(title)}/ignore`)
    return response.data
  },

  /**
   * Toggle human_verified status for an article
   */
  async toggleHumanVerified(title: string): Promise<{ success: boolean; article_title: string; human_verified: boolean }> {
    const response = await apiClient.post(`/api/articles/${encodeURIComponent(title)}/toggle-verified`)
    return response.data
  },

  /**
   * Get analysis result for an article from AnalyzedTracker
   */
  async getArticleAnalysisResult(title: string) {
    const response = await apiClient.get(`/api/articles/${encodeURIComponent(title)}/analysis-result`)
    return response.data
  },

  /**
   * Add multiple articles to the analysis queue
   */
  async addArticlesToAnalyze(request: {
    articles: Array<{
      title: string
      page_id?: number
      revision_id?: number
      source: string
      source_details: string
      priority: 'low' | 'medium' | 'high'
    }>
  }): Promise<{ success: boolean; added_count: number; message: string }> {
    const response = await apiClient.post('/api/articles/to-analyze/batch', request)
    return response.data
  },

  /**
   * Get articles from the analysis queue
   */
  async getArticlesToAnalyze(): Promise<{ success: boolean; articles: any[]; count: number }> {
    const response = await apiClient.get('/api/articles/to-analyze')
    return response.data
  },

  /**
   * Get total count of articles in the analysis queue
   */
  async getArticlesToAnalyzeCount(status?: string): Promise<{ total: number }> {
    const response = await apiClient.get('/api/articles/to-analyze/count', { params: { status } })
    return response.data
  },

  /**
   * Get total count of analysis results
   */
  async getAnalysisResultsCount(status?: string): Promise<{ total: number }> {
    const response = await apiClient.get('/api/articles/results/count', { params: { status } })
    return response.data
  },

  /**
   * Get published articles history
   */
  async getPublishedHistory(): Promise<{ success: boolean; items: any[] }> {
    const response = await apiClient.get('/api/history/published')
    return response.data
  },

  /**
   * Get articles pending in scheduler queue (status='pending' in analysis_results)
   */
  async getPendingSchedulerQueue(): Promise<{ success: boolean; articles: any[] }> {
    const response = await apiClient.get('/api/articles/results?status=pending&limit=1000')
    return response.data
  },

  /**
   * Sync manually published articles
   */
  async syncPublishedArticles(): Promise<{ success: boolean; synced_count: number; message: string }> {
    const response = await apiClient.post('/api/articles/sync-published')
    return response.data
  }
}
