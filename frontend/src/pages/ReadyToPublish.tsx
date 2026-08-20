import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Search, RefreshCw, Inbox } from 'lucide-react'
import { historyApi } from '../api/history.api'
import { articlesApi } from '../api/articles.api'

interface ReadyToPublishItem {
  title: string
  page_id: number
  revision_id: number
  analysis_date: string
  status: string
  mode: string
  changes_count: number
  character_count: number
  dead_links_count: number
  corrected_links_count: number
  human_verified: boolean
  summary?: string
}

type FilterType = 'all' | 'verified' | 'unverified'

// Palette centralisée : mêmes couleurs qu'à l'origine, juste factorisées pour cohérence
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

const FILTERS: { key: FilterType; label: string }[] = [
  { key: 'all', label: 'Tous' },
  { key: 'verified', label: 'Vérifiés' },
  { key: 'unverified', label: 'Non vérifiés' },
]

export default function ReadyToPublish() {
  const navigate = useNavigate()
  const [articles, setArticles] = useState<ReadyToPublishItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterType>('all')
  const [searchQuery, setSearchQuery] = useState('')

  const loadReadyToPublish = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true)
    else setRefreshing(true)
    setError(null)

    try {
      const [analyzedResponse, publishedResponse, pendingQueueResponse] = await Promise.all([
        articlesApi.getArticleHistory(100),
        historyApi.getPublishedHistory(),
        articlesApi.getPendingSchedulerQueue(),
      ])

      const pendingQueueTitles = new Set(
        (pendingQueueResponse.articles || []).map((item: any) => item.article_title || item.title)
      )

      const publishedTitles = new Set(
        (publishedResponse.items || []).map((item: any) => item.title)
      )

      const readyToPublish: ReadyToPublishItem[] = analyzedResponse
        .filter((item: any) => {
          const title = item.title || item.article_title
          const isPublished = publishedTitles.has(item.title)
          const isInSchedulerQueue = pendingQueueTitles.has(title)
          const hasValidCorrections = item.corrected_links_count > 0
          return !isPublished && !isInSchedulerQueue && hasValidCorrections
        })
        .map((item: any) => ({
          title: item.title || item.article_title,
          page_id: item.page_id,
          revision_id: item.revision_id,
          analysis_date: item.analysis_date,
          status: 'analyzed',
          mode: item.mode || 'unknown',
          changes_count: item.changes_count,
          character_count: item.character_count,
          dead_links_count: item.dead_links_count,
          corrected_links_count: item.corrected_links_count,
          human_verified: item.human_verified,
          summary: item.summary,
        }))
        .sort((a, b) => {
          const dateA = new Date(a.analysis_date || 0).getTime()
          const dateB = new Date(b.analysis_date || 0).getTime()
          return dateB - dateA
        })

      setArticles(readyToPublish)
    } catch (err: any) {
      setError(err?.message || 'Erreur lors du chargement des articles')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadReadyToPublish(true)
  }, [loadReadyToPublish])

  const filteredArticles = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    return articles.filter((article) => {
      const matchesSearch = !query || article.title.toLowerCase().includes(query)
      const matchesFilter =
        filter === 'all' ||
        (filter === 'verified' && article.human_verified) ||
        (filter === 'unverified' && !article.human_verified)
      return matchesSearch && matchesFilter
    })
  }, [articles, filter, searchQuery])

  const stats = useMemo(
    () => ({
      total: articles.length,
      verified: articles.filter((a) => a.human_verified).length,
      unverified: articles.filter((a) => !a.human_verified).length,
      corrections: articles.reduce((sum, a) => sum + a.corrected_links_count, 0),
    }),
    [articles]
  )

  const handleViewDetails = (title: string) => {
    navigate(`/article/detail?title=${encodeURIComponent(title)}`)
  }

  const handlePublish = (title: string) => {
    navigate(`/article/detail?title=${encodeURIComponent(title)}&publish=true`)
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return '—'
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return '—'
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatNumber = (num: number) => (num ?? 0).toLocaleString('fr-FR')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.35s ease-out' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '19px', fontWeight: 600, color: COLORS.textPrimary, letterSpacing: '-0.01em', margin: 0 }}>
            À publier
          </h2>
          <p style={{ color: COLORS.textSecondary, marginTop: '3px', fontSize: '12.5px' }}>
            Articles analysés avec corrections valides, prêts à publication
          </p>
        </div>
        <button
          onClick={() => loadReadyToPublish(false)}
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
        <StatCard label="Vérifiés" value={stats.verified} color={COLORS.success} delay={40} />
        <StatCard label="Non vérifiés" value={stats.unverified} color={COLORS.warning} delay={80} />
        <StatCard label="Corrections totales" value={stats.corrections} color={COLORS.accent} delay={120} />
      </div>

      {/* Filters */}
      <div style={{ backgroundColor: COLORS.bgPanel, border: `1px solid ${COLORS.border}`, borderRadius: '9px', padding: '12px' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <div style={{ position: 'relative' }}>
              <Search
                style={{
                  position: 'absolute',
                  left: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: '13px',
                  height: '13px',
                  color: COLORS.textMuted,
                  pointerEvents: 'none',
                }}
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Rechercher un article..."
                style={{
                  width: '100%',
                  padding: '8px 10px 8px 32px',
                  backgroundColor: COLORS.bgInput,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '7px',
                  color: COLORS.textPrimary,
                  fontSize: '12.5px',
                  outline: 'none',
                  transition: 'border-color 0.15s, box-shadow 0.15s',
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = COLORS.accent
                  e.currentTarget.style.boxShadow = `0 0 0 3px ${COLORS.accent}1a`
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = COLORS.border
                  e.currentTarget.style.boxShadow = 'none'
                }}
              />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '3px', backgroundColor: COLORS.bgInput, padding: '3px', borderRadius: '7px', border: `1px solid ${COLORS.border}` }}>
            {FILTERS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                style={{
                  padding: '6px 11px',
                  backgroundColor: filter === key ? COLORS.accent : 'transparent',
                  border: 'none',
                  borderRadius: '5px',
                  color: filter === key ? '#ffffff' : COLORS.textSecondary,
                  fontSize: '12px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'background-color 0.15s, color 0.15s',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={(e) => {
                  if (filter !== key) e.currentTarget.style.color = COLORS.textPrimary
                }}
                onMouseLeave={(e) => {
                  if (filter !== key) e.currentTarget.style.color = COLORS.textSecondary
                }}
              >
                {label}
              </button>
            ))}
          </div>
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
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            animation: 'fadeIn 0.2s ease-out',
          }}
        >
          <AlertTriangle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          {error}
        </div>
      )}

      {/* Articles List */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {[0, 1, 2].map((i) => (
            <SkeletonRow key={i} delay={i * 80} />
          ))}
        </div>
      ) : filteredArticles.length === 0 ? (
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
            <Inbox style={{ width: '18px', height: '18px', color: COLORS.textMuted }} />
          </div>
          <div style={{ marginBottom: '6px', fontSize: '13px', fontWeight: 500, color: COLORS.textPrimary }}>
            Aucun article prêt à publication
          </div>
          <div style={{ fontSize: '11.5px', color: COLORS.textMuted }}>
            {filter !== 'all' || searchQuery
              ? 'Aucun article ne correspond aux filtres actuels.'
              : 'Les articles analysés avec corrections valides apparaîtront ici.'}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredArticles.map((article, index) => (
            <ArticleRow
              key={article.title || index}
              article={article}
              index={index}
              formatDate={formatDate}
              formatNumber={formatNumber}
              onView={() => handleViewDetails(article.title)}
              onPublish={() => handlePublish(article.title)}
            />
          ))}
        </div>
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
        @keyframes shimmer {
          0% { background-position: -200px 0; }
          100% { background-position: 200px 0; }
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

function ModeBadge({ mode }: { mode: string }) {
  const label = (mode || 'unknown').toUpperCase()
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '1px 5px',
        borderRadius: '4px',
        backgroundColor: '#1a1a1a',
        border: '1px solid #2a2a2a',
        color: '#a0a0a0',
        fontSize: '8.5px',
        fontWeight: 600,
        letterSpacing: '0.03em',
      }}
    >
      {label}
    </span>
  )
}

