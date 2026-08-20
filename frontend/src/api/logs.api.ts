/**
 * Logs API - Retrieve logs, recent logs, statistics
 */

import apiClient from './client'
import type { LogsResponse, RecentLogsResponse, LogStatsResponse } from './types'

export const logsApi = {
  /**
   * Get all logs with pagination
   */
  async getLogs(limit?: number, level?: string, offset?: number): Promise<LogsResponse> {
    const params: any = {}
    if (limit) params.limit = limit
    if (level) params.level = level
    if (offset !== undefined) params.offset = offset
    
    const response = await apiClient.get<LogsResponse>('/api/logs/', { params })
    return response.data
  },

  /**
   * Get recent logs
   */
  async getRecentLogs(count: number = 50): Promise<RecentLogsResponse> {
    const response = await apiClient.get<RecentLogsResponse>('/api/logs/recent', {
      params: { count }
    })
    return response.data
  },

  /**
   * Get log statistics
   */
  async getLogStats(): Promise<LogStatsResponse> {
    const response = await apiClient.get<LogStatsResponse>('/api/logs/stats')
    return response.data
  }
}
