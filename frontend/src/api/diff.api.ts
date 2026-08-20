/**
 * Diff API - Generate, retrieve, validate diffs
 */

import apiClient from './client'
import type { DiffRequest, DiffResponse, DiffValidationRequest, DiffValidationResponse } from './types'

export const diffApi = {
  /**
   * Generate a diff
   */
  async generateDiff(request: DiffRequest): Promise<DiffResponse> {
    const response = await apiClient.post<DiffResponse>('/api/diff/generate', request)
    return response.data
  },

  /**
   * Get diff by ID
   */
  async getDiff(diffId: string): Promise<DiffResponse> {
    const response = await apiClient.get<DiffResponse>(`/api/diff/${diffId}`)
    return response.data
  },

  /**
   * Validate a diff before publication
   */
  async validateDiff(request: DiffValidationRequest): Promise<DiffValidationResponse> {
    const response = await apiClient.post<DiffValidationResponse>('/api/diff/validate', request)
    return response.data
  }
}
