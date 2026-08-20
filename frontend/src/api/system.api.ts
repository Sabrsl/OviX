/**
 * System API - Health, Status, Kill Switch, Scheduler
 */

import apiClient, { quickApiClient } from './client'
import type { HealthResponse, SystemStatus } from './types'

export const systemApi = {
  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<HealthResponse> {
    const response = await quickApiClient.get<HealthResponse>('/api/health')
    return response.data
  },

  /**
   * Get complete system status
   */
  async getSystemStatus(): Promise<SystemStatus> {
    const response = await quickApiClient.get<SystemStatus>('/api/system/status')
    return response.data
  },

  /**
   * Get Kill Switch status
   */
  async getKillSwitchStatus(): Promise<{ enabled: boolean; reason?: string; requested_by?: string }> {
    const response = await apiClient.get('/api/system/kill-switch')
    return response.data
  },

  /**
   * Activate Kill Switch
   */
  async activateKillSwitch(reason: string, _requestedBy: string): Promise<{ success: boolean }> {
    const response = await apiClient.post('/api/system/kill-switch/activate', {
      enabled: true,
      reason,
      requested_by: _requestedBy
    })
    return response.data
  },

  /**
   * Deactivate Kill Switch
   */
  async deactivateKillSwitch(reason: string, _requestedBy: string): Promise<{ success: boolean }> {
    const response = await apiClient.post('/api/system/kill-switch/deactivate', {
      enabled: false,
      reason,
      requested_by: _requestedBy
    })
    return response.data
  },

  /**
   * Get Scheduler status
   */
  async getSchedulerStatus(): Promise<{ 
    is_active: boolean; 
    current_task?: string; 
    queue_size?: number; 
    next_execution?: string; 
    last_execution?: string; 
    daily_processed?: number; 
    daily_limit?: number 
  }> {
    const response = await apiClient.get('/api/system/scheduler')
    return response.data
  },

  /**
   * Start Scheduler
   */
  async startScheduler(): Promise<{ success: boolean }> {
    const response = await apiClient.post('/api/system/scheduler/start')
    return response.data
  },

  /**
   * Pause Scheduler
   */
  async pauseScheduler(): Promise<{ success: boolean }> {
    const response = await apiClient.post('/api/system/scheduler/pause')
    return response.data
  },

  /**
   * Resume Scheduler
   */
  async resumeScheduler(): Promise<{ success: boolean }> {
    const response = await apiClient.post('/api/system/scheduler/resume')
    return response.data
  },

  /**
   * Stop Scheduler
   */
  async stopScheduler(): Promise<{ success: boolean }> {
    const response = await apiClient.post('/api/system/scheduler/stop')
    return response.data
  },

  /**
   * Run Scheduler manually
   */
  async runManualScheduler(options?: { include_analyzed?: boolean; lia_mode?: boolean }): Promise<{ success: boolean; message: string }> {
    const requestBody = {
      include_analyzed: options?.include_analyzed || false,
      lia_mode: options?.lia_mode || false
    }
    const response = await apiClient.post('/api/system/scheduler/run-manual', requestBody)
    return response.data
  },

  /**
   * Get Automation status
   */
  async getAutomationStatus(): Promise<{ 
    success: boolean; 
    status: string; 
    session_id?: string; 
    current_step?: string; 
    articles_processed?: number; 
    articles_published?: number; 
    articles_error?: number; 
    category_name?: string; 
    started_at?: string;
    message?: string;
    article_states?: Array<{
      title: string;
      status: string;
      progress?: number;
      current_step?: string;
      started_at?: string;
      elapsed_time_seconds?: number;
    }>;
  }> {
    const response = await apiClient.get('/api/system/automation')
    return response.data
  },

  /**
   * Pause Automation
   */
  async pauseAutomation(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post('/api/system/automation/pause')
    return response.data
  },

  /**
   * Resume Automation
   */
  async resumeAutomation(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post('/api/system/automation/resume')
    return response.data
  },

  /**
   * Stop Automation
   */
  async stopAutomation(): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post('/api/system/automation/stop')
    return response.data
  }
}
