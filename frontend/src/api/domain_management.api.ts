/**
 * Domain Management API client.
 * 
 * Provides functions for managing domain_to_site_name mappings
 * in case_normalization_data.yaml.
 */

const API_BASE = '/api/domain-management'

export interface DomainEntry {
  domain: string
  site_name: string
  source: string | null
  added_at: string | null
}

export interface DomainListResponse {
  success: boolean
  domains: DomainEntry[]
  total: number
  statistics: {
    total: number
    valid: number
    conflicts: number
  }
}

export interface AddDomainRequest {
  domain: string
  site_name: string
  source?: string
}

export interface UpdateDomainRequest {
  domain: string
  new_domain?: string
  new_site_name?: string
}

export interface DomainValidationResponse {
  valid: boolean
  normalized_domain: string | null
  errors: string[]
  warnings: string[]
}

/**
 * List all domain mappings with optional search filter.
 */
export async function listDomains(search?: string): Promise<DomainListResponse> {
  const params = new URLSearchParams()
  if (search) params.append('search', search)
  
  const response = await fetch(`${API_BASE}/?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`Failed to list domains: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Validate a domain entry before adding/updating.
 */
export async function validateDomain(domain: string, siteName: string): Promise<DomainValidationResponse> {
  const response = await fetch(`${API_BASE}/validate?domain=${encodeURIComponent(domain)}&site_name=${encodeURIComponent(siteName)}`)
  if (!response.ok) {
    throw new Error(`Failed to validate domain: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Add a new domain mapping.
 */
export async function addDomain(request: AddDomainRequest): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to add domain')
  }
  return response.json()
}

/**
 * Update an existing domain mapping.
 */
export async function updateDomain(domain: string, request: UpdateDomainRequest): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/${encodeURIComponent(domain)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to update domain')
  }
  return response.json()
}

/**
 * Delete a domain mapping.
 */
export async function deleteDomain(domain: string): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/${encodeURIComponent(domain)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to delete domain')
  }
  return response.json()
}
