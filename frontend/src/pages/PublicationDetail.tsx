import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle, Clock, ExternalLink, FileText, Calendar, Hash, User, Globe, Edit, AlertTriangle, Search } from 'lucide-react'
import { historyApi } from '../api/history.api'
import Button from '../components/Button'

interface PublishedArticle {
  title: string
  published_at: string
  category: string
  mode: string
  summary: string
  revision_id?: number | null
  dry_run?: boolean
  changes_count?: number
  // Additional fields from database
  total_links?: number
  dead_links_count?: number
  corrected_links_count?: number
  character_count?: number
  job_id?: string
  page_id?: number
}

export default function PublicationDetail() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const articleTitle = searchParams.get('title')

  const [article, setArticle] = useState<PublishedArticle | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false)

  useEffect(() => {
    if (!articleTitle) {
      setError("Aucun titre d'article fourni")
      setLoading(false)
      return
    }
    fetchArticleDetails(true)
  }, [articleTitle])

  const fetchArticleDetails = async (isInitial = false) => {
    try {
      if (isInitial) {
        setLoading(true)
      }
      const response = await historyApi.getPublishedHistory(100, 0)
      const foundArticle = response.items?.find((item: any) => item.title === articleTitle)

      if (foundArticle) {
        setArticle({
          title: foundArticle.title,
          published_at: foundArticle.published_at,
          category: foundArticle.category || 'unknown',
          mode: foundArticle.mode,
          summary: foundArticle.summary,
          revision_id: foundArticle.revision_id,
          dry_run: foundArticle.mode === 'dry_run',
          changes_count: foundArticle.changes_count || 0,
          total_links: foundArticle.total_links,
          dead_links_count: foundArticle.dead_links_count,
          corrected_links_count: foundArticle.corrected_links_count,
          character_count: foundArticle.character_count,
          job_id: foundArticle.job_id,
          page_id: foundArticle.page_id
        })
      } else {
        setError("Article non trouvé dans l'historique de publication")
      }
    } catch (err: any) {
      setError(err.message || "Erreur lors de la récupération des détails")
    } finally {
      if (isInitial) {
        setLoading(false)
      }
    }
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A'
    try {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return 'Date invalide'
      return date.toLocaleString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return 'Date invalide'
    }
  }

  const getWikipediaUrl = (title: string) => {
    return `https://fr.wikipedia.org/wiki/${encodeURIComponent(title)}`
  }

  const getRevisionUrl = (title: string, revisionId?: number | null) => {
    if (!revisionId) return undefined
    return `https://fr.wikipedia.org/w/index.php?title=${encodeURIComponent(title)}&oldid=${revisionId}`
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', maxWidth: '860px', margin: '0 auto', padding: '0 16px' }}>
        <div style={{ textAlign: 'center', color: '#666666' }}>
          <Clock className="animate-spin" style={{ width: '40px', height: '40px', margin: '0 auto 16px' }} />
          <div>Chargement...</div>
        </div>
      </div>
    )
  }

  if (error || !article) {
    return (
      <div style={{ padding: '0 16px', maxWidth: '860px', margin: '0 auto' }}>
        <Button
          variant="neutral"
          onClick={() => navigate('/publication/history')}
          style={{ backgroundColor: 'transparent', border: 'none', color: '#a0a0a0', marginBottom: '24px' }}
        >
          <ArrowLeft style={{ width: '16px', height: '16px' }} />
          Retour à l'historique
        </Button>
        <div style={{
          backgroundColor: '#161616',
          border: '1px solid #2a2a2a',
          borderRadius: '8px',
          padding: '48px',
          textAlign: 'center',
          color: '#ef4444'
        }}>
          <AlertTriangle style={{ width: '48px', height: '48px', margin: '0 auto 16px' }} />
          <div style={{ fontSize: '18px', marginBottom: '8px' }}>{error || 'Article non trouvé'}</div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '0 16px', maxWidth: '860px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <Button
          variant="neutral"
          onClick={() => navigate('/publication/history')}
          style={{ backgroundColor: 'transparent', border: 'none', color: '#a0a0a0', marginBottom: '16px' }}
        >
          <ArrowLeft style={{ width: '16px', height: '16px' }} />
          Retour à l'historique
        </Button>
        
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
          <div style={{
            backgroundColor: '#1a1a1a',
            border: '1px solid #2a2a2a',
            borderRadius: '8px',
            padding: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {article.dry_run ? (
              <Clock style={{ width: '32px', height: '32px', color: '#f59e0b' }} />
            ) : (
              <CheckCircle style={{ width: '32px', height: '32px', color: '#10b981' }} />
            )}
          </div>
          
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: '28px', fontWeight: 600, color: '#f5f5f5', margin: '0 0 8px 0' }}>
              {article.title}
            </h1>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', fontSize: '14px', color: '#a0a0a0' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Calendar style={{ width: '14px', height: '14px' }} />
                {formatDate(article.published_at)}
              </span>
              <span>•</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                {article.dry_run ? 'Test (dry-run)' : 'Publié'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Information Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
        {/* Article Info */}
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <FileText style={{ width: '20px', height: '20px', color: '#3b82f6' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>Informations</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Titre</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0', wordBreak: 'break-word' }}>{article.title}</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Catégorie</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>{article.category}</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Mode</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>{article.mode === 'IA' ? 'IA' : article.mode === 'regex' ? 'Regex' : article.mode}</div>
            </div>
          </div>
        </div>

        {/* Publication Info */}
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <CheckCircle style={{ width: '20px', height: '20px', color: '#10b981' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>Publication</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Date de publication</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>{formatDate(article.published_at)}</div>
            </div>
            {article.revision_id !== null && article.revision_id !== undefined && (
              <div>
                <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>ID de révision</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '14px', color: '#e0e0e0' }}>{article.revision_id}</span>
                  {getRevisionUrl(article.title, article.revision_id) && (
                    <a
                      href={getRevisionUrl(article.title, article.revision_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: '#e0e0e0', textDecoration: 'none' }}
                    >
                      <ExternalLink style={{ width: '14px', height: '14px' }} />
                    </a>
                  )}
                </div>
              </div>
            )}
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Statut</div>
              <div style={{ fontSize: '14px', color: article.dry_run ? '#f59e0b' : '#10b981' }}>
                {article.dry_run ? 'Test (dry-run)' : 'Publié'}
              </div>
            </div>
          </div>
        </div>

        {/* Summary */}
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Edit style={{ width: '20px', height: '20px', color: '#8b5cf6' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>Résumé</h3>
          </div>
          <div style={{ fontSize: '14px', color: '#e0e0e0', lineHeight: '1.6', maxHeight: '150px', overflowY: 'auto' }}>
            {article.summary || 'Aucun résumé disponible'}
          </div>
        </div>
      </div>

      {/* Modifications Summary */}
      {(article.total_links !== undefined || article.dead_links_count !== undefined || article.corrected_links_count !== undefined) && (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Edit style={{ width: '20px', height: '20px', color: '#3b82f6' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>Modifications effectuées</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div>
              <Button
                variant="neutral"
                onClick={() => navigate(`/article/detail?title=${encodeURIComponent(article.title)}`)}
                style={{ justifyContent: 'center', width: '100%', padding: '10px 16px' }}
              >
                <Search style={{ width: '16px', height: '16px' }} />
                Voir l'analyse
              </Button>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Problèmes détectés</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#ef4444' }}>
                {article.dead_links_count ?? 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Liens corrigés</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#10b981' }}>
                {article.corrected_links_count ?? 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f5f5f5', marginBottom: '16px' }}>Actions rapides</h3>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <a
            href={getWikipediaUrl(article.title)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ textDecoration: 'none' }}
          >
            <Button variant="neutral">
              <Globe style={{ width: '16px', height: '16px' }} />
              Article Wikipédia
            </Button>
          </a>

          {article.revision_id !== null && article.revision_id !== undefined && getRevisionUrl(article.title, article.revision_id) && (
            <a
              href={getRevisionUrl(article.title, article.revision_id)}
              target="_blank"
              rel="noopener noreferrer"
              style={{ textDecoration: 'none' }}
            >
              <Button variant="neutral">
                <Hash style={{ width: '16px', height: '16px' }} />
                Version publiée
              </Button>
            </a>
          )}

          <Button
            variant="neutral"
            onClick={() => {
              const text = `[[${article.title}]] - ${article.summary}`
              navigator.clipboard.writeText(text)
            }}
          >
            <Edit style={{ width: '16px', height: '16px' }} />
            Copier lien wiki
          </Button>
        </div>
      </div>

      {/* Technical Details */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
        <Button
          variant="neutral"
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          style={{
            backgroundColor: 'transparent',
            border: 'none',
            color: '#a0a0a0',
            fontSize: '16px',
            fontWeight: 600,
            padding: 0,
            marginBottom: showTechnicalDetails ? '16px' : '0'
          }}
        >
          <Hash style={{ width: '20px', height: '20px' }} />
          Détails techniques
          <span style={{ marginLeft: '8px', fontSize: '12px' }}>
            {showTechnicalDetails ? '▼' : '▶'}
          </span>
        </Button>

        {showTechnicalDetails && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Page ID</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>
                {article.page_id ?? 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Revision ID</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>
                {article.revision_id ?? 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Job ID</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0', wordBreak: 'break-all' }}>
                {article.job_id ?? 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Mode</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>
                {article.mode}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Caractères</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>
                {article.character_count ? article.character_count.toLocaleString() : 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Modifications</div>
              <div style={{ fontSize: '14px', color: '#e0e0e0' }}>
                {article.corrected_links_count ?? 'N/A'}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}