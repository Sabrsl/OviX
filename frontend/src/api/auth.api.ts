/**
 * Authentication API - Wikipedia login, status, logout
 */

import apiClient, { quickApiClient } from './client'
import type { WikipediaLoginRequest, WikipediaLoginResponse, AuthStatus } from './types'

export const authApi = {
  /**
   * Login to Wikipedia
   */
  async login(credentials: WikipediaLoginRequest): Promise<WikipediaLoginResponse> {
    const response = await apiClient.post<WikipediaLoginResponse>('/api/auth/login', credentials)
    return response.data
  },

  /**
   * Logout from Wikipedia
   */
  async logout(): Promise<{ success: boolean }> {
    const response = await apiClient.post('/api/auth/logout')
    return response.data
  },

  /**
   * Get authentication status
   */
  async getStatus(): Promise<AuthStatus> {
    const response = await quickApiClient.get<AuthStatus>('/api/auth/status')
    return response.data
  },

  /**
   * Get account information
   */
  async getAccount(): Promise<{ success: boolean; account?: any }> {
    const response = await apiClient.get('/api/auth/account')
    return response.data
  }
}
