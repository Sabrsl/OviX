import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle, XCircle, Clock, FileText, RefreshCw, Eye, AlertTriangle, Search, Loader2 } from 'lucide-react'
import { historyApi } from '../api/history.api'
import { articlesApi } from '../api/articles.api'
import { systemApi } from '../api/system.api'

// ---------------------------------------------------------------------------
// Types (kept loose/optional-safe on purpose: upstream payloads are `any`,
// so every field is defensively read with fallbacks throughout the file).
// ---------------------------------------------------------------------------
type Status = 'published' | 'pending' | 'rejected' | 'ignored' | 'error' | 'analyzing'

interface HistoryItem {
  title: string
  article_title?: string
  page_id?: string | number
  revision_id?: string | number
  status: Status
  analysis_date?: string
  analyzed_at?: string
  changes_count?: number
  corrections_count?: number
  summary?: string
  job_id?: string | null
  character_count?: number
  total_links?: number
  dead_links_count?: number
  corrected_links_count?: number
  human_verified?: boolean
  mode?: string
}

const VALID_STATUSES: Status[] = ['published', 'pending', 'rejected', 'ignored', 'error', 'analyzing']
const DEBOUNCE_MS = 250
const MAX_RETRIES = 2

const STATUS_META: Record<Status, { label: string; color: string; icon: typeof CheckCircle }> = {
  published: { label: 'Publié', color: '#10b981', icon: CheckCircle },
  pending: { label: 'En attente', color: '#f59e0b', icon: Clock },
  rejected: { label: 'Refusé', color: '#ef4444', icon: XCircle },
  ignored: { label: 'Ignoré', color: '#666666', icon: Clock },
  error: { label: 'Erreur', color: '#ef4444', icon: XCircle },
  analyzing: { label: 'Analyse…', color: '#3b82f6', icon: Loader2 },
}

function safeDate(value?: string): Date | null {
  if (!value) return null
  const d = new Date(value)
  return isNaN(d.getTime()) ? null : d
}

function formatDate(value?: string): string {
  const d = safeDate(value)
  if (!d) return 'Date inconnue'
  return d.toLocaleString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function formatNumber(n?: number): string {
  if (typeof n !== 'number' || isNaN(n)) return '0'
  return n.toLocaleString('fr-FR')
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(handle)
  }, [value, delayMs])
  return debounced
}

async function withRetry<T>(fn: () => Promise<T>, retries = MAX_RETRIES): Promise<T> {
  let lastErr: any
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastErr = err
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 400 * (attempt + 1)))
      }
    }
  }
  throw lastErr
}

