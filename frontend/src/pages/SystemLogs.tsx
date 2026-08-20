import { useState, useEffect, useRef, useCallback } from 'react'
import { logsApi } from '../api/logs.api'
import { LogEntry } from '../api/types'

const LEVELS = ['ALL', 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'] as const
type LevelFilter = typeof LEVELS[number]

const REFRESH_INTERVAL_MS = 5000
const LOGS_PER_PAGE = 100

export default function SystemLogs() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [levelFilter, setLevelFilter] = useState<LevelFilter>('ALL')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalLogs, setTotalLogs] = useState(0)

  const isMountedRef = useRef(true)
  const isFetchingRef = useRef(false)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const fetchLogs = useCallback(async (opts?: { silent?: boolean; page?: number; isInitial?: boolean }) => {
    if (isFetchingRef.current) return
    isFetchingRef.current = true

    const page = opts?.page || 1
    const offset = (page - 1) * LOGS_PER_PAGE
    const levelFilterParam = levelFilter === 'ALL' ? undefined : levelFilter

    if (opts?.silent) {
      setRefreshing(true)
    } else if (opts?.isInitial) {
      setLoading(true)
    }
    setError(null)

    try {
      const response = await logsApi.getLogs(LOGS_PER_PAGE, levelFilterParam, offset)
      if (!isMountedRef.current) return

      const newLogs = Array.isArray(response?.logs) ? response.logs : []
      setLogs(newLogs)
      setTotalLogs(response?.total || 0)
      setCurrentPage(page)
      setLastUpdated(new Date())
    } catch (err: any) {
      if (!isMountedRef.current) return
      console.error('Error fetching logs:', err)
      setError(err?.userMessage || err?.message || 'Erreur lors de la récupération des logs')
    } finally {
      if (isMountedRef.current) {
        if (opts?.isInitial) {
          setLoading(false)
        }
        setRefreshing(false)
      }
      isFetchingRef.current = false
    }
  }, [levelFilter])

  // Initial load + reload when the level filter changes
  useEffect(() => {
    fetchLogs({ page: 1, isInitial: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [levelFilter])

  // Auto-refresh polling: stays on the current page, silent (no full loader)
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      fetchLogs({ silent: true, page: currentPage })
    }, REFRESH_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [autoRefresh, fetchLogs, currentPage])

  const getLevelColor = (level: string) => {
    switch ((level || '').toUpperCase()) {
      case 'ERROR':
      case 'CRITICAL':
        return '#ef4444'
      case 'WARNING':
        return '#f59e0b'
      case 'INFO':
        return '#3b82f6'
      case 'DEBUG':
        return '#666666'
      default:
        return '#a0a0a0'
    }
  }

  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return '—'
    try {
      const date = new Date(timestamp)
      if (isNaN(date.getTime())) {
        const timeMatch = timestamp.match(/(\d{2}:\d{2}:\d{2})/)
        if (timeMatch) return timeMatch[1]
        return timestamp
      }
      return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return timestamp
    }
  }

  const totalPages = Math.max(1, Math.ceil(totalLogs / LOGS_PER_PAGE))

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > totalPages || loading) return
    fetchLogs({ page: newPage })
  }

  const formatLastUpdated = (date: Date | null) => {
    if (!date) return null
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>Journaux Système</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px', marginBottom: 0 }}>
            Voir les journaux système et événements
          </p>
          {lastUpdated && (
            <p style={{ color: '#666666', marginTop: '4px', marginBottom: 0, fontSize: '12px' }}>
              Dernière mise à jour : {formatLastUpdated(lastUpdated)}
              {refreshing && ' · actualisation…'}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary"
            onClick={() => fetchLogs({ page: 1 })}
            disabled={loading || refreshing}
            aria-busy={loading || refreshing}
          >
            {loading || refreshing ? 'Actualisation…' : 'Actualiser'}
          </button>
          <button
            className={`btn ${autoRefresh ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setAutoRefresh((v) => !v)}
            aria-pressed={autoRefresh}
          >
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          </button>
        </div>
      </div>

      {/* Level filter */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {LEVELS.map((lvl) => {
          const active = levelFilter === lvl
          return (
            <button
              key={lvl}
              onClick={() => setLevelFilter(lvl)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
                border: `1px solid ${active ? '#3a3a3a' : '#2a2a2a'}`,
                backgroundColor: active ? '#1f1f1f' : '#161616',
                color: active ? '#f5f5f5' : '#a0a0a0',
                transition: 'all 0.15s ease-in-out',
              }}
            >
              {lvl}
            </button>
          )
        })}
      </div>

      {loading ? (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            padding: '48px',
            backgroundColor: '#161616',
            borderRadius: '8px',
            border: '1px solid #2a2a2a',
          }}
        >
          <div style={{ textAlign: 'center', color: '#666666' }}>Chargement...</div>
        </div>
      ) : error ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px',
            padding: '48px',
            backgroundColor: '#161616',
            borderRadius: '8px',
            border: '1px solid #2a2a2a',
          }}
        >
          <div style={{ textAlign: 'center', color: '#ef4444' }}>{error}</div>
          <button className="btn btn-secondary" onClick={() => fetchLogs({ page: currentPage })}>
            Réessayer
          </button>
        </div>
      ) : (
        <div
          style={{
            backgroundColor: '#0a0a0a',
            border: '1px solid #2a2a2a',
            borderRadius: '8px',
            padding: '24px',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '13px',
            maxHeight: '600px',
            overflowY: 'auto',
          }}
        >
          {logs.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#666666', padding: '48px' }}>
              {levelFilter === 'ALL' ? 'Aucun log disponible' : 'Aucun log pour ce niveau'}
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {logs.map((log, index) => (
                  <div
                    key={`${log.timestamp}-${log.module}-${index}`}
                    style={{
                      display: 'flex',
                      gap: '16px',
                      padding: '8px 0',
                      borderBottom: index < logs.length - 1 ? '1px solid #1a1a1a' : 'none',
                      flexWrap: 'wrap',
                    }}
                  >
                    <span style={{ color: '#666666', minWidth: '80px' }}>{formatTimestamp(log.timestamp)}</span>
                    <span
                      style={{
                        color: getLevelColor(log.level),
                        minWidth: '60px',
                        fontWeight: 500,
                      }}
                    >
                      {log.level}
                    </span>
                    <span style={{ color: '#666666', minWidth: '120px', wordBreak: 'break-word' }}>
                      {log.module}
                    </span>
                    <span style={{ color: '#a0a0a0', flex: 1, minWidth: '200px', wordBreak: 'break-word' }}>
                      {log.message}
                    </span>
                  </div>
                ))}
              </div>

              {totalPages > 1 && (
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    gap: '8px',
                    marginTop: '16px',
                    paddingTop: '16px',
                    borderTop: '1px solid #1a1a1a',
                  }}
                >
                  <button
                    className="btn btn-secondary"
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={currentPage === 1 || loading}
                    style={{ padding: '6px 12px', fontSize: '12px' }}
                  >
                    ←
                  </button>
                  <span style={{ color: '#a0a0a0', fontSize: '12px' }}>
                    Page {currentPage} / {totalPages} ({totalLogs} logs)
                  </span>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={currentPage >= totalPages || loading}
                    style={{ padding: '6px 12px', fontSize: '12px' }}
                  >
                    →
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}