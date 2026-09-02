import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { CheckCircle, Clock, FileText, RefreshCw, AlertCircle, XCircle } from 'lucide-react'
import { historyApi } from '../api/history.api'

const COLORS = {
  bgPanel: '#161616',
  bgInput: '#0a0a0a',
  bgSubtle: '#1a1a1a',
  bgSubtleHover: '#1f1f1f',
  border: '#2a2a2a',
  borderHover: '#3a3a3a',
  textPrimary: '#f5f5f5',
  textSecondary: '#a0a0a0',
  textMuted: '#666666',
  accent: '#3b82f6',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
} as const

const PAGE_SIZE = 20

const FILTERS = ['all', 'published', 'failed', 'rejected'] as const
type FilterType = (typeof FILTERS)[number]

const FILTER_LABELS: Record<FilterType, string> = {
  all: 'Tous',
  published: 'Publiés',
  failed: 'Échoués',
  rejected: 'Rejetés',
}

interface HistoryItem {
  title: string
  mode?: string
  status?: string
  published_at?: string | number | Date
  category?: string
  revision_id?: string | number
  corrected_links_count?: number
  summary?: string
}

interface HistoryResponse {
  items?: HistoryItem[]
  total?: number
}

export default function PublicationHistory() {
  const [history, setHistory] = useState<HistoryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterType>('all')
  const [page, setPage] = useState(1)

  // Prevents setState on unmounted component + guards against out-of-order responses
  const requestIdRef = useRef(0)
  const isMountedRef = useRef(true)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const fetchHistory = useCallback(
    async (isInitial: boolean) => {
      const requestId = ++requestIdRef.current
      if (isInitial) setLoading(true)
      else setRefreshing(true)
      setError(null)

      try {
        const response = await historyApi.getPublishedHistory(page, PAGE_SIZE)
        // Ignore stale responses from a previous, superseded request
        if (!isMountedRef.current || requestId !== requestIdRef.current) return
        setHistory(response ?? { items: [], total: 0 })
      } catch (err: any) {
        if (!isMountedRef.current || requestId !== requestIdRef.current) return
        setError(
          err?.userMessage ||
            err?.message ||
            "Erreur lors de la récupération de l'historique. Veuillez réessayer."
        )
      } finally {
        if (!isMountedRef.current || requestId !== requestIdRef.current) return
        setLoading(false)
        setRefreshing(false)
      }
    },
    [page]
  )

  useEffect(() => {
    fetchHistory(true)
  }, [fetchHistory])

  const getStatusIcon = (dryRun: boolean, failed: boolean) => {
    if (failed) return <XCircle style={{ width: '15px', height: '15px', color: COLORS.danger }} />
    return dryRun ? (
      <Clock style={{ width: '15px', height: '15px', color: COLORS.warning }} />
    ) : (
      <CheckCircle style={{ width: '15px', height: '15px', color: COLORS.success }} />
    )
  }

  const formatDate = (timestamp: any) => {
    if (!timestamp) return 'N/A'
    try {
      const date = new Date(timestamp)
      if (isNaN(date.getTime())) return 'Date invalide'
      return date.toLocaleString('fr-FR')
    } catch {
      return 'Date invalide'
    }
  }

  const items = history?.items ?? []

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const isDryRun = item.mode === 'dry_run'
      const isFailed = item.status === 'failed'
      const isRejected = item.status === 'rejected'
      switch (filter) {
        case 'published':
          return !isDryRun && !isFailed && !isRejected
        case 'failed':
          return isFailed
        case 'rejected':
          return isRejected
        default:
          return true
      }
    })
  }, [items, filter])

  const stats = useMemo(
    () => ({
      total: history?.total ?? 0,
      published: items.filter((i) => i.mode !== 'dry_run' && i.status !== 'failed' && i.status !== 'rejected').length,
      dryRun: items.filter((i) => i.mode === 'dry_run').length,
      changes: items.reduce((sum, i) => sum + (i.corrected_links_count || 0), 0),
    }),
    [items, history?.total]
  )

  const totalPages = Math.max(1, Math.ceil((history?.total ?? 0) / PAGE_SIZE))
  const canGoPrev = page > 1
  const canGoNext = page * PAGE_SIZE < (history?.total ?? 0)
  const isBusy = loading || refreshing

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.35s ease-out' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '19px', fontWeight: 600, color: COLORS.textPrimary, letterSpacing: '-0.01em', margin: 0 }}>
            Historique des publications
          </h2>
          <p style={{ color: COLORS.textSecondary, marginTop: '3px', fontSize: '12.5px', margin: '3px 0 0' }}>
            Voir l'historique des publications et statistiques
          </p>
        </div>
        <button
          onClick={() => fetchHistory(false)}
          disabled={isBusy}
          aria-busy={refreshing}
          aria-label="Actualiser l'historique"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 13px',
            backgroundColor: COLORS.bgSubtle,
            border: `1px solid ${COLORS.border}`,
            borderRadius: '7px',
            color: COLORS.textSecondary,
            fontSize: '12px',
            fontWeight: 500,
            cursor: isBusy ? 'not-allowed' : 'pointer',
            opacity: isBusy ? 0.6 : 1,
            transition: 'background-color 0.15s, border-color 0.15s, color 0.15s, transform 0.1s',
          }}
          onMouseEnter={(e) => {
            if (isBusy) return
            e.currentTarget.style.borderColor = COLORS.borderHover
            e.currentTarget.style.color = COLORS.textPrimary
            e.currentTarget.style.backgroundColor = COLORS.bgSubtleHover
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = COLORS.border
            e.currentTarget.style.color = COLORS.textSecondary
            e.currentTarget.style.backgroundColor = COLORS.bgSubtle
          }}
          onMouseDown={(e) => {
            if (!isBusy) e.currentTarget.style.transform = 'scale(0.97)'
          }}
          onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
        >
          <RefreshCw
            style={{
              width: '12px',
              height: '12px',
              animation: refreshing ? 'spin 0.8s linear infinite' : 'none',
            }}
          />
          Actualiser
        </button>
      </div>

      {/* Statistics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
        <StatCard label="Total" value={stats.total} color={COLORS.textPrimary} delay={0} loading={loading} />
        <StatCard label="Publiés" value={stats.published} color={COLORS.success} delay={40} loading={loading} />
        <StatCard label="Dry-run" value={stats.dryRun} color={COLORS.warning} delay={80} loading={loading} />
        <StatCard label="Modifications" value={stats.changes} color={COLORS.accent} delay={120} loading={loading} />
      </div>

      {/* Filters */}
      <div style={{ backgroundColor: COLORS.bgPanel, border: `1px solid ${COLORS.border}`, borderRadius: '9px', padding: '12px' }}>
        <div
          role="tablist"
          aria-label="Filtrer les publications"
          style={{
            display: 'flex',
            gap: '3px',
            backgroundColor: COLORS.bgInput,
            padding: '3px',
            borderRadius: '7px',
            border: `1px solid ${COLORS.border}`,
            width: 'fit-content',
            maxWidth: '100%',
            overflowX: 'auto',
          }}
        >
          {FILTERS.map((f) => (
            <button
              key={f}
              role="tab"
              aria-selected={filter === f}
              onClick={() => {
                setFilter(f)
              }}
              style={{
                padding: '6px 13px',
                backgroundColor: filter === f ? COLORS.accent : 'transparent',
                border: 'none',
                borderRadius: '5px',
                color: filter === f ? '#ffffff' : COLORS.textSecondary,
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'background-color 0.15s, color 0.15s',
                whiteSpace: 'nowrap',
              }}
              onMouseEnter={(e) => {
                if (filter !== f) e.currentTarget.style.color = COLORS.textPrimary
              }}
              onMouseLeave={(e) => {
                if (filter !== f) e.currentTarget.style.color = COLORS.textSecondary
              }}
            >
              {FILTER_LABELS[f]}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            color: COLORS.danger,
            fontSize: '12.5px',
            padding: '12px 14px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: '7px',
            animation: 'fadeIn 0.2s ease-out',
          }}
        >
          <AlertCircle style={{ width: '15px', height: '15px', flexShrink: 0, marginTop: '1px' }} />
          <div style={{ flex: 1 }}>{error}</div>
          <button
            onClick={() => fetchHistory(false)}
            style={{
              flexShrink: 0,
              background: 'transparent',
              border: `1px solid rgba(239, 68, 68, 0.4)`,
              borderRadius: '5px',
              color: COLORS.danger,
              fontSize: '11.5px',
              fontWeight: 500,
              padding: '4px 9px',
              cursor: 'pointer',
              transition: 'background-color 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.12)')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            Réessayer
          </button>
        </div>
      )}

      {/* History List */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }} aria-busy="true" aria-label="Chargement de l'historique">
          {[0, 1, 2].map((i) => (
            <SkeletonRow key={i} delay={i * 80} />
          ))}
        </div>
      ) : filteredItems.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            padding: '48px 20px',
            color: COLORS.textSecondary,
            backgroundColor: COLORS.bgPanel,
            border: `1px dashed ${COLORS.border}`,
            borderRadius: '9px',
            animation: 'fadeIn 0.3s ease-out',
          }}
        >
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '11px',
              backgroundColor: COLORS.bgSubtle,
              border: `1px solid ${COLORS.border}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 12px',
            }}
          >
            <FileText style={{ width: '18px', height: '18px', color: COLORS.textMuted }} />
          </div>
          <div style={{ marginBottom: '6px', fontSize: '13px', fontWeight: 500, color: COLORS.textPrimary }}>
            Aucune publication
          </div>
          <div style={{ fontSize: '11.5px', color: COLORS.textMuted }}>
            {items.length === 0
              ? "Aucune publication n'a encore été enregistrée."
              : 'Aucune publication ne correspond aux filtres actuels.'}
          </div>
          {items.length > 0 && filter !== 'all' && (
            <button
              onClick={() => setFilter('all')}
              style={{
                marginTop: '14px',
                background: 'transparent',
                border: `1px solid ${COLORS.border}`,
                borderRadius: '6px',
                color: COLORS.textSecondary,
                fontSize: '11.5px',
                fontWeight: 500,
                padding: '6px 12px',
                cursor: 'pointer',
                transition: 'border-color 0.15s, color 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = COLORS.borderHover
                e.currentTarget.style.color = COLORS.textPrimary
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = COLORS.border
                e.currentTarget.style.color = COLORS.textSecondary
              }}
            >
              Réinitialiser les filtres
            </button>
          )}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', opacity: refreshing ? 0.6 : 1, transition: 'opacity 0.15s' }}>
            {filteredItems.map((item, index) => (
              <HistoryRow
                key={item.revision_id ?? `${item.title}-${index}`}
                item={item}
                index={index}
                getStatusIcon={getStatusIcon}
                formatDate={formatDate}
              />
            ))}
          </div>

          {/* Pagination */}
          {(history?.total ?? 0) > PAGE_SIZE && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px' }}>
              <button
                onClick={() => canGoPrev && setPage((p) => Math.max(1, p - 1))}
                disabled={!canGoPrev || isBusy}
                aria-label="Page précédente"
                style={{
                  padding: '8px 14px',
                  backgroundColor: COLORS.bgSubtle,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '7px',
                  color: !canGoPrev ? COLORS.textMuted : COLORS.textSecondary,
                  fontSize: '12.5px',
                  fontWeight: 500,
                  cursor: !canGoPrev || isBusy ? 'not-allowed' : 'pointer',
                  opacity: !canGoPrev || isBusy ? 0.5 : 1,
                  transition: 'background-color 0.15s, color 0.15s',
                }}
                onMouseEnter={(e) => {
                  if (!canGoPrev || isBusy) return
                  e.currentTarget.style.backgroundColor = COLORS.bgSubtleHover
                  e.currentTarget.style.color = COLORS.textPrimary
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = COLORS.bgSubtle
                  e.currentTarget.style.color = COLORS.textSecondary
                }}
              >
                Précédent
              </button>
              <span style={{ fontSize: '12.5px', color: COLORS.textSecondary, fontVariantNumeric: 'tabular-nums' }}>
                Page {page} / {totalPages}
              </span>
              <button
                onClick={() => canGoNext && setPage((p) => p + 1)}
                disabled={!canGoNext || isBusy}
                aria-label="Page suivante"
                style={{
                  padding: '8px 14px',
                  backgroundColor: COLORS.bgSubtle,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '7px',
                  color: !canGoNext ? COLORS.textMuted : COLORS.textSecondary,
                  fontSize: '12.5px',
                  fontWeight: 500,
                  cursor: !canGoNext || isBusy ? 'not-allowed' : 'pointer',
                  opacity: !canGoNext || isBusy ? 0.5 : 1,
                  transition: 'background-color 0.15s, color 0.15s',
                }}
                onMouseEnter={(e) => {
                  if (!canGoNext || isBusy) return
                  e.currentTarget.style.backgroundColor = COLORS.bgSubtleHover
                  e.currentTarget.style.color = COLORS.textPrimary
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = COLORS.bgSubtle
                  e.currentTarget.style.color = COLORS.textSecondary
                }}
              >
                Suivant
              </button>
            </div>
          )}
        </>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.45; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
        }
        @media (max-width: 480px) {
          .history-row-meta { width: 100%; justify-content: flex-start; }
        }
      `}</style>
    </div>
  )
}

