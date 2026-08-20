/**
 * Analysis API - Start, monitor, cancel, results
 */

import apiClient from './client'
import type { AnalysisRequest, AnalysisJob, AnalysisResult } from './types'

export const analysisApi = {
  /**
   * Start a new analysis
   */
  async startAnalysis(request: AnalysisRequest): Promise<{ success: boolean; job_id: string }> {
    const response = await apiClient.post('/api/analysis/start', request)
    return response.data
  },

  /**
   * Start batch analysis for multiple articles
   */
  async startBatchAnalysis(request: {
    article_titles: string[];
    mode?: string;
    ai_provider?: string;
    ai_character_limit?: number;
    gemini_api_key?: string;
    gemini_project_id?: string;
  }): Promise<{ success: boolean; job_id: string }> {
    const response = await apiClient.post('/api/analysis/batch', request)
    return response.data
  },

  /**
   * Get analysis job status
   */
  async getAnalysisStatus(jobId: string): Promise<AnalysisJob> {
    const response = await apiClient.get<AnalysisJob>(`/api/analysis/${jobId}`)
    return response.data
  },

  /**
   * Cancel an analysis
   */
  async cancelAnalysis(jobId: string): Promise<{ success: boolean }> {
    const response = await apiClient.post(`/api/analysis/${jobId}/cancel`)
    return response.data
  },

  /**
   * Pause an analysis
   */
  async pauseAnalysis(jobId: string): Promise<{ success: boolean }> {
    const response = await apiClient.post(`/api/analysis/${jobId}/pause`)
    return response.data
  },

  /**
   * Resume a paused analysis
   */
  async resumeAnalysis(jobId: string): Promise<{ success: boolean }> {
    const response = await apiClient.post(`/api/analysis/${jobId}/resume`)
    return response.data
  },

  /**
   * Get analysis results
   */
  async getAnalysisResults(jobId: string): Promise<AnalysisResult> {
    const response = await apiClient.get<AnalysisResult>(`/api/analysis/${jobId}/results`)
    return response.data
  },

  /**
   * Get list of all analyses
   */
  async getAllAnalyses(): Promise<{ success: boolean; analyses: AnalysisJob[] }> {
    const response = await apiClient.get('/api/analysis/')
    return response.data
  }
}
