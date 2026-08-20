/**
 * Settings API - Get and update application settings
 */

import apiClient from './client'
import type { SettingsResponse, AppSettings } from './types'

export const settingsApi = {
  /**
   * Get current settings
   */
  async getSettings(): Promise<SettingsResponse> {
    const response = await apiClient.get<SettingsResponse>('/api/settings/')
    return response.data
  },

  /**
   * Update settings
   */
  async updateSettings(settings: Partial<AppSettings>): Promise<SettingsResponse> {
    const response = await apiClient.put<SettingsResponse>('/api/settings/', settings)
    return response.data
  }
}
