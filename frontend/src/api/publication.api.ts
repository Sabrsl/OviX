/**
 * Publication API - Validate, publish, status
 */

import apiClient from './client'
import type { PublicationRequest, PublicationResponse, PublicationStatus } from './types'

export const publicationApi = {
  /**
   * Validate a publication (dry-run)
   */
  async validatePublication(request: PublicationRequest): Promise<PublicationResponse> {
    const response = await apiClient.post<PublicationResponse>('/api/publication/validate', request)
    return response.data
  },

  /**
   * Publish to Wikipedia
   */
  async publish(request: PublicationRequest): Promise<PublicationResponse> {
    const response = await apiClient.post<PublicationResponse>('/api/publication/publish', request)
    return response.data
  },

  /**
   * Get publication status
   */
  async getPublicationStatus(publicationId: string): Promise<PublicationStatus> {
    const response = await apiClient.get<PublicationStatus>(`/api/publication/${publicationId}`)
    return response.data
  },

  /**
   * Stream publication status updates using Server-Sent Events (SSE)
   */
  streamPublicationStatus(publicationId: string, onMessage: (data: any) => void, onError?: (error: any) => void): () => void {
    const eventSource = new EventSource(`/api/publication/${publicationId}/stream`)

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch (err) {
        console.error('Failed to parse SSE message:', err)
      }
    }

    eventSource.onerror = (error) => {
      console.error('SSE error:', error)
      if (onError) onError(error)
      eventSource.close()
    }

    // Return cleanup function
    return () => {
      eventSource.close()
    }
  },

  /**
   * Get all pending publications
   */
  async getPendingPublications(): Promise<{ success: boolean; publications: PublicationStatus[] }> {
    const response = await apiClient.get('/api/publication/pending')
    return response.data
  }
}
