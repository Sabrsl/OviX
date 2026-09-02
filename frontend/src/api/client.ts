/**
 * OVIX API Client - Configuration
 * Centralized HTTP client for API communication
 */

import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const API_TIMEOUT = parseInt(import.meta.env.VITE_API_TIMEOUT || '300000')
const API_QUICK_TIMEOUT = parseInt(import.meta.env.VITE_API_QUICK_TIMEOUT || '10000')

// Use relative URLs in development to leverage Vite proxy
const isDev = import.meta.env.DEV
const baseURL = isDev ? '' : API_BASE_URL

// Main API client with longer timeout for operations
export const apiClient = axios.create({
  baseURL: baseURL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Quick API client with short timeout for health checks and status
export const quickApiClient = axios.create({
  baseURL: baseURL,
  timeout: API_QUICK_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // Transform errors into user-friendly messages
    const message = error.response?.data?.detail || error.message || 'Une erreur est survenue'

    // Centralized 401 detection - dispatch event for auth status refresh
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }

    // Kill switch error detection - dispatch event for UI notification
    if (message && (message.includes('kill switch') || message.includes('STOP command') || message.includes('système de sécurité'))) {
      window.dispatchEvent(new CustomEvent('kill-switch:error', {
        detail: { message: 'Publication bloquée par le système de sécurité (Kill Switch ou STOP sur page de discussion)' }
      }))
    }

    return Promise.reject({
      ...error,
      message,
      userMessage: translateError(message)
    })
  }
)

function translateError(error: string): string {
  // Translate technical errors to user-friendly messages
  const errorMap: Record<string, string> = {
    'Connection refused': 'Impossible de se connecter au serveur OVIX',
    'Network Error': 'Erreur de connexion réseau',
    'timeout': 'Délai d\'attente dépassé',
    '401': 'Authentification requise',
    '403': 'Accès refusé',
    '404': 'Ressource non trouvée',
    '429': 'Trop de requêtes, veuillez réessayer plus tard',
    '500': 'Erreur serveur interne',
    '503': 'Service temporairement indisponible',
    'Wikipedia site not initialized': 'La connexion Wikipédia n\'est pas initialisée',
  }

  for (const [key, value] of Object.entries(errorMap)) {
    if (error.includes(key)) {
      return value
    }
  }

  return error
}

export default apiClient
