import { useState, useEffect } from 'react'
import { CheckCircle, XCircle, Clock, FileText, AlertTriangle } from 'lucide-react'
import { publicationApi } from '../api/publication.api'
import { historyApi } from '../api/history.api'

export default function PublicationPending() {
  const [publications, setPublications] = useState<any[]>([])
  const [publishedArticles, setPublishedArticles] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)

  const fetchPendingPublications = async () => {
    setError(null)
    try {
      const response = await publicationApi.getPendingPublications()
      setPublications(response.publications || [])

      // Fetch published articles to check which ones are already published
      const publishedHistory = await historyApi.getPublishedHistory()
      const publishedSet = new Set(publishedHistory.items?.map((item: any) => item.title) || [])
      setPublishedArticles(publishedSet)
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la récupération des publications')
    }
  }

  useEffect(() => {
    fetchPendingPublications()
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'published':
        return <CheckCircle style={{ width: '16px', height: '16px', color: '#10b981' }} />
      case 'failed':
        return <XCircle style={{ width: '16px', height: '16px', color: '#ef4444' }} />
      case 'publishing':
        return <Clock style={{ width: '16px', height: '16px', color: '#3b82f6' }} />
      default:
        return <Clock style={{ width: '16px', height: '16px', color: '#666666' }} />
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'published':
        return 'Publié'
      case 'failed':
        return 'Échoué'
      case 'publishing':
        return 'En cours'
      case 'pending':
        return 'En attente'
      case 'cancelled':
        return 'Annulé'
      default:
        return status
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published':
        return '#10b981'
      case 'failed':
        return '#ef4444'
      case 'publishing':
        return '#3b82f6'
      case 'pending':
        return '#f59e0b'
      default:
        return '#666666'
    }
  }

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>Publications en Attente</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Réviser et approuver les publications en attente</p>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px', backgroundColor: '#161616', borderRadius: '8px', border: '1px solid #2a2a2a' }}>
          <div style={{ textAlign: 'center', color: '#ef4444' }}>{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>Publications en Attente</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Réviser et approuver les publications en attente</p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => fetchPendingPublications()}
        >
          Actualiser
        </button>
      </div>

      {/* Statistics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Total</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>
            {publications.length}
          </div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>En attente</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#f59e0b' }}>
            {publications.filter(p => p.status === 'pending').length}
          </div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>En cours</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#3b82f6' }}>
            {publications.filter(p => p.status === 'publishing').length}
          </div>
        </div>
      </div>

      {/* Publications List */}
      {publications.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px', backgroundColor: '#161616', borderRadius: '8px', border: '1px solid #2a2a2a' }}>
          <div style={{ textAlign: 'center', color: '#666666' }}>
            <FileText style={{ width: '48px', height: '48px', color: '#2a2a2a', margin: '0 auto 16px' }} />
            <div style={{ fontSize: '16px', marginBottom: '8px' }}>Aucune publication en attente</div>
            <div style={{ fontSize: '14px' }}>
              Il n'y a actuellement aucune correction en attente de révision.
            </div>
          </div>
        </div>
      ) : (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {publications.map((publication, index) => (
              <div 
                key={index}
                style={{ 
                  backgroundColor: '#1a1a1a', 
                  border: '1px solid #2a2a2a', 
                  borderRadius: '6px', 
                  padding: '16px' 
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <FileText style={{ width: '20px', height: '20px', color: '#666666' }} />
                    <div>
                      <div style={{ fontSize: '16px', fontWeight: 500, color: '#f5f5f5' }}>
                        {publication.article_title}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666666' }}>
                        {new Date(publication.created_at).toLocaleString('fr-FR')}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {getStatusIcon(publication.status)}
                    <span style={{ fontSize: '14px', color: getStatusColor(publication.status), fontWeight: 500 }}>
                      {getStatusText(publication.status)}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button 
                    className="btn btn-secondary" 
                    style={{ fontSize: '12px', padding: '8px 12px' }}
                    onClick={() => {/* Handle review */}}
                  >
                    Réviser
                  </button>
                  <button 
                    className="btn btn-primary" 
                    style={{ 
                      fontSize: '12px', 
                      padding: '8px 12px',
                      opacity: publishedArticles.has(publication.article_title) ? 0.5 : 1,
                      cursor: publishedArticles.has(publication.article_title) ? 'not-allowed' : 'pointer'
                    }}
                    disabled={publishedArticles.has(publication.article_title)}
                    onClick={() => {/* Handle approve */}}
                  >
                    {publishedArticles.has(publication.article_title) ? 'Déjà publié' : 'Approuver'}
                  </button>
                  <button 
                    className="btn btn-danger" 
                    style={{ fontSize: '12px', padding: '8px 12px' }}
                    onClick={() => {/* Handle reject */}}
                  >
                    Rejeter
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
