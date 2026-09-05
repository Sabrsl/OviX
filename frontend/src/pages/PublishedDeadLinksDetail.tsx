import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  RefreshCw,
  ArrowLeft,
  ExternalLink,
  FileText,
  Clock,
  XCircle,
  CheckCircle,
  Link2,
  ShieldAlert,
} from 'lucide-react'

interface DeadLink {
  url: string
  status: string
  error_message?: string
  reference?: string
  line_number?: number
}

interface ArticleDetail {
  article_title: string
  dead_links_count: number
  corrected_links_count: number
  uncorrected_count: number
  analysis_date: string
  status: string
  issues_count: number
  issues: any[]
  dead_links?: DeadLink[]
}

interface ApiResponse {
  success: boolean
  article: ArticleDetail
  error?: string
}

export default function PublishedDeadLinksDetail() {
  const navigate = useNavigate()
  const { articleTitle } = useParams<{ articleTitle: string }>()
  const [data, setData] = useState<ArticleDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch(`/api/article/${encodeURIComponent(articleTitle || '')}/dead-links`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const result: ApiResponse = await response.json()
      if (result.success) {
        setData(result.article)
      } else {
        setError(result.error || 'Failed to fetch data')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to connect to server'
      setError(errorMessage)
      console.error('Error fetching article details:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (articleTitle) {
      fetchData()
    }
  }, [articleTitle])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getWikipediaUrl = (title: string) => {
    return `https://fr.wikipedia.org/wiki/${encodeURIComponent(title)}`
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => navigate('/published-dead-links')}
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
                {data?.article_title || 'Détails des liens morts'}
              </h1>
              <p style={{ fontSize: '12px', color: '#a0a0a0', margin: '4px 0 0' }}>
                Liens morts non corrigés
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={fetchData}
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
          <RefreshCw className="animate-spin" style={{ width: '32px', height: '32px' }} />
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
                Total liens morts
              </div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#ef4444' }}>
                {data.dead_links_count}
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
                {data.corrected_links_count}
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
                {data.uncorrected_count}
              </div>
            </div>
            <div style={{
              padding: '16px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px'
            }}>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>
                Dernière analyse
              </div>
              <div style={{ fontSize: '14px', fontWeight: 500, color: '#f5f5f5' }}>
                {formatDate(data.analysis_date)}
              </div>
            </div>
          </div>

          {/* Wikipedia Link */}
          <div style={{
            marginBottom: '24px',
            padding: '16px',
            backgroundColor: '#1a1a1a',
            border: '1px solid #2a2a2a',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <FileText style={{ width: '20px', height: '20px', color: '#3b82f6' }} />
              <div>
                <div style={{ fontSize: '13px', fontWeight: 500, color: '#f5f5f5' }}>
                  Article Wikipédia
                </div>
                <div style={{ fontSize: '12px', color: '#a0a0a0' }}>
                  {data.article_title}
                </div>
              </div>
            </div>
            <a
              href={getWikipediaUrl(data.article_title)}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 12px',
                backgroundColor: '#3b82f6',
                border: 'none',
                borderRadius: '6px',
                color: '#ffffff',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 500,
                textDecoration: 'none'
              }}
            >
              <ExternalLink style={{ width: '14px', height: '14px' }} />
              Voir sur Wikipédia
            </a>
          </div>

          {/* Dead Links List */}
          {data.dead_links && data.dead_links.length > 0 ? (
            <div style={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <div style={{
                padding: '16px',
                borderBottom: '1px solid #2a2a2a',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <ShieldAlert style={{ width: '18px', height: '18px', color: '#ef4444' }} />
                <div style={{ fontSize: '14px', fontWeight: 600, color: '#f5f5f5' }}>
                  Liens morts détectés ({data.dead_links.length})
                </div>
              </div>
              <div style={{ padding: '0' }}>
                {data.dead_links.map((link, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '16px',
                      borderBottom: index < data.dead_links!.length - 1 ? '1px solid #2a2a2a' : 'none',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <Link2 style={{ width: '16px', height: '16px', color: '#ef4444', flexShrink: 0, marginTop: '2px' }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: '13px',
                          color: '#f5f5f5',
                          wordBreak: 'break-all',
                          marginBottom: '4px'
                        }}>
                          {link.url || 'URL non disponible'}
                        </div>
                        {link.error_message && (
                          <div style={{
                            fontSize: '12px',
                            color: '#ef4444',
                            marginTop: '4px',
                            padding: '8px',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            borderRadius: '4px'
                          }}>
                            {link.error_message}
                          </div>
                        )}
                        {(link.reference || link.line_number) && (
                          <div style={{
                            fontSize: '11px',
                            color: '#a0a0a0',
                            marginTop: '8px',
                            display: 'flex',
                            gap: '12px'
                          }}>
                            {link.reference && (
                              <span>Référence: {link.reference}</span>
                            )}
                            {link.line_number && (
                              <span>Ligne: {link.line_number}</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{
              padding: '60px',
              textAlign: 'center',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '8px',
              color: '#a0a0a0'
            }}>
              <CheckCircle style={{ width: '48px', height: '48px', margin: '0 auto 16px', color: '#10b981' }} />
              <div style={{ fontSize: '16px' }}>
                Aucun lien mort détecté
              </div>
              {data.issues_count > 0 && (
                <div style={{ fontSize: '13px', marginTop: '8px', color: '#666666' }}>
                  {data.issues_count} issues trouvées mais aucun lien mort extrait
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