function SkeletonRow({ delay = 0 }: { delay?: number }) {
  return (
    <div
      style={{
        height: '62px',
        backgroundColor: '#161616',
        border: '1px solid #2a2a2a',
        borderRadius: '9px',
        padding: '13px',
        display: 'flex',
        alignItems: 'center',
        gap: '13px',
        animation: `fadeIn 0.3s ease-out ${delay}ms both`,
      }}
    >
      <div style={{ width: '16px', height: '16px', borderRadius: '50%', backgroundColor: '#222', animation: 'pulse 1.5s ease-in-out infinite', flexShrink: 0 }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ width: '45%', height: '11px', borderRadius: '4px', backgroundColor: '#222', animation: 'pulse 1.5s ease-in-out infinite' }} />
        <div style={{ width: '70%', height: '9px', borderRadius: '4px', backgroundColor: '#1e1e1e', animation: 'pulse 1.5s ease-in-out infinite' }} />
      </div>
      <div style={{ width: '120px', height: '26px', borderRadius: '6px', backgroundColor: '#1e1e1e', animation: 'pulse 1.5s ease-in-out infinite', flexShrink: 0 }} />
    </div>
  )
}

function ArticleRow({
  article,
  index,
  formatDate,
  formatNumber,
  onView,
  onPublish,
}: {
  article: ReadyToPublishItem
  index: number
  formatDate: (d: string) => string
  formatNumber: (n: number) => string
  onView: () => void
  onPublish: () => void
}) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: '13px 14px',
        backgroundColor: '#161616',
        border: `1px solid ${hovered ? '#3a3a3a' : '#2a2a2a'}`,
        borderRadius: '9px',
        display: 'flex',
        alignItems: 'center',
        gap: '13px',
        transition: 'border-color 0.15s, transform 0.15s, box-shadow 0.15s',
        transform: hovered ? 'translateY(-1px)' : 'none',
        boxShadow: hovered ? '0 5px 14px rgba(0,0,0,0.2)' : 'none',
        animation: `fadeInUp 0.3s ease-out ${Math.min(index * 30, 300)}ms both`,
      }}
    >
      <div
        title={article.human_verified ? 'Vérifié' : 'Non vérifié'}
        style={{
          flexShrink: 0,
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          backgroundColor: article.human_verified ? '#10b981' : '#f59e0b',
        }}
      />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '5px',
          }}
        >
          <div
            style={{
              fontSize: '16px',
              fontWeight: 500,
              color: '#f5f5f5',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              minWidth: 0,
            }}
          >
            {article.title}
          </div>
          <ModeBadge mode={article.mode} />
        </div>
        <div style={{ display: 'flex', gap: '13px', fontSize: '12px', color: '#666666', flexWrap: 'wrap' }}>
          <span>Analysé : <span style={{ color: '#a0a0a0' }}>{formatDate(article.analysis_date)}</span></span>
          <span>Corrections : <span style={{ color: '#a0a0a0' }}>{article.corrected_links_count} liens</span></span>
          <span>Caractères : <span style={{ color: '#a0a0a0' }}>{formatNumber(article.character_count)}</span></span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
        <button
          onClick={onView}
          style={{
            padding: '7px 12px',
            backgroundColor: '#1a1a1a',
            border: '1px solid #2a2a2a',
            borderRadius: '6px',
            color: '#a0a0a0',
            fontSize: '12.5px',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'background-color 0.15s, color 0.15s, transform 0.1s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#222222'
            e.currentTarget.style.color = '#f5f5f5'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#1a1a1a'
            e.currentTarget.style.color = '#a0a0a0'
          }}
          onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.96)')}
          onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
        >
          Voir
        </button>
        <button
          onClick={onPublish}
          style={{
            padding: '7px 12px',
            backgroundColor: '#10b981',
            border: '1px solid #10b981',
            borderRadius: '6px',
            color: '#ffffff',
            fontSize: '12.5px',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'filter 0.15s, transform 0.1s, box-shadow 0.15s',
            boxShadow: hovered ? '0 3px 10px rgba(16, 185, 129, 0.22)' : 'none',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.filter = 'brightness(1.1)')}
          onMouseLeave={(e) => (e.currentTarget.style.filter = 'brightness(1)')}
          onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.96)')}
          onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
        >
          Publier
        </button>
      </div>
    </div>
  )
}