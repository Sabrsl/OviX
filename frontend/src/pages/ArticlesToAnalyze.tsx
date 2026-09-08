import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, Search, AlertTriangle, CheckCircle, Clock, RefreshCw } from 'lucide-react'
import { articlesApi } from '../api/articles.api'
import { historyApi } from '../api/history.api'
import Button from '../components/Button'

interface ArticleToAnalyze {
  id: string
  title: string
  page_id?: number
  revision_id?: number
  source: 'category' | 'manual' | 'petscan' | 'file' | 'user-contribs'
  source_details: string
  priority: 'low' | 'medium' | 'high'
  added_at: string
  status: 'pending' | 'analyzing' | 'analyzed' | 'error'
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  backgroundColor: '#0a0a0a',
  border: '1px solid #2a2a2a',
  borderRadius: '6px',
  color: '#f5f5f5',
  fontSize: '13px'
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '12px',
  color: '#a0a0a0',
  marginBottom: '6px'
}

export default function ArticlesToAnalyze() {
  const navigate = useNavigate()
  const [articles, setArticles] = useState<ArticleToAnalyze[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newArticleTitle, setNewArticleTitle] = useState('')
  const [newArticleSource, setNewArticleSource] = useState<'category' | 'manual' | 'petscan' | 'file' | 'user-contribs'>('manual')
  const [newArticleSourceDetails, setNewArticleSourceDetails] = useState('')
  const [newArticlePriority, setNewArticlePriority] = useState<'low' | 'medium' | 'high'>('medium')
  const [addingArticle, setAddingArticle] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [analyzingArticle, setAnalyzingArticle] = useState<string | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const filteredArticles = articles.filter(article =>
    article.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  useEffect(() => {
    loadArticles(true)
  }, [])

  const loadArticles = async (isInitial = false) => {
    if (isInitial) {
      setLoading(true)
    }
    setError(null)
    try {
      const [articlesResponse, publishedResponse, analyzedResponse, countResponse] = await Promise.all([
        articlesApi.getArticlesToAnalyze(),
        historyApi.getPublishedHistory(),
        articlesApi.getArticleHistory(1000),
        articlesApi.getArticlesToAnalyzeCount()
      ])

      setTotalCount(countResponse.total)

      const sortedArticles = articlesResponse.articles.sort((a: any, b: any) => {
        const dateA = new Date(a.added_at || 0).getTime()
        const dateB = new Date(b.added_at || 0).getTime()
        return dateB - dateA
      })

      setArticles(sortedArticles)
    } catch (err: any) {
      setError(err.message || 'Erreur lors du chargement des articles')
    } finally {
      if (isInitial) {
        setLoading(false)
      }
    }
  }

  const handleAddArticle = async () => {
    if (!newArticleTitle.trim()) {
      setError('Veuillez entrer un titre d\'article')
      return
    }

    setAddingArticle(true)
    setError(null)

    try {
      await articlesApi.addArticlesToAnalyze({
        articles: [{
          title: newArticleTitle.trim(),
          source: newArticleSource,
          source_details: newArticleSourceDetails,
          priority: newArticlePriority
        }]
      })

      setShowAddModal(false)
      setNewArticleTitle('')
      setNewArticleSourceDetails('')
      setNewArticlePriority('medium')

      await loadArticles()
    } catch (err: any) {
      setError(err.message || 'Erreur lors de l\'ajout de l\'article')
    } finally {
      setAddingArticle(false)
    }
  }

  const handleDeleteArticle = async (id: string) => {
    if (!window.confirm('Supprimer cet article de la file d\'attente ?')) {
      return
    }

    try {
      const response = await fetch(`/api/articles/to-analyze/${id}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Erreur lors de la suppression')
      }

      await loadArticles()
    } catch (err: any) {
      setError(err.message || 'Erreur lors de la suppression de l\'article')
    }
  }

  const handleSyncPublished = async () => {
    setSyncing(true)
    setError(null)
    try {
      const response = await articlesApi.syncPublishedArticles()
      alert(response.message)
      await loadArticles()
    } catch (err: any) {
      setError(err.message || 'Erreur lors de la synchronisation')
    } finally {
      setSyncing(false)
    }
  }

  const handleAnalyzeArticle = async (title: string) => {
    if (isAnalyzing) {
      setError('Une analyse est déjà en cours. Attendez qu\'elle se termine.')
      return
    }

    setIsAnalyzing(true)
    setAnalyzingArticle(title)
    setError(null)
    try {
      await articlesApi.analyzeArticle(title, 'regex')
      navigate(`/analysis/history?search=${encodeURIComponent(title)}`)
    } catch (err: any) {
      setError(err.message || 'Erreur lors de l\'analyse')
      setAnalyzingArticle(null)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high': return '#ef4444'
      case 'medium': return '#f59e0b'
      case 'low': return '#059669'
      default: return '#666666'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Clock style={{ width: '14px', height: '14px', color: '#f59e0b' }} />
      case 'analyzing': return <Search style={{ width: '14px', height: '14px', color: '#e0e0e0' }} />
      case 'analyzed': return <CheckCircle style={{ width: '14px', height: '14px', color: '#059669' }} />
      case 'error': return <AlertTriangle style={{ width: '14px', height: '14px', color: '#ef4444' }} />
      default: return <Clock style={{ width: '14px', height: '14px', color: '#666666' }} />
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        animation: 'fadeIn 0.2s ease-in-out',
        maxWidth: '860px',
        margin: '0 auto',
        padding: '0 16px'
      }}
    >
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#f5f5f5' }}>File d'analyse</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px', fontSize: '13px' }}>Articles en attente d'analyse</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button variant="neutral" onClick={handleSyncPublished} disabled={syncing} style={{ fontSize: '13px' }}>
            <RefreshCw style={{ width: '14px', height: '14px', animation: syncing ? 'spin 1s linear infinite' : 'none' }} />
            {syncing ? 'Synchronisation...' : 'Synchroniser'}
          </Button>
          <Button variant="primary" onClick={() => setShowAddModal(true)} style={{ fontSize: '13px' }}>
            <Plus style={{ width: '14px', height: '14px' }} />
            Ajouter un article
          </Button>
        </div>
      </div>

      {/* Search */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '14px' }}>
        <div style={{ position: 'relative' }}>
          <Search style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', width: '14px', height: '14px', color: '#666666' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher un article..."
            style={{ ...inputStyle, padding: '10px 12px 10px 36px' }}
          />
        </div>
      </div>

      {/* Statistics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px' }}>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '14px' }}>
          <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>Total (base)</div>
          <div style={{ fontSize: '19px', fontWeight: 600, color: '#f5f5f5' }}>{totalCount}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '14px' }}>
          <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>Affichés</div>
          <div style={{ fontSize: '19px', fontWeight: 600, color: '#a0a0a0' }}>{filteredArticles.length}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '14px' }}>
          <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>En attente</div>
          <div style={{ fontSize: '19px', fontWeight: 600, color: '#f59e0b' }}>{articles.filter(a => a.status === 'pending').length}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '14px' }}>
          <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>En cours</div>
          <div style={{ fontSize: '19px', fontWeight: 600, color: '#e0e0e0' }}>{articles.filter(a => a.status === 'analyzing').length}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '14px' }}>
          <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>Erreur</div>
          <div style={{ fontSize: '19px', fontWeight: 600, color: '#ef4444' }}>{articles.filter(a => a.status === 'error').length}</div>
        </div>
      </div>

      {/* Analysis Status Banner */}
      {isAnalyzing && (
        <div style={{
          padding: '14px',
          backgroundColor: '#1a1a1a',
          borderRadius: '8px',
          border: '1px solid #3a3a3a',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Search style={{ width: '18px', height: '18px', color: '#e0e0e0', animation: 'spin 1s linear infinite' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 500, color: '#f5f5f5' }}>Analyse en cours</div>
              <div style={{ fontSize: '11px', color: '#a0a0a0' }}>
                {analyzingArticle ? `Article : ${analyzingArticle}` : 'Traitement...'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          color: '#ef4444',
          fontSize: '13px',
          padding: '10px 12px',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertTriangle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          {error}
        </div>
      )}

      {/* Articles List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#a0a0a0', fontSize: '13px' }}>
          Chargement...
        </div>
      ) : filteredArticles.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#a0a0a0' }}>
          <div style={{ marginBottom: '16px', fontSize: '13px' }}>Aucun article dans la file d'attente</div>
          <Button variant="primary" onClick={() => setShowAddModal(true)} style={{ fontSize: '13px' }}>
            Ajouter le premier article
          </Button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filteredArticles.map((article) => (
            <div
              key={article.id}
              style={{
                padding: '14px',
                backgroundColor: '#161616',
                border: '1px solid #2a2a2a',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                flexWrap: 'wrap',
                transition: 'all 0.2s'
              }}
            >
              <div style={{ marginRight: '4px', flexShrink: 0 }}>
                {getStatusIcon(article.status)}
              </div>
              <div style={{ flex: 1, minWidth: '160px' }}>
                <div style={{ fontSize: '14px', fontWeight: 500, color: '#f5f5f5', marginBottom: '4px' }}>
                  {article.title}
                </div>
                <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: '#666666', flexWrap: 'wrap' }}>
                  <span>Source: {article.source}</span>
                  <span>Détails: {article.source_details}</span>
                  <span>Ajouté: {new Date(article.added_at).toLocaleString('fr-FR')}</span>
                </div>
              </div>
              <div style={{
                padding: '1px 6px',
                backgroundColor: `${getPriorityColor(article.priority)}12`,
                borderRadius: '9999px',
                fontSize: '9px',
                color: getPriorityColor(article.priority),
                fontWeight: 500,
                border: `1px solid ${getPriorityColor(article.priority)}25`,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px',
                flexShrink: 0
              }}>
                <span style={{
                  width: '3px',
                  height: '3px',
                  borderRadius: '50%',
                  backgroundColor: getPriorityColor(article.priority)
                }} />
                {article.priority === 'high' ? 'Haute' : article.priority === 'medium' ? 'Moyenne' : 'Basse'}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                {article.status === 'pending' && (
                  <Button variant="neutral" onClick={() => handleAnalyzeArticle(article.title)} disabled={isAnalyzing} style={{ fontSize: '12px' }}>
                    {isAnalyzing ? 'Analyse en cours...' : 'Analyser'}
                  </Button>
                )}
                {article.status === 'error' && (
                  <Button
                    variant="neutral"
                    onClick={() => handleAnalyzeArticle(article.title)}
                    disabled={isAnalyzing}
                    style={{ color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.4)', fontSize: '12px' }}
                  >
                    {isAnalyzing ? 'Analyse en cours...' : 'Réessayer'}
                  </Button>
                )}
                <Button variant="danger" onClick={() => handleDeleteArticle(article.id)} style={{ fontSize: '12px' }}>
                  <Trash2 style={{ width: '13px', height: '13px' }} />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Article Modal */}
      {showAddModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px'
          }}
          onClick={() => setShowAddModal(false)}
        >
          <div
            style={{
              backgroundColor: '#161616',
              border: '1px solid #2a2a2a',
              borderRadius: '12px',
              padding: '22px',
              maxWidth: '460px',
              width: '100%'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f5f5f5', marginBottom: '16px' }}>
              Ajouter un article à analyser
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={labelStyle}>Titre de l'article *</label>
                <input
                  type="text"
                  value={newArticleTitle}
                  onChange={(e) => setNewArticleTitle(e.target.value)}
                  placeholder="Ex: Paris"
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Source</label>
                <select
                  value={newArticleSource}
                  onChange={(e) => setNewArticleSource(e.target.value as any)}
                  style={inputStyle}
                >
                  <option value="manual">Manuel</option>
                  <option value="category">Catégorie</option>
                  <option value="petscan">PetScan</option>
                  <option value="file">Fichier</option>
                  <option value="user-contribs">Contributions utilisateur</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Détails de la source</label>
                <input
                  type="text"
                  value={newArticleSourceDetails}
                  onChange={(e) => setNewArticleSourceDetails(e.target.value)}
                  placeholder="Ex: Category:Article à wikifier"
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Priorité</label>
                <select
                  value={newArticlePriority}
                  onChange={(e) => setNewArticlePriority(e.target.value as any)}
                  style={inputStyle}
                >
                  <option value="low">Basse</option>
                  <option value="medium">Moyenne</option>
                  <option value="high">Haute</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', marginTop: '20px', justifyContent: 'flex-end' }}>
              <Button variant="neutral" onClick={() => setShowAddModal(false)} style={{ fontSize: '13px' }}>
                Annuler
              </Button>
              <Button variant="primary" onClick={handleAddArticle} disabled={addingArticle || !newArticleTitle.trim()} style={{ fontSize: '13px' }}>
                {addingArticle ? 'Ajout...' : 'Ajouter'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}