function StatCard({
  label,
  value,
  color,
  delay = 0,
  loading = false,
}: {
  label: string
  value: number
  color: string
  delay?: number
  loading?: boolean
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        backgroundColor: COLORS.bgPanel,
        border: `1px solid ${hovered ? COLORS.borderHover : COLORS.border}`,
        borderRadius: '9px',
        padding: '12px 14px',
        transition: 'border-color 0.15s, transform 0.15s, box-shadow 0.15s',
        transform: hovered ? 'translateY(-1px)' : 'none',
        boxShadow: hovered ? '0 6px 16px rgba(0,0,0,0.22)' : 'none',
        animation: `fadeInUp 0.35s ease-out ${delay}ms both`,
      }}
    >
      <div
        style={{
          fontSize: '10.5px',
          color: COLORS.textMuted,
          marginBottom: '6px',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          fontWeight: 500,
        }}
      >
        {label}
      </div>
      {loading ? (
        <div style={{ width: '36px', height: '20px', borderRadius: '4px', backgroundColor: '#222', animation: 'pulse 1.5s ease-in-out infinite' }} />
      ) : (
        <div style={{ fontSize: '20px', fontWeight: 600, color, letterSpacing: '-0.01em', fontVariantNumeric: 'tabular-nums' }}>
          {value.toLocaleString('fr-FR')}
        </div>
      )}
    </div>
  )
}

