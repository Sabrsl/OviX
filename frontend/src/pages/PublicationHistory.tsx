import { useState, useEffect } from 'react'
import { CheckCircle, Clock, FileText, RefreshCw } from 'lucide-react'
import { historyApi } from '../api/history.api'

const COLORS = {
  bgPanel: '#161616',
  bgInput: '#0a0a0a',
  bgSubtle: '#1a1a1a',
  border: '#2a2a2a',
  textPrimary: '#f5f5f5',
  textSecondary: '#a0a0a0',
  textMuted: '#666666',
  accent: '#3b82f6',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
} as const

const FILTERS = ['all', 'published', 'failed', 'rejected'] as const
type FilterType = typeof FILTERS[number]

const FILTER_LABELS: Record<FilterType, string> = {
  all: 'Tous',
  published: 'Publiés',
  failed: 'Échoués',
  rejected: 'Rejetés',
}

export default function PublicationHistory() {
  const [history, setHistory] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterType>('all')
  const [page, setPage] = useState(1)

  const fetchHistory = async (isInitial = false) => {
    if (isInitial) setLoading(true)
    else setRefreshing(true)
    setError(null)
    try {
      const response = await historyApi.getPublishedHistory(page, 20)
      setHistory(response)
    } catch (err: any) {
      setError(err.message || err.userMessage || "Erreur lors de la récupération de l'historique")
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchHistory(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  const getStatusIcon = (dryRun: boolean) => {
    return dryRun
      ? <Clock style={{ width: '15px', height: '15px', color: COLORS.warning }} />
      : <CheckCircle style={{ width: '15px', height: '15px', color: COLORS.success }} />
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

  const filteredItems = history?.items?.filter((item: any) => {
    if (filter === 'all') return true
    if (filter === 'published') return item.mode !== 'dry_run'
    if (filter === 'failed') return false // Adjust based on actual data
    if (filter === 'rejected') return false // Adjust based on actual data
    return true
  }) || []

  const stats = {
    total: history?.total || 0,
    published: history?.items?.filter((i: any) => i.mode !== 'dry_run').length || 0,
    dryRun: history?.items?.filter((i: any) => i.mode === 'dry_run').length || 0,
    changes: history?.items?.reduce((sum: number, i: any) => sum + (i.changes_count || 0), 0) || 0,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.35s ease-out' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '19px', fontWeight: 600, color: COLORS.textPrimary, letterSpacing: '-0.01em', margin: 0 }}>
            Historique des publications
          </h2>
          <p style={{ color: COLORS.textSecondary, marginTop: '3px', fontSize: '12.5px' }}>
            Voir l'historique des publications et statistiques
          </p>
        </div>
        <button
          onClick={() => fetchHistory(false)}
          disabled={refreshing || loading}
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
            cursor: refreshing || loading ? 'not-allowed' : 'pointer',
            opacity: refreshing || loading ? 0.6 : 1,
            transition: 'background-color 0.15s, border-color 0.15s, color 0.15s, transform 0.1s',
          }}
          onMouseEnter={(e) => {
            if (refreshing || loading) return
            e.currentTarget.style.borderColor = '#3a3a3a'
            e.currentTarget.style.color = COLORS.textPrimary
            e.currentTarget.style.backgroundColor = '#1f1f1f'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = COLORS.border
            e.currentTarget.style.color = COLORS.textSecondary
            e.currentTarget.style.backgroundColor = COLORS.bgSubtle
          }}
          onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.97)')}
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
        <StatCard label="Total" value={stats.total} color={COLORS.textPrimary} delay={0} />
        <StatCard label="Publiés" value={stats.published} color={COLORS.success} delay={40} />
        <StatCard label="Dry-run" value={stats.dryRun} color={COLORS.warning} delay={80} />
        <StatCard label="Modifications" value={stats.changes} color={COLORS.accent} delay={120} />
      </div>

      {/* Filters */}
      <div style={{ backgroundColor: COLORS.bgPanel, border: `1px solid ${COLORS.border}`, borderRadius: '9px', padding: '12px' }}>
        <div style={{ display: 'flex', gap: '3px', backgroundColor: COLORS.bgInput, padding: '3px', borderRadius: '7px', border: `1px solid ${COLORS.border}`, width: 'fit-content' }}>
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
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
          style={{
            color: COLORS.danger,
            fontSize: '12.5px',
            padding: '10px 14px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: '7px',
            animation: 'fadeIn 0.2s ease-out',
          }}
        >
          {error}
        </div>
      )}

      {/* History List */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
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
            Aucune publication ne correspond aux filtres actuels.
          </div>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {filteredItems.map((item: any, index: number) => (
              <HistoryRow
                key={index}
                item={item}
                index={index}
                getStatusIcon={getStatusIcon}
                formatDate={formatDate}
              />
            ))}
          </div>

          {/* Pagination */}
          {history?.total > 20 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px' }}>
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                style={{
                  padding: '8px 14px',
                  backgroundColor: COLORS.bgSubtle,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '7px',
                  color: page === 1 ? COLORS.textMuted : COLORS.textSecondary,
                  fontSize: '12.5px',
                  fontWeight: 500,
                  cursor: page === 1 ? 'not-allowed' : 'pointer',
                  opacity: page === 1 ? 0.5 : 1,
                  transition: 'background-color 0.15s, color 0.15s',
                }}
                onMouseEnter={(e) => {
                  if (page === 1) return
                  e.currentTarget.style.backgroundColor = '#1f1f1f'
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
                Page {page}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={(page * 20) >= (history?.total || 0)}
                style={{
                  padding: '8px 14px',
                  backgroundColor: COLORS.bgSubtle,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '7px',
                  color: (page * 20) >= (history?.total || 0) ? COLORS.textMuted : COLORS.textSecondary,
                  fontSize: '12.5px',
                  fontWeight: 500,
                  cursor: (page * 20) >= (history?.total || 0) ? 'not-allowed' : 'pointer',
                  opacity: (page * 20) >= (history?.total || 0) ? 0.5 : 1,
                  transition: 'background-color 0.15s, color 0.15s',
                }}
                onMouseEnter={(e) => {
                  if ((page * 20) >= (history?.total || 0)) return
                  e.currentTarget.style.backgroundColor = '#1f1f1f'
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
      `}</style>
    </div>
  )
}

function StatCard({
  label,
  value,
  color,
  delay = 0,
}: {
  label: string
  value: number
  color: string
  delay?: number
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        backgroundColor: '#161616',
        border: `1px solid ${hovered ? '#3a3a3a' : '#2a2a2a'}`,
        borderRadius: '9px',
        padding: '12px 14px',
        transition: 'border-color 0.15s, transform 0.15s, box-shadow 0.15s',
        transform: hovered ? 'translateY(-1px)' : 'none',
        boxShadow: hovered ? '0 6px 16px rgba(0,0,0,0.22)' : 'none',
        animation: `fadeInUp 0.35s ease-out ${delay}ms both`,
      }}
    >
      <div style={{ fontSize: '10.5px', color: '#666666', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>
        {label}
      </div>
      <div style={{ fontSize: '20px', fontWeight: 600, color, letterSpacing: '-0.01em', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  )
}

function SkeletonRow({ delay = 0 }: { delay?: number }) {
  return (
    <div
      style={{
        height: '78px',
        backgroundColor: '#161616',
        border: '1px solid #2a2a2a',
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
  item: any
  index: number
  getStatusIcon: (dryRun: boolean) => React.ReactNode
  formatDate: (t: any) => string
}) {
  const [hovered, setHovered] = useState(false)
  const isDryRun = item.mode === 'dry_run'

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => (window.location.href = `/publication/detail?title=${encodeURIComponent(item.title)}`)}
      style={{
        backgroundColor: COLORS.bgPanel,
        border: `1px solid ${hovered ? '#3a3a3a' : COLORS.border}`,
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
          <div style={{ marginTop: '2px', flexShrink: 0 }}>{getStatusIcon(isDryRun)}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '15px', fontWeight: 500, color: COLORS.textPrimary, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {item.title}
            </div>
            <div style={{ fontSize: '11.5px', color: COLORS.textMuted, marginTop: '3px' }}>
              {formatDate(item.published_at)}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11.5px', color: COLORS.textMuted, flexWrap: 'wrap' }}>
          {item.category && <span>{item.category}</span>}
          {item.category && <span>•</span>}
          <StatusBadge dryRun={isDryRun} />
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

function StatusBadge({ dryRun }: { dryRun: boolean }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '1.5px 7px',
        borderRadius: '4px',
        backgroundColor: dryRun ? 'rgba(245, 158, 11, 0.1)' : 'rgba(16, 185, 129, 0.1)',
        color: dryRun ? COLORS.warning : COLORS.success,
        fontSize: '10px',
        fontWeight: 600,
        letterSpacing: '0.02em',
      }}
    >
      {dryRun ? 'Dry-run' : 'Publié'}
    </span>
  )
}