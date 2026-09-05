import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  RefreshCw,
  ArrowLeft,
  ExternalLink,
  FileText,
  Clock,
  XCircle,
  CheckCircle,
} from 'lucide-react'

interface Article {
  article_title: string
  dead_links_count: number
  corrected_links_count: number
  uncorrected_count: number
  analysis_date: string
  status: string
  issues_count: number
  issues: unknown[]
}

interface ApiResponse {
  success: boolean
  count: number
  articles: Article[]
  error?: string
}

type FilterType = 'published' | 'analyzed'

const isFilterType = (value: string | null): value is FilterType =>
  value === 'published' || value === 'analyzed'

export default function PublishedDeadLinks() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [data, setData] = useState<ApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterType>(() => {
    const fromUrl = searchParams.get('filter')
    return isFilterType(fromUrl) ? fromUrl : 'published'
  })

  const abortRef = useRef<AbortController | null>(null)

  const fetchData = useCallback(async (currentFilter: FilterType) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      setLoading(true)
      setError(null)
      const endpoint =
        currentFilter === 'published'
          ? '/api/published-uncorrected-dead-links'
          : '/api/analyzed-uncorrected-dead-links'

      const response = await fetch(endpoint, { signal: controller.signal })

      if (!response.ok) {
        throw new Error(`Erreur serveur (${response.status})`)
      }

      const result: ApiResponse = await response.json()

      if (controller.signal.aborted) return

      setData(result)
      if (!result.success) {
        setError(result.error || 'Échec de la récupération des données')
      }
    } catch (err) {
      if (controller.signal.aborted || (err as Error)?.name === 'AbortError') return
      setError(err instanceof Error ? err.message : 'Échec de la connexion au serveur')
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    fetchData(filter)
    return () => {
      abortRef.current?.abort()
    }
  }, [filter, fetchData])

  const formatDate = useCallback((dateString: string) => {
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return '—'
    return date.toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }, [])

  const articles = data?.articles ?? []
  const totalDeadLinks = articles.reduce((sum, a) => sum + (a.dead_links_count ?? 0), 0)
  const totalCorrected = articles.reduce((sum, a) => sum + (a.corrected_links_count ?? 0), 0)
  const totalUncorrected = articles.reduce((sum, a) => sum + (a.uncorrected_count ?? 0), 0)

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px',
              color: '#f5f5f5',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            <ArrowLeft style={{ width: '16px', height: '16px' }} />
            Retour
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <AlertTriangle style={{ width: '20px', height: '20px', color: '#ef4444' }} />
            </div>
            <div>
              <h1 style={{ fontSize: '18px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>
                Liens morts publiés
              </h1>
              <p style={{ fontSize: '12px', color: '#a0a0a0', margin: '4px 0 0' }}>
                Articles publiés avec liens morts restants
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={() => fetchData(filter)}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: '#1a1a1a',
            border: '1px solid #2a2a2a',
            borderRadius: '8px',
            color: '#f5f5f5',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            opacity: loading ? 0.5 : 1
          }}
        >
          <RefreshCw style={{ width: '16px', height: '16px', animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          Actualiser
        </button>
      </div>

      {/* Filter */}
      <div style={{
        marginBottom: '24px',
        display: 'flex',
        gap: '8px',
        padding: '8px',
        backgroundColor: '#1a1a1a',
        border: '1px solid #2a2a2a',
        borderRadius: '8px'
      }}>
        <button
          onClick={() => setFilter('published')}
          style={{
            padding: '8px 16px',
            backgroundColor: filter === 'published' ? '#3b82f6' : 'transparent',
            border: 'none',
            borderRadius: '6px',
            color: '#f5f5f5',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: filter === 'published' ? 600 : 400
          }}
        >
          Publiés
        </button>
        <button
          onClick={() => setFilter('analyzed')}
          style={{
            padding: '8px 16px',
            backgroundColor: filter === 'analyzed' ? '#3b82f6' : 'transparent',
            border: 'none',
            borderRadius: '6px',
            color: '#f5f5f5',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: filter === 'analyzed' ? 600 : 400
          }}
        >
          Analysés
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          marginBottom: '20px',
          padding: '16px',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          color: '#ef4444',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <XCircle style={{ width: '18px', height: '18px', flexShrink: 0 }} />
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '60px',
          color: '#a0a0a0'
        }}>
          <RefreshCw style={{ width: '32px', height: '32px', animation: 'spin 1s linear infinite' }} />
        </div>
      )}

      {/* Content */}
      {!loading && data && (
        <>
          {/* Stats */}
          <div style={{
            marginBottom: '24px',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px'
          }}>
            <div style={{
              padding: '16px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>
                Articles concernés
              </div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>
                {data.count}
              </div>
            </div>
            <div style={{
              padding: '16px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>
                Total liens morts
              </div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#ef4444' }}>
                {totalDeadLinks}
              </div>
            </div>
            <div style={{
              padding: '16px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>
                Liens corrigés
              </div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#10b981' }}>
                {totalCorrected}
              </div>
            </div>
            <div style={{
              padding: '16px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>
                Liens non corrigés
              </div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#f59e0b' }}>
                {totalUncorrected}
              </div>
            </div>
          </div>

          {/* Articles List */}
          {articles.length === 0 ? (
            <div style={{
              padding: '60px',
              textAlign: 'center',
              color: '#a0a0a0'
            }}>
              <CheckCircle style={{ width: '48px', height: '48px', margin: '0 auto 16px', color: '#10b981' }} />
              <div style={{ fontSize: '16px' }}>
                Aucun article publié avec des liens morts non corrigés
              </div>
            </div>
          ) : (
            <div style={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #2a2a2a' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: '#a0a0a0', textTransform: 'uppercase' }}>
                      Article
                    </th>
                    <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: 600, color: '#a0a0a0', textTransform: 'uppercase' }}>
                      Liens morts
                    </th>
                    <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: 600, color: '#a0a0a0', textTransform: 'uppercase' }}>
                      Corrigés
                    </th>
                    <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: 600, color: '#a0a0a0', textTransform: 'uppercase' }}>
                      Non corrigés
                    </th>
                    <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: 600, color: '#a0a0a0', textTransform: 'uppercase' }}>
                      Analyse
                    </th>
                    <th style={{ padding: '12px 16px', textAlign: 'center', fontSize: '12px', fontWeight: 600, color: '#a0a0a0', textTransform: 'uppercase' }}>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {articles.map((article, index) => (
                    <tr
                      key={`${article.article_title}-${index}`}
                      style={{
                        borderBottom: index < articles.length - 1 ? '1px solid #2a2a2a' : 'none'
                      }}
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <FileText style={{ width: '16px', height: '16px', color: '#3b82f6' }} />
                          <span style={{ fontSize: '13px', color: '#f5f5f5' }}>
                            {article.article_title}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                        <span style={{ fontSize: '13px', color: '#ef4444', fontWeight: 600 }}>
                          {article.dead_links_count}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                        <span style={{ fontSize: '13px', color: '#10b981', fontWeight: 600 }}>
                          {article.corrected_links_count}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                        <span style={{ fontSize: '13px', color: '#f59e0b', fontWeight: 600 }}>
                          {article.uncorrected_count}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                          <Clock style={{ width: '14px', height: '14px', color: '#a0a0a0' }} />
                          <span style={{ fontSize: '12px', color: '#a0a0a0' }}>
                            {formatDate(article.analysis_date)}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                        <button
                          onClick={() => navigate(
                            filter === 'published'
                              ? `/published-dead-links/${encodeURIComponent(article.article_title)}`
                              : `/analyzed-dead-links/${encodeURIComponent(article.article_title)}`
                          )}
                          style={{
                            padding: '6px 12px',
                            backgroundColor: '#3b82f6',
                            border: 'none',
                            borderRadius: '6px',
                            color: '#ffffff',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: 500,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            margin: '0 auto'
                          }}
                        >
                          <ExternalLink style={{ width: '14px', height: '14px' }} />
                          Voir détails
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}