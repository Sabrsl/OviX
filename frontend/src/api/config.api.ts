/**
 * Configuration API client
 * 
 * Provides methods to interact with the configuration endpoints
 * for managing OVIX settings from the UI.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface ConfigResponse {
  success: boolean
  config: Record<string, any>
  source: string
}

export interface ConfigUpdateRequest {
  section: string
  key: string
  value: any
}

export interface ConfigSectionUpdateRequest {
  section: string
  data: Record<string, any>
}

export interface ConfigValidationResponse {
  success: boolean
  valid: boolean
  errors: string[]
  warnings: string[]
}

class ConfigAPI {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  /**
   * Get the complete configuration
   */
  async getConfig(): Promise<ConfigResponse> {
    return this.request<ConfigResponse>('/api/config/')
  }

  /**
   * Get a specific configuration section
   */
  async getConfigSection(section: string): Promise<ConfigResponse> {
    return this.request<ConfigResponse>(`/api/config/${section}`)
  }

  /**
   * Update a single configuration value
   */
  async updateConfigValue(request: ConfigUpdateRequest): Promise<ConfigResponse> {
    return this.request<ConfigResponse>('/api/config/value', {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  /**
   * Update an entire configuration section
   */
  async updateConfigSection(request: ConfigSectionUpdateRequest): Promise<ConfigResponse> {
    return this.request<ConfigResponse>('/api/config/section', {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  /**
   * Validate configuration data
   */
  async validateConfig(configData?: Record<string, any>): Promise<ConfigValidationResponse> {
    return this.request<ConfigValidationResponse>('/api/config/validate', {
      method: 'POST',
      body: configData ? JSON.stringify(configData) : undefined,
    })
  }

  /**
   * Reset configuration to default values
   */
  async resetConfig(): Promise<ConfigResponse> {
    return this.request<ConfigResponse>('/api/config/reset', {
      method: 'POST',
    })
  }
}

export const configApi = new ConfigAPI()
