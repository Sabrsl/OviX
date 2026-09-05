import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, Search, AlertTriangle, CheckCircle, Clock, RefreshCw, Square } from 'lucide-react'
import { articlesApi } from '../api/articles.api'
import { historyApi } from '../api/history.api'

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

      // Set total count from database
      setTotalCount(countResponse.total)

      // Don't filter articles - show all articles from the database
      // The database status should be the source of truth for all pages
      // Sort by added date, most recent first
      const sortedArticles = articlesResponse.articles.sort((a: any, b: any) => {
        const dateA = new Date(a.added_at || 0).getTime()
        const dateB = new Date(b.added_at || 0).getTime()
        return dateB - dateA // Descending order (most recent first)
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

      // Reload articles to show the newly added one
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

      // Reload articles to show updated list
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
      // Reload articles to show updated list
      await loadArticles()
    } catch (err: any) {
      setError(err.message || 'Erreur lors de la synchronisation')
    } finally {
      setSyncing(false)
    }
  }

  const handleAnalyzeArticle = async (title: string) => {
    // Check if an analysis is already in progress
    if (isAnalyzing) {
      setError('Une analyse est déjà en cours. Attendez qu\'elle se termine.')
      return
    }

    setIsAnalyzing(true)
    setAnalyzingArticle(title)
    setError(null)
    try {
      await articlesApi.analyzeArticle(title, 'regex')
      // Navigate to analysis history to see the article being analyzed with search parameter
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
      case 'low': return '#10b981'
      default: return '#666666'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Clock style={{ width: '16px', height: '16px', color: '#f59e0b' }} />
      case 'analyzing': return <Search style={{ width: '16px', height: '16px', color: '#3b82f6' }} />
      case 'analyzed': return <CheckCircle style={{ width: '16px', height: '16px', color: '#10b981' }} />
      case 'error': return <AlertTriangle style={{ width: '16px', height: '16px', color: '#ef4444' }} />
      default: return <Clock style={{ width: '16px', height: '16px', color: '#666666' }} />
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending': return 'En attente'
      case 'analyzing': return 'En cours'
      case 'analyzed': return 'Analysé'
      case 'error': return 'Erreur'
      default: return status
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>File d'analyse</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Articles en attente d'analyse</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={handleSyncPublished}
            disabled={syncing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '6px',
              color: '#a0a0a0',
              fontSize: '14px',
              fontWeight: 500,
              cursor: syncing ? 'not-allowed' : 'pointer'
            }}
          >
            <RefreshCw style={{ width: '16px', height: '16px', animation: syncing ? 'spin 1s linear infinite' : 'none' }} />
            {syncing ? 'Synchronisation...' : 'Synchroniser'}
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              backgroundColor: '#3b82f6',
              border: 'none',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer'
            }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Ajouter un article
          </button>
        </div>
      </div>

      {/* Search */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
        <div style={{ position: 'relative' }}>
          <Search style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', width: '16px', height: '16px', color: '#666666' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher un article..."
            style={{
              width: '100%',
              padding: '12px 12px 12px 40px',
              backgroundColor: '#0a0a0a',
              border: '1px solid #2a2a2a',
              borderRadius: '6px',
              color: '#f5f5f5',
              fontSize: '14px'
            }}
          />
        </div>
      </div>

      {/* Statistics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Total (base)</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>{totalCount}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Affichés</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#a0a0a0' }}>{filteredArticles.length}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>En attente</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#f59e0b' }}>{articles.filter(a => a.status === 'pending').length}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>En cours</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#3b82f6' }}>{articles.filter(a => a.status === 'analyzing').length}</div>
        </div>
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#666666', marginBottom: '4px' }}>Erreur</div>
          <div style={{ fontSize: '24px', fontWeight: 600, color: '#ef4444' }}>{articles.filter(a => a.status === 'error').length}</div>
        </div>
      </div>

      {/* Analysis Status Banner */}
      {isAnalyzing && (
        <div style={{
          padding: '16px',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderRadius: '8px',
          border: '1px solid #3b82f6',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Search style={{ width: '20px', height: '20px', color: '#3b82f6', animation: 'spin 1s linear infinite' }} />
            <div>
              <div style={{ fontSize: '14px', fontWeight: 500, color: '#f5f5f5' }}>Analyse en cours</div>
              <div style={{ fontSize: '12px', color: '#a0a0a0' }}>
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
          fontSize: '14px',
          padding: '12px',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertTriangle style={{ width: '16px', height: '16px' }} />
          {error}
        </div>
      )}

      {/* Articles List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '48px', color: '#a0a0a0' }}>
          Chargement...
        </div>
      ) : filteredArticles.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px', color: '#a0a0a0' }}>
          <div style={{ marginBottom: '16px' }}>Aucun article dans la file d'attente</div>
          <button
            onClick={() => setShowAddModal(true)}
            style={{
              padding: '10px 16px',
              backgroundColor: '#3b82f6',
              border: 'none',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            Ajouter le premier article
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredArticles.map((article) => (
            <div
              key={article.id}
              style={{
                padding: '16px',
                backgroundColor: '#161616',
                border: '1px solid #2a2a2a',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                transition: 'all 0.2s'
              }}
            >
              <div style={{ marginRight: '8px' }}>
                {getStatusIcon(article.status)}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '16px', fontWeight: 500, color: '#f5f5f5', marginBottom: '4px' }}>
                  {article.title}
                </div>
                <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: '#666666' }}>
                  <span>Source: {article.source}</span>
                  <span>Détails: {article.source_details}</span>
                  <span>Ajouté: {new Date(article.added_at).toLocaleString('fr-FR')}</span>
                </div>
              </div>
              <div style={{
                padding: '4px 8px',
                backgroundColor: `${getPriorityColor(article.priority)}20`,
                borderRadius: '4px',
                fontSize: '12px',
                color: getPriorityColor(article.priority),
                fontWeight: 500,
                border: `1px solid ${getPriorityColor(article.priority)}40`
              }}>
                {article.priority === 'high' ? 'Haute' : article.priority === 'medium' ? 'Moyenne' : 'Basse'}
              </div>
              <div style={{
                padding: '4px 8px',
                backgroundColor: '#1a1a1a',
                borderRadius: '4px',
                fontSize: '12px',
                color: '#a0a0a0'
              }}>
                {getStatusText(article.status)}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                {article.status === 'pending' && (
                  <button
                    onClick={() => handleAnalyzeArticle(article.title)}
                    disabled={isAnalyzing}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: isAnalyzing ? '#666666' : '#10b981',
                      border: 'none',
                      borderRadius: '4px',
                      color: '#ffffff',
                      fontSize: '12px',
                      cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                      opacity: isAnalyzing ? 0.5 : 1
                    }}
                  >
                    {isAnalyzing ? 'Analyse en cours...' : 'Analyser'}
                  </button>
                )}
                {article.status === 'error' && (
                  <button
                    onClick={() => handleAnalyzeArticle(article.title)}
                    disabled={isAnalyzing}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: isAnalyzing ? '#666666' : '#f59e0b',
                      border: 'none',
                      borderRadius: '4px',
                      color: '#ffffff',
                      fontSize: '12px',
                      cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                      opacity: isAnalyzing ? 0.5 : 1
                    }}
                  >
                    {isAnalyzing ? 'Analyse en cours...' : 'Réessayer'}
                  </button>
                )}
                <button
                  onClick={() => handleDeleteArticle(article.id)}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: '#ef4444',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#ffffff',
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                >
                  <Trash2 style={{ width: '14px', height: '14px' }} />
                </button>
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
            zIndex: 1000
          }}
          onClick={() => setShowAddModal(false)}
        >
          <div
            style={{
              backgroundColor: '#161616',
              border: '1px solid #2a2a2a',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '500px',
              width: '90%'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#f5f5f5', marginBottom: '16px' }}>
              Ajouter un article à analyser
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Titre de l'article *
                </label>
                <input
                  type="text"
                  value={newArticleTitle}
                  onChange={(e) => setNewArticleTitle(e.target.value)}
                  placeholder="Ex: Paris"
                  style={{
                    width: '100%',
                    padding: '12px',
                    backgroundColor: '#0a0a0a',
                    border: '1px solid #2a2a2a',
                    borderRadius: '6px',
                    color: '#f5f5f5',
                    fontSize: '14px'
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Source
                </label>
                <select
                  value={newArticleSource}
                  onChange={(e) => setNewArticleSource(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '12px',
                    backgroundColor: '#0a0a0a',
                    border: '1px solid #2a2a2a',
                    borderRadius: '6px',
                    color: '#f5f5f5',
                    fontSize: '14px'
                  }}
                >
                  <option value="manual">Manuel</option>
                  <option value="category">Catégorie</option>
                  <option value="petscan">PetScan</option>
                  <option value="file">Fichier</option>
                  <option value="user-contribs">Contributions utilisateur</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Détails de la source
                </label>
                <input
                  type="text"
                  value={newArticleSourceDetails}
                  onChange={(e) => setNewArticleSourceDetails(e.target.value)}
                  placeholder="Ex: Category:Article à wikifier"
                  style={{
                    width: '100%',
                    padding: '12px',
                    backgroundColor: '#0a0a0a',
                    border: '1px solid #2a2a2a',
                    borderRadius: '6px',
                    color: '#f5f5f5',
                    fontSize: '14px'
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Priorité
                </label>
                <select
                  value={newArticlePriority}
                  onChange={(e) => setNewArticlePriority(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '12px',
                    backgroundColor: '#0a0a0a',
                    border: '1px solid #2a2a2a',
                    borderRadius: '6px',
                    color: '#f5f5f5',
                    fontSize: '14px'
                  }}
                >
                  <option value="low">Basse</option>
                  <option value="medium">Moyenne</option>
                  <option value="high">Haute</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '12px', marginTop: '24px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowAddModal(false)}
                style={{
                  padding: '10px 16px',
                  backgroundColor: '#1a1a1a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '6px',
                  color: '#a0a0a0',
                  fontSize: '14px',
                  cursor: 'pointer'
                }}
              >
                Annuler
              </button>
              <button
                onClick={handleAddArticle}
                disabled={addingArticle || !newArticleTitle.trim()}
                style={{
                  padding: '10px 16px',
                  backgroundColor: '#3b82f6',
                  border: 'none',
                  borderRadius: '6px',
                  color: '#ffffff',
                  fontSize: '14px',
                  cursor: addingArticle || !newArticleTitle.trim() ? 'not-allowed' : 'pointer'
                }}
              >
                {addingArticle ? 'Ajout...' : 'Ajouter'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}