export default function AnalyzedHistory() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [rawItems, setRawItems] = useState<HistoryItem[]>([])
  const [publishedTitles, setPublishedTitles] = useState<Set<string>>(new Set())
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [partialWarning, setPartialWarning] = useState<string | null>(null)
  const [analyzingArticles, setAnalyzingArticles] = useState<HistoryItem[]>([])

  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [modeFilter, setModeFilter] = useState<string>('all')
  const [searchInput, setSearchInput] = useState<string>(searchParams.get('search') || '')
  const [dateFilter, setDateFilter] = useState<string>('all')
  const searchQuery = useDebouncedValue(searchInput, DEBOUNCE_MS)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  // Prevents a slow, superseded request from clobbering fresher state.
  const requestIdRef = useRef(0)

  const fetchHistory = useCallback(async (isManualRefresh = false, isInitial = false) => {
    const requestId = ++requestIdRef.current
    if (isInitial) {
      setLoading(true)
    } else if (isManualRefresh) {
      setRefreshing(true)
    }
    setError(null)
    setPartialWarning(null)

    const offset = (page - 1) * PAGE_SIZE

    const results = await Promise.allSettled([
      withRetry(() => articlesApi.getArticleHistory(PAGE_SIZE, offset)),
      withRetry(() => historyApi.getPublishedHistory()),
      withRetry(() => articlesApi.getAnalysisResultsCount('pending')),
    ])

    if (requestId !== requestIdRef.current) return // a newer request already landed

    const [analyzedResult, publishedResult, countResult] = results
    const analyzedOk = analyzedResult.status === 'fulfilled'
    const publishedOk = publishedResult.status === 'fulfilled'
    const countOk = countResult.status === 'fulfilled'

    if (!analyzedOk) {
      const err: any = analyzedResult.reason
      setError(err?.message || err?.userMessage || 'Impossible de récupérer l\'historique des articles analysés.')
      if (isInitial) {
        setLoading(false)
      }
      if (isManualRefresh) {
        setRefreshing(false)
      }
      return
    }

    const analyzedResponse = analyzedResult.value
    const rawList = Array.isArray(analyzedResponse) ? analyzedResponse : []

    // Set total count from database
    if (countOk) {
      setTotalCount(countResult.value.total)
    }

    const normalized: HistoryItem[] = rawList
      .filter((item: any) => item && (item.title || item.article_title))
      .map((item: any): HistoryItem => ({
        title: item.title ?? item.article_title,
        article_title: item.article_title,
        page_id: item.page_id,
        revision_id: item.revision_id,
        status: VALID_STATUSES.includes(item.status) ? item.status : 'pending',
        analysis_date: item.analysis_date ?? item.analyzed_at,
        changes_count: Number(item.changes_count) || 0,
        summary: item.summary,
        job_id: item.job_id ?? null,
        character_count: Number(item.character_count) || 0,
        total_links: item.total_links,
        dead_links_count: Number(item.dead_links_count) || 0,
        corrected_links_count: item.corrected_links_count,
        human_verified: item.human_verified,
        mode: item.mode,
      }))

    setRawItems(normalized)

    if (publishedOk) {
      const publishedResponse: any = publishedResult.value
      const pubItems = Array.isArray(publishedResponse?.items) ? publishedResponse.items : []
      const titles = new Set<string>(
        pubItems
          .map((p: any) => p?.title || p?.article_title)
          .filter((t: any): t is string => typeof t === 'string' && t.length > 0)
      )
      setPublishedTitles(titles)
    } else {
      // Analyzed history loaded fine; published status just can't be cross-checked.
      setPublishedTitles(new Set())
      setPartialWarning('Le statut "Publié" peut être incomplet : le service de suivi des publications est indisponible.')
    }

    if (isInitial) {
      setLoading(false)
    }
    setRefreshing(false)
  }, [])

  useEffect(() => {
    fetchHistory(false, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  // Fetch articles currently being analyzed from automation status
  useEffect(() => {
    const fetchAnalyzingArticles = async () => {
      try {
        const automationStatus = await systemApi.getAutomationStatus()
        if (automationStatus.success && automationStatus.article_states) {
          const analyzing: HistoryItem[] = automationStatus.article_states
            .filter((state: any) => state.status === 'analyzing' || state.status === 'retrieving' || state.status === 'correcting')
            .map((state: any): HistoryItem => ({
              title: state.title,
              status: 'analyzing',
              analysis_date: state.started_at,
              changes_count: 0,
              corrected_links_count: 0,
              dead_links_count: 0,
              total_links: 0,
              character_count: 0,
            }))
          setAnalyzingArticles(analyzing)
        } else {
          setAnalyzingArticles([])
        }
      } catch (err) {
        console.error('Failed to fetch analyzing articles:', err)
        setAnalyzingArticles([])
      }
    }

    fetchAnalyzingArticles()
    // Polling disabled by default to prevent UI blocking
    // User can manually refresh with the refresh button
    // const interval = setInterval(fetchAnalyzingArticles, 3000) // Poll every 3 seconds
    // return () => clearInterval(interval)
  }, [])

  const enrichedItems = useMemo(() => {
    // Combine analyzing articles with analyzed articles
    const combined = [...analyzingArticles, ...rawItems]
    return combined.map((item) => {
      // Use status directly from backend (SQLite source of truth)
      return {
        ...item,
        status: item.status,
      }
    })
  }, [rawItems, analyzingArticles])

  const normalizedItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    const now = Date.now()
    const cutoffMs =
      dateFilter === '24h' ? 24 * 60 * 60 * 1000 :
      dateFilter === '7d' ? 7 * 24 * 60 * 60 * 1000 :
      dateFilter === '30d' ? 30 * 24 * 60 * 60 * 1000 :
      null

    return enrichedItems
      .filter((item) => {
        if (statusFilter !== 'all' && item.status !== statusFilter) return false
        if (modeFilter === 'ia' && item.mode !== 'IA') return false
        if (modeFilter === 'regex' && item.mode !== 'regex') return false
        if (query && !item.title.toLowerCase().includes(query)) return false
        if (cutoffMs !== null) {
          const d = safeDate(item.analysis_date)
          if (!d || now - d.getTime() > cutoffMs) return false
        }
        return true
      })
      .sort((a, b) => {
        const dateA = safeDate(a.analysis_date)?.getTime() ?? 0
        const dateB = safeDate(b.analysis_date)?.getTime() ?? 0
        return dateB - dateA
      })
  }, [enrichedItems, statusFilter, modeFilter, searchQuery, dateFilter])

  const stats = useMemo(() => {
    const counts: Record<Status, number> = { published: 0, pending: 0, rejected: 0, ignored: 0, error: 0, analyzing: 0 }
    for (const item of enrichedItems) counts[item.status]++
    return counts
  }, [enrichedItems])

  const hasActiveFilters = statusFilter !== 'all' || modeFilter !== 'all' || searchInput !== '' || dateFilter !== 'all'

  const clearFilters = () => {
    setStatusFilter('all')
    setModeFilter('all')
    setSearchInput('')
    setDateFilter('all')
  }

  const handleViewDetails = (item: HistoryItem) => {
    const articleTitle = item.title || item.article_title
    if (!articleTitle) return
    const params = new URLSearchParams()
    params.set('title', articleTitle)
    if (item.job_id) params.set('jobId', item.job_id)
    navigate(`/article/detail?${params.toString()}`)
  }

  // ---- Loading state -------------------------------------------------------
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>Historique d'analyse</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Voir les articles analysés et leur statut</p>
        </div>
        <SkeletonBlock />
      </div>
    )
  }

  // ---- Hard error state (analyzed history itself failed) -------------------
  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>Historique d'analyse</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Voir les articles analysés et leur statut</p>
        </div>
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px',
          padding: '48px', backgroundColor: '#161616', borderRadius: '8px', border: '1px solid #3a1f1f'
        }}>
          <AlertTriangle style={{ width: '40px', height: '40px', color: '#ef4444' }} />
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '16px', fontWeight: 500, color: '#f5f5f5', marginBottom: '4px' }}>
              Chargement impossible
            </div>
            <div style={{ fontSize: '14px', color: '#a0a0a0', maxWidth: '420px' }}>{error}</div>
          </div>
          <button
            className="btn btn-secondary"
            onClick={() => fetchHistory(true)}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            Réessayer
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', animation: 'fadeIn 0.2s ease-in-out' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#f5f5f5' }}>Articles Analysés</h2>
          <p style={{ color: '#a0a0a0', marginTop: '2px', fontSize: '12px' }}>Voir les articles analysés et leur statut</p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => fetchHistory(true)}
          disabled={refreshing}
          style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            opacity: refreshing ? 0.6 : 1,
            cursor: refreshing ? 'not-allowed' : 'pointer',
            fontSize: '12px'
          }}
        >
          <RefreshCw style={{ width: '13px', height: '13px', animation: refreshing ? 'spin 0.8s linear infinite' : 'none' }} />
          {refreshing ? 'Actualisation…' : 'Actualiser'}
        </button>
      </div>

      {partialWarning && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: '8px',
          backgroundColor: '#1f1a0f', border: '1px solid #4a3a10', borderRadius: '6px', padding: '8px 12px'
        }}>
          <AlertTriangle style={{ width: '13px', height: '13px', color: '#f59e0b', flexShrink: 0, marginTop: '2px' }} />
          <span style={{ fontSize: '11px', color: '#d4b877' }}>{partialWarning}</span>
        </div>
      )}

      {/* Filters */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '12px 14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <h3 style={{ fontSize: '10px', fontWeight: 600, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Filtres
          </h3>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              style={{ background: 'none', border: 'none', color: '#3b82f6', fontSize: '11px', cursor: 'pointer', padding: 0 }}
            >
              Réinitialiser
            </button>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
          {/* Status Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#a0a0a0', marginBottom: '4px' }}>
              Statut
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={selectStyle}
            >
              <option value="all">Tous</option>
              <option value="published">Publié</option>
              <option value="rejected">Refusé</option>
              <option value="ignored">Ignoré</option>
              <option value="pending">En attente</option>
              <option value="analyzing">En cours d'analyse</option>
              <option value="error">Erreur</option>
            </select>
          </div>

          {/* Type de correction Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#a0a0a0', marginBottom: '4px' }}>
              Type de correction
            </label>
            <select
              value={modeFilter}
              onChange={(e) => setModeFilter(e.target.value)}
              style={selectStyle}
            >
              <option value="all">Tous</option>
              <option value="ia">IA</option>
              <option value="regex">Règles</option>
            </select>
          </div>

          {/* Date Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#a0a0a0', marginBottom: '4px' }}>
              Période
            </label>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              style={selectStyle}
            >
              <option value="all">Toutes</option>
              <option value="24h">Dernières 24h</option>
              <option value="7d">Derniers 7 jours</option>
              <option value="30d">Derniers 30 jours</option>
            </select>
          </div>

          {/* Search */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#a0a0a0', marginBottom: '4px' }}>
              Recherche
            </label>
            <div style={{ position: 'relative' }}>
              <Search style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', width: '12px', height: '12px', color: '#666666' }} />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Rechercher par titre..."
                style={{ ...selectStyle, paddingLeft: '34px' }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Statistics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
        <StatCard label="Total" value={totalCount} color="#f5f5f5" />
        <StatCard label="En attente" value={stats.pending} color={STATUS_META.pending.color} />
        <StatCard label="Publiés" value={stats.published} color={STATUS_META.published.color} />
        <StatCard label="Rejetés" value={stats.rejected} color={STATUS_META.rejected.color} />
      </div>

      {/* History List */}
      {normalizedItems.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '32px', backgroundColor: '#161616', borderRadius: '8px', border: '1px solid #2a2a2a' }}>
          <div style={{ textAlign: 'center', color: '#666666' }}>
            <FileText style={{ width: '36px', height: '36px', color: '#2a2a2a', margin: '0 auto 12px' }} />
            <div style={{ fontSize: '13px', marginBottom: '4px', color: '#a0a0a0' }}>
              {totalCount === 0 ? 'Aucun article analysé' : 'Aucun résultat'}
            </div>
            <div style={{ fontSize: '11px', marginBottom: hasActiveFilters ? '12px' : 0 }}>
              {hasActiveFilters
                ? 'Aucun article ne correspond aux filtres actuels.'
                : 'Commencez par analyser des articles pour voir l\'historique.'}
            </div>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="btn btn-secondary"
                style={{ fontSize: '11px' }}
              >
                Réinitialiser les filtres
              </button>
            )}
          </div>
        </div>
      ) : (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '14px 16px' }}>
          <div style={{ fontSize: '11px', color: '#666666', marginBottom: '10px' }}>
            Affichage de {normalizedItems.length} article{normalizedItems.length > 1 ? 's' : ''}
            {hasActiveFilters && totalCount !== normalizedItems.length ? ` sur ${totalCount}` : ''}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {normalizedItems.map((item, index) => (
              <HistoryRow key={`${item.title}-${item.revision_id ?? item.job_id ?? index}`} item={item} onOpen={handleViewDetails} />
            ))}
          </div>
          
          {/* Pagination controls */}
          {totalCount > PAGE_SIZE && (
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center', 
              gap: '12px', 
              marginTop: '16px', 
              paddingTop: '16px', 
              borderTop: '1px solid #2a2a2a' 
            }}>
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn btn-secondary"
                style={{ 
                  fontSize: '12px', 
                  padding: '6px 12px',
                  opacity: page === 1 ? 0.5 : 1,
                  cursor: page === 1 ? 'not-allowed' : 'pointer'
                }}
              >
                Précédent
              </button>
              <span style={{ fontSize: '12px', color: '#a0a0a0' }}>
                Page {page}
              </span>
              <button
                onClick={() => setPage(p => p + 1)}
                disabled={normalizedItems.length < PAGE_SIZE}
                className="btn btn-secondary"
                style={{ 
                  fontSize: '12px', 
                  padding: '6px 12px',
                  opacity: normalizedItems.length < PAGE_SIZE ? 0.5 : 1,
                  cursor: normalizedItems.length < PAGE_SIZE ? 'not-allowed' : 'pointer'
                }}
              >
                Suivant
              </button>
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }
      `}</style>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Presentational helpers
// ---------------------------------------------------------------------------

const selectStyle: React.CSSProperties = {
  width: '100%',
  padding: '7px 8px',
  backgroundColor: '#0a0a0a',
  border: '1px solid #2a2a2a',
  borderRadius: '5px',
  color: '#f5f5f5',
  fontSize: '12px',
  boxSizing: 'border-box',
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '6px', padding: '10px 12px' }}>
      <div style={{ fontSize: '10px', color: '#666666', marginBottom: '2px' }}>{label}</div>
      <div style={{ fontSize: '17px', fontWeight: 600, color }}>{formatNumber(value)}</div>
    </div>
  )
}

function HistoryRow({ item, onOpen }: { item: HistoryItem; onOpen: (item: HistoryItem) => void }) {
  const meta = STATUS_META[item.status] ?? STATUS_META.pending
  const Icon = meta.icon
  const isSpinning = item.status === 'analyzing'

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onOpen(item)
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(item)}
      onKeyDown={handleKeyDown}
      style={{
        backgroundColor: '#1a1a1a',
        border: '1px solid #2a2a2a',
        borderRadius: '7px',
        padding: '10px 12px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        outlineOffset: '2px',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = '#3b82f6'
        e.currentTarget.style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(59, 130, 246, 0.1)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = '#2a2a2a'
        e.currentTarget.style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = 'none'
      }}
      onFocus={(e) => {
        e.currentTarget.style.borderColor = '#3b82f6'
      }}
      onBlur={(e) => {
        e.currentTarget.style.borderColor = '#2a2a2a'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', minWidth: 0 }}>
          <Icon style={{ width: '14px', height: '14px', color: meta.color, flexShrink: 0, marginTop: '2px', animation: isSpinning ? 'spin 1s linear infinite' : 'none' }} />
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontSize: '13px', fontWeight: 500, color: '#f5f5f5',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
            }}>
              {item.title || 'Titre inconnu'}
            </div>
            <div style={{ fontSize: '10px', color: '#666666', marginTop: '1px' }}>
              {formatDate(item.analysis_date)}
            </div>
            <div style={{ fontSize: '10px', color: '#888888', marginTop: '2px' }}>
              Type de correction: {item.mode === 'ia' ? 'IA' : item.mode === 'regex' ? 'Règles' : 'Règles'} • Modifications: {formatNumber(item.corrected_links_count)}
            </div>
            {(item.character_count ?? 0) > 0 && (
              <div style={{ fontSize: '10px', color: '#888888', marginTop: '1px' }}>
                {formatNumber(item.character_count)} caractères
              </div>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
          <span style={{
            fontSize: '10px', fontWeight: 500, color: meta.color,
            backgroundColor: `${meta.color}1a`, padding: '3px 8px', borderRadius: '999px'
          }}>
            {meta.label}
          </span>
          <Eye style={{ width: '14px', height: '14px', color: '#666666' }} />
        </div>
      </div>
    </div>
  )
}

function SkeletonBlock() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} style={{
            height: '72px', backgroundColor: '#161616', border: '1px solid #2a2a2a',
            borderRadius: '8px', animation: 'pulse 1.5s ease-in-out infinite'
          }} />
        ))}
      </div>
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} style={{
              height: '76px', backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a',
              borderRadius: '8px', animation: 'pulse 1.5s ease-in-out infinite', animationDelay: `${i * 0.1}s`
            }} />
          ))}
        </div>
      </div>
      <style>{`@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 0.8; } }`}</style>
    </div>
  )
}