function SkeletonRow({ delay = 0 }: { delay?: number }) {
  return (
    <div
      style={{
        height: '78px',
        backgroundColor: COLORS.bgPanel,
        border: `1px solid ${COLORS.border}`,
        borderRadius: '10px',
        padding: '18px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '18px',
        animation: `fadeIn 0.3s ease-out ${delay}ms both`,
      }}
    >
      <div style={{ width: '15px', height: '15px', borderRadius: '50%', backgroundColor: '#222', animation: 'pulse 1.5s ease-in-out infinite', flexShrink: 0 }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ width: '40%', height: '13px', borderRadius: '4px', backgroundColor: '#222', animation: 'pulse 1.5s ease-in-out infinite' }} />
        <div style={{ width: '65%', height: '10px', borderRadius: '4px', backgroundColor: '#1e1e1e', animation: 'pulse 1.5s ease-in-out infinite' }} />
      </div>
      <div style={{ width: '100px', height: '11px', borderRadius: '4px', backgroundColor: '#1e1e1e', animation: 'pulse 1.5s ease-in-out infinite', flexShrink: 0 }} />
    </div>
  )
}

function HistoryRow({
  item,
  index,
  getStatusIcon,
  formatDate,
}: {
  item: HistoryItem
  index: number
  getStatusIcon: (dryRun: boolean, failed: boolean) => React.ReactNode
  formatDate: (t: any) => string
}) {
  const [hovered, setHovered] = useState(false)
  const isDryRun = item.mode === 'dry_run'
  const isFailed = item.status === 'failed'
  const isRejected = item.status === 'rejected'

  const handleOpen = () => {
    if (!item.title) return
    window.location.href = `/publication/detail?title=${encodeURIComponent(item.title)}`
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleOpen()
        }
      }}
      style={{
        backgroundColor: COLORS.bgPanel,
        border: `1px solid ${hovered ? COLORS.borderHover : COLORS.border}`,
        borderRadius: '10px',
        padding: '18px 20px',
        cursor: 'pointer',
        transition: 'border-color 0.15s, transform 0.15s, box-shadow 0.15s',
        transform: hovered ? 'translateY(-1px)' : 'none',
        boxShadow: hovered ? '0 5px 14px rgba(0,0,0,0.2)' : 'none',
        animation: `fadeInUp 0.3s ease-out ${Math.min(index * 30, 300)}ms both`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', flex: 1, minWidth: '220px' }}>
          <div style={{ marginTop: '2px', flexShrink: 0 }}>{getStatusIcon(isDryRun, isFailed)}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: '15px',
                fontWeight: 500,
                color: COLORS.textPrimary,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {item.title || 'Sans titre'}
            </div>
            <div style={{ fontSize: '11.5px', color: COLORS.textMuted, marginTop: '3px' }}>
              {formatDate(item.published_at)}
            </div>
          </div>
        </div>
        <div
          className="history-row-meta"
          style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11.5px', color: COLORS.textMuted, flexWrap: 'wrap' }}
        >
          {item.category && <span>{item.category}</span>}
          {item.category && <span>•</span>}
          <StatusBadge dryRun={isDryRun} failed={isFailed} rejected={isRejected} />
          {item.revision_id && (
            <>
              <span>•</span>
              <span>Rév. {item.revision_id}</span>
            </>
          )}
        </div>
      </div>

      {item.summary && (
        <div
          style={{
            fontSize: '12.5px',
            color: COLORS.textSecondary,
            marginTop: '10px',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '100%',
          }}
        >
          {item.summary}
        </div>
      )}
    </div>
  )
}

function StatusBadge({ dryRun, failed, rejected }: { dryRun: boolean; failed: boolean; rejected: boolean }) {
  const config = failed
    ? { label: 'Échoué', color: COLORS.danger, bg: 'rgba(239, 68, 68, 0.1)' }
    : rejected
      ? { label: 'Rejeté', color: COLORS.textMuted, bg: 'rgba(102, 102, 102, 0.15)' }
      : dryRun
        ? { label: 'Dry-run', color: COLORS.warning, bg: 'rgba(245, 158, 11, 0.1)' }
        : { label: 'Publié', color: COLORS.success, bg: 'rgba(16, 185, 129, 0.1)' }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '1.5px 7px',
        borderRadius: '4px',
        backgroundColor: config.bg,
        color: config.color,
        fontSize: '10px',
        fontWeight: 600,
        letterSpacing: '0.02em',
      }}
    >
      {config.label}
    </span>
  )
}