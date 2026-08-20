import { useState, useEffect } from 'react'
import { Search, FileText, AlertTriangle, CheckCircle, User, FileText as FileIcon, Scan } from 'lucide-react'
import { analysisApi } from '../api/analysis.api'
import { articlesApi } from '../api/articles.api'
import { useNavigate } from 'react-router-dom'

export default function AnalysisNew() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'category' | 'manual' | 'petscan' | 'file' | 'user-contribs' | 'article'>('category')
  const [articleTitle, setArticleTitle] = useState('')
  const [category, setCategory] = useState('Article à wikifier/Liste complète')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Predefined categories
  const [predefinedCategories, setPredefinedCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('custom')
  const [loadingCategories, setLoadingCategories] = useState(false)

  // Category options
  const [maxArticles, setMaxArticles] = useState(100)
  const [recursive, setRecursive] = useState(false)
  const [excludePublished, setExcludePublished] = useState(true)
  const [includeAnalyzed, setIncludeAnalyzed] = useState(false)

  // Article retrieval
  const [retrievingArticles, setRetrievingArticles] = useState(false)
  const [articles, setArticles] = useState<any[]>([])
  const [articlesRetrieved, setArticlesRetrieved] = useState(false)
  const [selectedArticles, setSelectedArticles] = useState<Set<string>>(new Set())
  const [analyzingArticle, setAnalyzingArticle] = useState<string | null>(null)

  // Load articles from localStorage on mount
  useEffect(() => {
    const savedArticles = localStorage.getItem('retrievedArticles')
    const savedSelected = localStorage.getItem('selectedArticles')
    const savedRetrieved = localStorage.getItem('articlesRetrieved')

    if (savedArticles) {
      try {
        setArticles(JSON.parse(savedArticles))
      } catch (e) {
        console.error('Failed to parse saved articles:', e)
      }
    }

    if (savedSelected) {
      try {
        setSelectedArticles(new Set(JSON.parse(savedSelected)))
      } catch (e) {
        console.error('Failed to parse saved selected articles:', e)
      }
    }

    if (savedRetrieved === 'true') {
      setArticlesRetrieved(true)
    }
  }, [])

  // Save articles to localStorage when they change
  useEffect(() => {
    if (articles.length > 0) {
      localStorage.setItem('retrievedArticles', JSON.stringify(articles))
    } else {
      localStorage.removeItem('retrievedArticles')
    }
  }, [articles])

  useEffect(() => {
    localStorage.setItem('selectedArticles', JSON.stringify(Array.from(selectedArticles)))
  }, [selectedArticles])

  useEffect(() => {
    localStorage.setItem('articlesRetrieved', String(articlesRetrieved))
  }, [articlesRetrieved])

  // Manual retrieval
  const [manualTitles, setManualTitles] = useState('')

  // PetScan retrieval
  const [petScanId, setPetScanId] = useState('')

  // File retrieval
  const [filePath, setFilePath] = useState('')

  // User contributions retrieval
  const [username, setUsername] = useState('')

  // Analysis mode
  const [analysisMode, setAnalysisMode] = useState<'regex' | 'ia'>('regex')

  // AI Configuration
  const [aiProvider, setAiProvider] = useState<'gemini' | 'ollama'>('gemini')
  const [aiCharacterLimit, setAiCharacterLimit] = useState(50000)
  const [geminiApiKey, setGeminiApiKey] = useState('')
  const [geminiProjectId, setGeminiProjectId] = useState('')

  // Load predefined categories
  useEffect(() => {
    const loadCategories = async () => {
      setLoadingCategories(true)
      try {
        const response = await articlesApi.getPredefinedCategories('fr')
        setPredefinedCategories(response.categories)
      } catch (err: any) {
        console.error('Failed to load predefined categories:', err)
      } finally {
        setLoadingCategories(false)
      }
    }
    loadCategories()
  }, [])

  const handleRetrieveArticles = async () => {
    setRetrievingArticles(true)
    setError(null)

    try {
      let result

      if (mode === 'category') {
        // Use selected predefined category or custom category
        const targetCategory = selectedCategory === 'custom' ? category : selectedCategory
        if (!targetCategory) {
          setError('Veuillez sélectionner ou entrer une catégorie')
          setRetrievingArticles(false)
          return
        }

        result = await articlesApi.searchByCategory({
          category: targetCategory,
          limit: maxArticles,
          recursive,
          exclude_published: excludePublished,
          include_analyzed: includeAnalyzed
        })
      } else if (mode === 'manual') {
        const titles = manualTitles.split('\n').map(t => t.trim()).filter(t => t)
        if (titles.length === 0) {
          setError('Veuillez entrer au moins un titre d\'article')
          setRetrievingArticles(false)
          return
        }

        result = await articlesApi.searchManual({
          titles,
          exclude_published: excludePublished,
          include_analyzed: includeAnalyzed
        })
      } else if (mode === 'petscan') {
        if (!petScanId) {
          setError('Veuillez entrer un PetScan ID')
          setRetrievingArticles(false)
          return
        }

        result = await articlesApi.searchPetScan({
          psid: petScanId,
          limit: maxArticles,
          exclude_published: excludePublished,
          include_analyzed: includeAnalyzed
        })
      } else if (mode === 'file') {
        if (!filePath) {
          setError('Veuillez entrer le chemin du fichier')
          setRetrievingArticles(false)
          return
        }

        result = await articlesApi.searchFile({
          file_path: filePath,
          limit: maxArticles,
          include_analyzed: includeAnalyzed
        })
      } else if (mode === 'user-contribs') {
        if (!username) {
          setError('Veuillez entrer un nom d\'utilisateur')
          setRetrievingArticles(false)
          return
        }

        result = await articlesApi.searchUserContribs({
          username,
          limit: maxArticles,
          exclude_published: excludePublished,
          include_analyzed: includeAnalyzed
        })
      } else {
        setError('Mode non supporté')
        setRetrievingArticles(false)
        return
      }

      const retrievedArticles = result.articles || []
      setArticles(retrievedArticles)
      setArticlesRetrieved(true)

      // Add articles to queue only if they are not already analyzed or published
      if (retrievedArticles.length > 0) {
        await addArticlesToQueue(retrievedArticles, mode)
      }
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la récupération des articles')
    } finally {
      setRetrievingArticles(false)
    }
  }

  const addArticlesToQueue = async (retrievedArticles: any[], source: string) => {
    try {
      const addedCount = await articlesApi.addArticlesToAnalyze({
        articles: retrievedArticles.map(article => ({
          title: article.title,
          page_id: article.page_id,
          revision_id: article.revision_id,
          source: source,
          source_details: getSourceDetails(source),
          priority: 'medium'
        }))
      })

      if (addedCount.added_count > 0) {
        // Show success message
        console.log(`Added ${addedCount.added_count} articles to analysis queue`)
      }
    } catch (err: any) {
      console.error('Failed to add articles to queue:', err)
      // Don't block the main workflow if this fails
    }
  }

  const getSourceDetails = (source: string) => {
    switch (source) {
      case 'category':
        return selectedCategory === 'custom' ? category : selectedCategory
      case 'manual':
        return 'Manual entry'
      case 'petscan':
        return `PetScan ID: ${petScanId}`
      case 'file':
        return `File: ${filePath}`
      case 'user-contribs':
        return `User: ${username}`
      default:
        return source
    }
  }

  const handleStartAnalysis = async () => {
    setError(null)

    if (mode === 'article' && !articleTitle) {
      setError('Veuillez entrer un titre d\'article')
      return
    }

    // For retrieval modes, require articles to be retrieved first
    if (['category', 'manual', 'petscan', 'file', 'user-contribs'].includes(mode)) {
      if (!articlesRetrieved) {
        setError('Veuillez d\'abord récupérer les articles')
        return
      }
      if (articles.length === 0) {
        setError('Aucun article disponible')
        return
      }
    }

    // Validate AI configuration if IA mode is selected
    if (analysisMode === 'ia') {
      if (aiProvider === 'gemini' && (!geminiApiKey || !geminiProjectId)) {
        setError('Veuillez configurer l\'API key et le Project ID Gemini')
        return
      }
    }

    setLoading(true)
    try {
      const baseRequest = {
        mode: analysisMode,
        ai_provider: aiProvider,
        ai_character_limit: aiCharacterLimit,
        gemini_api_key: geminiApiKey,
        gemini_project_id: geminiProjectId
      }

      if (mode === 'article') {
        // Single article analysis
        const request = {
          ...baseRequest,
          article_title: articleTitle,
          analysis_type: 'article' as const
        }

        const result = await analysisApi.startAnalysis(request)
        navigate(`/analysis/results?jobId=${result.job_id}`)
      } else {
        // Batch analysis for selected articles or all articles
        const articlesToAnalyze = selectedArticles.size > 0
          ? articles.filter(a => selectedArticles.has(a.title))
          : articles

        if (articlesToAnalyze.length === 0) {
          setError('Veuillez sélectionner au moins un article')
          setLoading(false)
          return
        }

        const articleTitles = articlesToAnalyze.map(a => a.title)
        const request = {
          ...baseRequest,
          article_titles: articleTitles
        }

        const result = await analysisApi.startBatchAnalysis(request)
        // Navigate to analyzed history to see results when ready
        navigate('/analysis/history')
      }
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors du démarrage de l\'analyse')
    } finally {
      setLoading(false)
    }
  }

  const handleAnalyzeSingle = async (articleTitle: string) => {
    setError(null)
    setAnalyzingArticle(articleTitle)

    // Validate AI configuration if IA mode is selected
    if (analysisMode === 'ia') {
      if (aiProvider === 'gemini' && (!geminiApiKey || !geminiProjectId)) {
        setError('Veuillez configurer l\'API key et le Project ID Gemini')
        setAnalyzingArticle(null)
        return
      }
    }

    try {
      const request = {
        mode: analysisMode,
        ai_provider: aiProvider,
        ai_character_limit: aiCharacterLimit,
        gemini_api_key: geminiApiKey,
        gemini_project_id: geminiProjectId,
        article_title: articleTitle,
        analysis_type: 'article' as const
      }

      const result = await analysisApi.startAnalysis(request)
      // Navigate to analyzed history to see results when ready
      navigate('/analysis/history')
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors du démarrage de l\'analyse')
      setAnalyzingArticle(null)
    }
  }

  const handleSelectAll = () => {
    if (selectedArticles.size === articles.length) {
      setSelectedArticles(new Set())
    } else {
      setSelectedArticles(new Set(articles.map(a => a.title)))
    }
  }

  const handleToggleArticle = (title: string) => {
    const newSelected = new Set(selectedArticles)
    if (newSelected.has(title)) {
      newSelected.delete(title)
    } else {
      newSelected.add(title)
    }
    setSelectedArticles(newSelected)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
      <div>
        <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>Nouvelle Analyse</h2>
        <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Démarrer une nouvelle analyse de liens morts</p>
      </div>

      {/* Mode Selection */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
          Source d'articles
        </h3>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={() => setMode('category')}
            style={{
              flex: '1 1 auto',
              padding: '12px',
              backgroundColor: mode === 'category' ? '#3b82f6' : '#1a1a1a',
              border: mode === 'category' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
              borderRadius: '6px',
              color: mode === 'category' ? '#ffffff' : '#a0a0a0',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              minWidth: '120px'
            }}
          >
            <FileText style={{ width: '16px', height: '16px' }} />
            Catégorie
          </button>
          <button
            onClick={() => setMode('manual')}
            style={{
              flex: '1 1 auto',
              padding: '12px',
              backgroundColor: mode === 'manual' ? '#3b82f6' : '#1a1a1a',
              border: mode === 'manual' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
              borderRadius: '6px',
              color: mode === 'manual' ? '#ffffff' : '#a0a0a0',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              minWidth: '120px'
            }}
          >
            <Search style={{ width: '16px', height: '16px' }} />
            Manuel
          </button>
          <button
            onClick={() => setMode('petscan')}
            style={{
              flex: '1 1 auto',
              padding: '12px',
              backgroundColor: mode === 'petscan' ? '#3b82f6' : '#1a1a1a',
              border: mode === 'petscan' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
              borderRadius: '6px',
              color: mode === 'petscan' ? '#ffffff' : '#a0a0a0',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              minWidth: '120px'
            }}
          >
            <Scan style={{ width: '16px', height: '16px' }} />
            PetScan
          </button>
          <button
            onClick={() => setMode('file')}
            style={{
              flex: '1 1 auto',
              padding: '12px',
              backgroundColor: mode === 'file' ? '#3b82f6' : '#1a1a1a',
              border: mode === 'file' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
              borderRadius: '6px',
              color: mode === 'file' ? '#ffffff' : '#a0a0a0',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              minWidth: '120px'
            }}
          >
            <FileIcon style={{ width: '16px', height: '16px' }} />
            Fichier
          </button>
          <button
            onClick={() => setMode('user-contribs')}
            style={{
              flex: '1 1 auto',
              padding: '12px',
              backgroundColor: mode === 'user-contribs' ? '#3b82f6' : '#1a1a1a',
              border: mode === 'user-contribs' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
              borderRadius: '6px',
              color: mode === 'user-contribs' ? '#ffffff' : '#a0a0a0',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              minWidth: '120px'
            }}
          >
            <User style={{ width: '16px', height: '16px' }} />
            Contributions
          </button>
          <button
            onClick={() => setMode('article')}
            style={{
              flex: '1 1 auto',
              padding: '12px',
              backgroundColor: mode === 'article' ? '#3b82f6' : '#1a1a1a',
              border: mode === 'article' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
              borderRadius: '6px',
              color: mode === 'article' ? '#ffffff' : '#a0a0a0',
              fontSize: '14px',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              minWidth: '120px'
            }}
          >
            <Search style={{ width: '16px', height: '16px' }} />
            Article unique
          </button>
        </div>
      </div>

      {/* Input Form */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
          {mode === 'category' ? 'Catégorie' : 
           mode === 'manual' ? 'Liste manuelle' :
           mode === 'petscan' ? 'PetScan' :
           mode === 'file' ? 'Fichier' :
           mode === 'user-contribs' ? 'Contributions utilisateur' :
           'Article unique'}
        </h3>
        
        {mode === 'category' ? (
          <div>
            {/* Predefined Categories Dropdown */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Catégorie prédéfinie
              </label>
              <select
                value={selectedCategory}
                onChange={(e) => {
                  setSelectedCategory(e.target.value)
                  if (e.target.value !== 'custom') {
                    setCategory(e.target.value)
                  }
                }}
                disabled={loadingCategories}
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
                <option value="custom">Autre (personnalisé)</option>
                {predefinedCategories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            {/* Custom Category Input */}
            {selectedCategory === 'custom' && (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Nom de la catégorie personnalisée
                </label>
                <input
                  type="text"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="Ex: Article à wikifier/Liste complète"
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
            )}

            <p style={{ fontSize: '12px', color: '#666666', marginTop: '8px' }}>
              L'analyse recherchera tous les articles de cette catégorie
            </p>

            {/* Category Options */}
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Max articles
                </label>
                <input
                  type="number"
                  value={maxArticles}
                  onChange={(e) => setMaxArticles(parseInt(e.target.value) || 100)}
                  min="1"
                  max="1000"
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

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="recursive"
                  checked={recursive}
                  onChange={(e) => setRecursive(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="recursive" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Inclure les sous-catégories
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="exclude-published"
                  checked={excludePublished}
                  onChange={(e) => setExcludePublished(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="exclude-published" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Exclure les articles publiés récemment (6 mois)
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="include-analyzed"
                  checked={includeAnalyzed}
                  onChange={(e) => setIncludeAnalyzed(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="include-analyzed" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Inclure les articles déjà analysés
                </label>
              </div>
            </div>

            {/* Retrieve Articles Button */}
            <button
              onClick={handleRetrieveArticles}
              disabled={retrievingArticles || !category}
              style={{
                marginTop: '16px',
                width: '100%',
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #3b82f6',
                borderRadius: '6px',
                color: '#3b82f6',
                fontSize: '14px',
                fontWeight: 500,
                cursor: retrievingArticles || !category ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'center'
              }}
            >
              {retrievingArticles ? 'Récupération...' : 'Récupérer les articles'}
            </button>

            {/* Articles Retrieved Info */}
            {articlesRetrieved && (
              <div style={{
                marginTop: '16px',
                padding: '12px',
                backgroundColor: '#161616',
                borderRadius: '6px',
                border: '1px solid #2a2a2a'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle style={{ width: '16px', height: '16px', color: '#10b981' }} />
                  <span style={{ fontSize: '14px', color: '#f5f5f5' }}>
                    {articles.length} article(s) trouvé(s)
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : mode === 'manual' ? (
          <div>
            <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
              Titres d'articles (un par ligne)
            </label>
            <textarea
              value={manualTitles}
              onChange={(e) => setManualTitles(e.target.value)}
              placeholder="Paris&#10;Londres&#10;Berlin"
              rows={10}
              style={{
                width: '100%',
                padding: '12px',
                backgroundColor: '#0a0a0a',
                border: '1px solid #2a2a2a',
                borderRadius: '6px',
                color: '#f5f5f5',
                fontSize: '14px',
                fontFamily: 'monospace',
                resize: 'vertical'
              }}
            />
            <p style={{ fontSize: '12px', color: '#666666', marginTop: '8px' }}>
              Entrez un titre d'article par ligne
            </p>

            {/* Manual Options */}
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="exclude-published-manual"
                  checked={excludePublished}
                  onChange={(e) => setExcludePublished(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="exclude-published-manual" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Exclure les articles publiés récemment (6 mois)
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="include-analyzed-manual"
                  checked={includeAnalyzed}
                  onChange={(e) => setIncludeAnalyzed(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="include-analyzed-manual" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Inclure les articles déjà analysés
                </label>
              </div>
            </div>

            {/* Retrieve Articles Button */}
            <button
              onClick={handleRetrieveArticles}
              disabled={retrievingArticles}
              style={{
                marginTop: '16px',
                width: '100%',
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #3b82f6',
                borderRadius: '6px',
                color: '#3b82f6',
                fontSize: '14px',
                fontWeight: 500,
                cursor: retrievingArticles ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'center'
              }}
            >
              {retrievingArticles ? 'Récupération...' : 'Récupérer les articles'}
            </button>

            {/* Articles Retrieved Info */}
            {articlesRetrieved && (
              <div style={{
                marginTop: '16px',
                padding: '12px',
                backgroundColor: '#161616',
                borderRadius: '6px',
                border: '1px solid #2a2a2a'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle style={{ width: '16px', height: '16px', color: '#10b981' }} />
                  <span style={{ fontSize: '14px', color: '#f5f5f5' }}>
                    {articles.length} article(s) trouvé(s)
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : mode === 'petscan' ? (
          <div>
            <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
              PetScan ID
            </label>
            <input
              type="text"
              value={petScanId}
              onChange={(e) => setPetScanId(e.target.value)}
              placeholder="Ex: 123456"
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
            <p style={{ fontSize: '12px', color: '#666666', marginTop: '8px' }}>
              Entrez l'ID de la requête PetScan (nombre entier)
            </p>

            {/* PetScan Options */}
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Max articles
                </label>
                <input
                  type="number"
                  value={maxArticles}
                  onChange={(e) => setMaxArticles(parseInt(e.target.value) || 100)}
                  min="1"
                  max="1000"
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

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="exclude-published-petscan"
                  checked={excludePublished}
                  onChange={(e) => setExcludePublished(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="exclude-published-petscan" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Exclure les articles publiés récemment (6 mois)
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="include-analyzed-petscan"
                  checked={includeAnalyzed}
                  onChange={(e) => setIncludeAnalyzed(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="include-analyzed-petscan" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Inclure les articles déjà analysés
                </label>
              </div>
            </div>

            {/* Retrieve Articles Button */}
            <button
              onClick={handleRetrieveArticles}
              disabled={retrievingArticles || !petScanId}
              style={{
                marginTop: '16px',
                width: '100%',
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #3b82f6',
                borderRadius: '6px',
                color: '#3b82f6',
                fontSize: '14px',
                fontWeight: 500,
                cursor: retrievingArticles || !petScanId ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'center'
              }}
            >
              {retrievingArticles ? 'Récupération...' : 'Récupérer les articles'}
            </button>

            {/* Articles Retrieved Info */}
            {articlesRetrieved && (
              <div style={{
                marginTop: '16px',
                padding: '12px',
                backgroundColor: '#161616',
                borderRadius: '6px',
                border: '1px solid #2a2a2a'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle style={{ width: '16px', height: '16px', color: '#10b981' }} />
                  <span style={{ fontSize: '14px', color: '#f5f5f5' }}>
                    {articles.length} article(s) trouvé(s)
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : mode === 'file' ? (
          <div>
            <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
              Chemin du fichier
            </label>
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="Ex: /path/to/articles.txt"
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
            <p style={{ fontSize: '12px', color: '#666666', marginTop: '8px' }}>
              Le fichier doit contenir un titre d'article par ligne
            </p>

            {/* File Options */}
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Max articles
                </label>
                <input
                  type="number"
                  value={maxArticles}
                  onChange={(e) => setMaxArticles(parseInt(e.target.value) || 100)}
                  min="1"
                  max="1000"
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

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="include-analyzed-file"
                  checked={includeAnalyzed}
                  onChange={(e) => setIncludeAnalyzed(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="include-analyzed-file" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Inclure les articles déjà analysés
                </label>
              </div>
            </div>

            {/* Retrieve Articles Button */}
            <button
              onClick={handleRetrieveArticles}
              disabled={retrievingArticles || !filePath}
              style={{
                marginTop: '16px',
                width: '100%',
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #3b82f6',
                borderRadius: '6px',
                color: '#3b82f6',
                fontSize: '14px',
                fontWeight: 500,
                cursor: retrievingArticles || !filePath ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'center'
              }}
            >
              {retrievingArticles ? 'Récupération...' : 'Récupérer les articles'}
            </button>

            {/* Articles Retrieved Info */}
            {articlesRetrieved && (
              <div style={{
                marginTop: '16px',
                padding: '12px',
                backgroundColor: '#161616',
                borderRadius: '6px',
                border: '1px solid #2a2a2a'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle style={{ width: '16px', height: '16px', color: '#10b981' }} />
                  <span style={{ fontSize: '14px', color: '#f5f5f5' }}>
                    {articles.length} article(s) trouvé(s)
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : mode === 'user-contribs' ? (
          <div>
            <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
              Nom d'utilisateur Wikipédia
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Ex: Username"
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
            <p style={{ fontSize: '12px', color: '#666666', marginTop: '8px' }}>
              Récupérera les articles récemment modifiés par cet utilisateur
            </p>

            {/* User Contribs Options */}
            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                  Max articles
                </label>
                <input
                  type="number"
                  value={maxArticles}
                  onChange={(e) => setMaxArticles(parseInt(e.target.value) || 100)}
                  min="1"
                  max="1000"
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

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="exclude-published-user"
                  checked={excludePublished}
                  onChange={(e) => setExcludePublished(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="exclude-published-user" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Exclure les articles publiés récemment (6 mois)
                </label>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <input
                  type="checkbox"
                  id="include-analyzed-user"
                  checked={includeAnalyzed}
                  onChange={(e) => setIncludeAnalyzed(e.target.checked)}
                  style={{ width: '16px', height: '16px' }}
                />
                <label htmlFor="include-analyzed-user" style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  Inclure les articles déjà analysés
                </label>
              </div>
            </div>

            {/* Retrieve Articles Button */}
            <button
              onClick={handleRetrieveArticles}
              disabled={retrievingArticles || !username}
              style={{
                marginTop: '16px',
                width: '100%',
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #3b82f6',
                borderRadius: '6px',
                color: '#3b82f6',
                fontSize: '14px',
                fontWeight: 500,
                cursor: retrievingArticles || !username ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'center'
              }}
            >
              {retrievingArticles ? 'Récupération...' : 'Récupérer les articles'}
            </button>

            {/* View History Button */}
            <button
              onClick={() => {
                navigate('/user-contributions')
              }}
              style={{
                marginTop: '8px',
                width: '100%',
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #2a2a2a',
                borderRadius: '6px',
                color: '#a0a0a0',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'center'
              }}
            >
              Voir mes 50 dernières contributions
            </button>

            {/* Articles Retrieved Info */}
            {articlesRetrieved && (
              <div style={{
                marginTop: '16px',
                padding: '12px',
                backgroundColor: '#161616',
                borderRadius: '6px',
                border: '1px solid #2a2a2a'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CheckCircle style={{ width: '16px', height: '16px', color: '#10b981' }} />
                  <span style={{ fontSize: '14px', color: '#f5f5f5' }}>
                    {articles.length} article(s) trouvé(s)
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div>
            <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
              Titre de l'article
            </label>
            <input
              type="text"
              value={articleTitle}
              onChange={(e) => setArticleTitle(e.target.value)}
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
            <p style={{ fontSize: '12px', color: '#666666', marginTop: '8px' }}>
              L'analyse sera effectuée sur cet article spécifique
            </p>
          </div>
        )}
      </div>

      {/* Analysis Mode - Only show for non-user-contribs modes */}
      {mode !== 'user-contribs' && (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
            Mode d'analyse
          </h3>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => setAnalysisMode('regex')}
              style={{
                flex: 1,
                padding: '12px',
                backgroundColor: analysisMode === 'regex' ? '#3b82f6' : '#1a1a1a',
                border: analysisMode === 'regex' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
                borderRadius: '6px',
                color: analysisMode === 'regex' ? '#ffffff' : '#a0a0a0',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer'
              }}
            >
              Regex (Rapide)
            </button>
            <button
              onClick={() => setAnalysisMode('ia')}
              style={{
                flex: 1,
                padding: '12px',
                backgroundColor: analysisMode === 'ia' ? '#3b82f6' : '#1a1a1a',
                border: analysisMode === 'ia' ? '1px solid #3b82f6' : '1px solid #2a2a2a',
                borderRadius: '6px',
                color: analysisMode === 'ia' ? '#ffffff' : '#a0a0a0',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer'
              }}
            >
              IA (Précis)
            </button>
          </div>
        </div>
      )}

      {/* AI Configuration */}
      {analysisMode === 'ia' && (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
            Configuration IA
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Provider IA
              </label>
              <select
                value={aiProvider}
                onChange={(e) => setAiProvider(e.target.value as 'gemini' | 'ollama')}
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
                <option value="gemini">Google Gemini</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Limite de caractères
              </label>
              <input
                type="number"
                value={aiCharacterLimit}
                onChange={(e) => setAiCharacterLimit(parseInt(e.target.value) || 50000)}
                min="1000"
                max="100000"
                step="1000"
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
              <p style={{ fontSize: '12px', color: '#666666', marginTop: '4px' }}>
                Nombre maximum de caractères à envoyer à l'IA
              </p>
            </div>

            {aiProvider === 'gemini' && (
              <>
                <div>
                  <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                    API Key Gemini
                  </label>
                  <input
                    type="password"
                    value={geminiApiKey}
                    onChange={(e) => setGeminiApiKey(e.target.value)}
                    placeholder="AIza..."
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
                    Project ID
                  </label>
                  <input
                    type="text"
                    value={geminiProjectId}
                    onChange={(e) => setGeminiProjectId(e.target.value)}
                    placeholder="your-project-id"
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
              </>
            )}

            {aiProvider === 'ollama' && (
              <div style={{ padding: '12px', backgroundColor: '#1a1a1a', borderRadius: '6px', border: '1px solid #2a2a2a' }}>
                <p style={{ fontSize: '12px', color: '#a0a0a0' }}>
                  Ollama doit être installé et configuré localement. Assurez-vous que le serveur Ollama est accessible.
                </p>
              </div>
            )}
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

      {/* Articles List - Only show for non-user-contribs modes */}
      {articlesRetrieved && articles.length > 0 && mode !== 'user-contribs' && (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Articles récupérés ({articles.length})
            </h3>
            <button
              onClick={handleSelectAll}
              style={{
                padding: '6px 12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #3b82f6',
                borderRadius: '4px',
                color: '#3b82f6',
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              {selectedArticles.size === articles.length ? 'Tout désélectionner' : 'Tout sélectionner'}
            </button>
          </div>

          <div style={{ maxHeight: '400px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {articles.map((article, index) => (
              <div
                key={article.title || index}
                style={{
                  padding: '12px',
                  backgroundColor: '#1a1a1a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  transition: 'all 0.2s'
                }}
              >
                <input
                  type="checkbox"
                  checked={selectedArticles.has(article.title)}
                  onChange={() => handleToggleArticle(article.title)}
                  style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '14px', color: '#f5f5f5', fontWeight: 500 }}>
                    {article.title}
                  </div>
                  {article.page_id && (
                    <div style={{ fontSize: '12px', color: '#666666' }}>
                      Page ID: {article.page_id}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleAnalyzeSingle(article.title)}
                  disabled={analyzingArticle === article.title}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: analyzingArticle === article.title ? '#3b82f6' : '#10b981',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#ffffff',
                    fontSize: '12px',
                    cursor: analyzingArticle === article.title ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  {analyzingArticle === article.title ? 'Analyse...' : 'Analyser'}
                </button>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '12px', fontSize: '12px', color: '#666666' }}>
            {selectedArticles.size > 0
              ? `${selectedArticles.size} article(s) sélectionné(s)`
              : 'Aucun article sélectionné'}
          </div>
        </div>
      )}

      {/* Start Button - Only show for non-user-contribs modes */}
      {mode !== 'user-contribs' && (
        <button
          className="btn btn-primary"
          onClick={handleStartAnalysis}
          disabled={loading}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}
        >
          <Search style={{ width: '16px', height: '16px' }} />
          {loading ? 'Démarrage...' : selectedArticles.size > 0
            ? `Analyser ${selectedArticles.size} article(s)`
            : 'Analyser tous les articles'}
        </button>
      )}
    </div>
  )
}
