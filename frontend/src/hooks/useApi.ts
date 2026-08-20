/**
 * Custom hook for API calls with loading and error states
 */

import { useState, useEffect, useRef } from 'react'

interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useApi<T>(
  apiCall: () => Promise<T>,
  immediate = true
): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const isInitialRef = useRef(true)

  const fetchData = async () => {
    if (isInitialRef.current) {
      setLoading(true)
    }
    setError(null)
    try {
      const result = await apiCall()
      console.log('useApi - API call successful:', result)
      setData(result)
    } catch (err: any) {
      console.error('useApi - API call failed:', err)
      setError(err.message || err.userMessage || 'Une erreur est survenue')
    } finally {
      if (isInitialRef.current) {
        setLoading(false)
        isInitialRef.current = false
      }
    }
  }

  useEffect(() => {
    if (immediate) {
      fetchData()
    }
  }, [immediate])

  return { data, loading, error, refetch: fetchData }
}
