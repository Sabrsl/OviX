import { useState, useEffect, useCallback } from 'react'
import { Search, FileText, AlertTriangle, CheckCircle, User, FileText as FileIcon, Scan, Download } from 'lucide-react'
import { articlesApi } from '../api/articles.api'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'

type Mode = 'category' | 'manual' | 'petscan' | 'file' | 'user-contribs' | 'article'

const LS_ARTICLES = 'retrievedArticles'
const LS_SELECTED = 'selectedArticles'
const LS_RETRIEVED = 'articlesRetrieved'

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback
  try {
    return JSON.parse(raw) as T
  } catch (e) {
    console.error('Failed to parse saved data:', e)
    return fallback
  }
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

const helpStyle: React.CSSProperties = {
  fontSize: '11px',
  color: '#666666',
  marginTop: '6px'
}

const sectionTitleStyle: React.CSSProperties = {
  fontSize: '12px',
  fontWeight: 500,
  color: '#666666',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  marginBottom: '14px'
}

function CheckboxRow({
  id,
  checked,
  onChange,
  label
}: {
  id: string
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <input
        type="checkbox"
        id={id}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ width: '14px', height: '14px', cursor: 'pointer' }}
      />
      <label htmlFor={id} style={{ fontSize: '13px', color: '#a0a0a0', cursor: 'pointer' }}>
        {label}
      </label>
    </div>
  )
}

function ArticlesRetrievedBadge({ count }: { count: number }) {
  return (
    <div
      style={{
        marginTop: '16px',
        padding: '10px 12px',
        backgroundColor: '#161616',
        borderRadius: '6px',
        border: '1px solid #2a2a2a'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <CheckCircle style={{ width: '14px', height: '14px', color: '#059669', flexShrink: 0 }} />
        <span style={{ fontSize: '13px', color: '#f5f5f5' }}>
          {count} article{count > 1 ? 's' : ''} trouvé{count > 1 ? 's' : ''}
        </span>
      </div>
    </div>
  )
}

export default function RecuperationArticles() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('category')
  const [articleTitle, setArticleTitle] = useState('')
  const [category, setCategory] = useState('Article à wikifier/Liste complète')
  const [error, setError] = useState<string | null>(null)

  // Predefined categories
  const [predefinedCategories, setPredefinedCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('custom')
  const [loadingCategories, setLoadingCategories] = useState(false)

  // Shared options
  const [maxArticles, setMaxArticles] = useState(100)
  const [recursive, setRecursive] = useState(false)
  const [excludePublished, setExcludePublished] = useState(true)
  const [includeAnalyzed, setIncludeAnalyzed] = useState(false)

  // Article retrieval
  const [retrievingArticles, setRetrievingArticles] = useState(false)
  const [analyzingSingleArticle, setAnalyzingSingleArticle] = useState(false)
  const [articles, setArticles] = useState<any[]>([])
  const [articlesRetrieved, setArticlesRetrieved] = useState(false)
  const [selectedArticles, setSelectedArticles] = useState<Set<string>>(new Set())

  // Mode-specific inputs
  const [manualTitles, setManualTitles] = useState('')
  const [petScanId, setPetScanId] = useState('')
  const [filePath, setFilePath] = useState('')
  const [username, setUsername] = useState('')

  // Load persisted state on mount
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      const savedArticles = safeParse<any[]>(localStorage.getItem(LS_ARTICLES), [])
      const savedSelected = safeParse<string[]>(localStorage.getItem(LS_SELECTED), [])
      const savedRetrieved = localStorage.getItem(LS_RETRIEVED) === 'true'

      if (Array.isArray(savedArticles) && savedArticles.length > 0) {
        setArticles(savedArticles)
      }
      if (Array.isArray(savedSelected) && savedSelected.length > 0) {
        setSelectedArticles(new Set(savedSelected))
      }
      setArticlesRetrieved(savedRetrieved)
    } catch (e) {
      console.error('Failed to restore persisted state:', e)
    }
  }, [])

  // Persist state when it changes
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      if (articles.length > 0) {
        localStorage.setItem(LS_ARTICLES, JSON.stringify(articles))
      } else {
        localStorage.removeItem(LS_ARTICLES)
      }
    } catch (e) {
      console.error('Failed to persist articles:', e)
    }
  }, [articles])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(LS_SELECTED, JSON.stringify(Array.from(selectedArticles)))
    } catch (e) {
      console.error('Failed to persist selection:', e)
    }
  }, [selectedArticles])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      localStorage.setItem(LS_RETRIEVED, String(articlesRetrieved))
    } catch (e) {
      console.error('Failed to persist retrieved flag:', e)
    }
  }, [articlesRetrieved])

  // Load predefined categories
  useEffect(() => {
    let cancelled = false
    const loadCategories = async () => {
      setLoadingCategories(true)
      try {
        const response = await articlesApi.getPredefinedCategories('fr')
        if (!cancelled) {
          setPredefinedCategories(response?.categories ?? [])
        }
      } catch (err: any) {
        console.error('Failed to load predefined categories:', err)
      } finally {
        if (!cancelled) setLoadingCategories(false)
      }
    }
    loadCategories()
    return () => {
      cancelled = true
    }
  }, [])

  const handleRetrieveArticles = useCallback(async () => {
    setError(null)
    setRetrievingArticles(true)

    try {
      let result: any

      if (mode === 'category') {
        const targetCategory = selectedCategory === 'custom' ? category.trim() : selectedCategory
        if (!targetCategory) {
          setError('Veuillez sélectionner ou entrer une catégorie')
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
        const titles = manualTitles.split('\n').map((t) => t.trim()).filter(Boolean)
        if (titles.length === 0) {
          setError("Veuillez entrer au moins un titre d'article")
          return
        }
        result = await articlesApi.searchManual({
          titles,
          exclude_published: excludePublished,
          include_analyzed: includeAnalyzed
        })
      } else if (mode === 'petscan') {
        const psid = petScanId.trim()
        if (!psid) {
          setError('Veuillez entrer un PetScan ID')
          return
        }
        result = await articlesApi.searchPetScan({
          psid,
          limit: maxArticles,
          exclude_published: excludePublished,
          include_analyzed: includeAnalyzed
        })
      } else if (mode === 'file') {
        const path = filePath.trim()
        if (!path) {
          setError('Veuillez entrer le chemin du fichier')
          return
        }
        result = await articlesApi.searchFile({
          file_path: path,
          limit: maxArticles,
          include_analyzed: includeAnalyzed
        })
      } else if (mode === 'user-contribs') {
        const user = username.trim()
        if (!user) {
          setError("Veuillez entrer un nom d'utilisateur")
          return
        }
        result = await articlesApi.searchUserContribs({
          username: user,
          limit: maxArticles,
          exclude_published: excludePublished,
          include_analyzed: includeAnalyzed
        })
      } else {
        setError('Mode non supporté')
        return
      }

      const retrievedArticles = Array.isArray(result?.articles) ? result.articles : []
      setArticles(retrievedArticles)
      setSelectedArticles(new Set())
      setArticlesRetrieved(true)
    } catch (err: any) {
      setError(err?.message || err?.userMessage || 'Erreur lors de la récupération des articles')
    } finally {
      setRetrievingArticles(false)
    }
  }, [mode, selectedCategory, category, maxArticles, recursive, excludePublished, includeAnalyzed, manualTitles, petScanId, filePath, username])

  const handleStartAnalysis = async () => {
    setError(null)

    if (mode === 'article') {
      const title = articleTitle.trim()
      if (!title) {
        setError("Veuillez entrer un titre d'article")
        return
      }
      
      setAnalyzingSingleArticle(true)
      
      try {
        // Add article to analysis queue first
        await articlesApi.addArticlesToAnalyze({
          articles: [{
            title,
            source: 'manual',
            source_details: 'Article unique',
            priority: 'high'
          }]
        })
        
        // Trigger analysis
        await articlesApi.analyzeArticle(title, 'regex')
        
        // Navigate to detail page
        navigate(`/article/detail?title=${encodeURIComponent(title)}`)
      } catch (err: any) {
        setError(err?.message || err?.userMessage || 'Erreur lors de l\'ajout de l\'article à la file d\'analyse')
      } finally {
        setAnalyzingSingleArticle(false)
      }
      return
    }

    // For other modes (category, manual, petscan, file), add selected articles to analysis queue
    if (selectedArticles.size > 0) {
      setRetrievingArticles(true)
      try {
        const sourceMap: Record<Mode, string> = {
          category: 'category',
          manual: 'manual',
          petscan: 'petscan',
          file: 'file',
          'user-contribs': 'user-contribs',
          article: 'manual'
        }
        
        const sourceDetailsMap: Record<Mode, string> = {
          category: selectedCategory === 'custom' ? category.trim() : selectedCategory,
          manual: 'Liste manuelle',
          petscan: `PetScan ID: ${petScanId}`,
          file: `Fichier: ${filePath}`,
          'user-contribs': `Contributions: ${username}`,
          article: 'Article unique'
        }

        const articlesToAdd = Array.from(selectedArticles).map(title => ({
          title,
          source: sourceMap[mode],
          source_details: sourceDetailsMap[mode],
          priority: 'medium' as const
        }))

        const result = await articlesApi.addArticlesToAnalyze({
          articles: articlesToAdd
        })

        if (result.success) {
          navigate('/analysis/history')
        } else {
          setError(result.message || 'Erreur lors de l\'ajout des articles à la file d\'analyse')
        }
      } catch (err: any) {
        setError(err?.message || err?.userMessage || 'Erreur lors de l\'ajout des articles à la file d\'analyse')
      } finally {
        setRetrievingArticles(false)
      }
    } else {
      navigate('/analysis/history')
    }
  }

  const handleSelectAll = () => {
    setSelectedArticles((prev) =>
      prev.size === articles.length ? new Set() : new Set(articles.map((a) => a.title))
    )
  }

  const handleToggleArticle = (title: string) => {
    setSelectedArticles((prev) => {
      const next = new Set(prev)
      if (next.has(title)) {
        next.delete(title)
      } else {
        next.add(title)
      }
      return next
    })
  }

  const modeMeta: Record<Mode, { icon: JSX.Element; label: string; disabled?: boolean }> = {
    category: { icon: <FileText style={{ width: '14px', height: '14px' }} />, label: 'Catégorie' },
    article: { icon: <Search style={{ width: '14px', height: '14px' }} />, label: 'Article unique' },
    file: { icon: <FileIcon style={{ width: '14px', height: '14px' }} />, label: 'Fichier' },
    manual: { icon: <Search style={{ width: '14px', height: '14px' }} />, label: 'Manuel' },
    petscan: { icon: <Scan style={{ width: '14px', height: '14px' }} />, label: 'PetScan' },
    'user-contribs': { icon: <User style={{ width: '14px', height: '14px' }} />, label: 'Contributions', disabled: true }
  }

  const sectionTitles: Record<Mode, string> = {
    category: 'Catégorie',
    manual: 'Liste manuelle',
    petscan: 'PetScan',
    file: 'Fichier',
    'user-contribs': 'Contributions utilisateur',
    article: 'Article unique'
  }

  const isRetrievalMode = mode !== 'article'
  const isFormValid = (() => {
    if (mode === 'category') return selectedCategory === 'custom' ? category.trim().length > 0 : true
    if (mode === 'petscan') return petScanId.trim().length > 0
    if (mode === 'file') return filePath.trim().length > 0
    if (mode === 'user-contribs') return username.trim().length > 0
    return true
  })()

  const maxArticlesField = (
    <div>
      <label style={labelStyle}>Max articles</label>
      <input
        type="number"
        value={maxArticles}
        onChange={(e) => {
          const v = parseInt(e.target.value, 10)
          setMaxArticles(Number.isFinite(v) && v > 0 ? v : 100)
        }}
        min={1}
        max={1000}
        style={inputStyle}
      />
    </div>
  )

  const excludePublishedField = (idSuffix: string) => (
    <CheckboxRow
      id={`exclude-published-${idSuffix}`}
      checked={excludePublished}
      onChange={setExcludePublished}
      label="Exclure les articles publiés récemment (6 mois)"
    />
  )

  const includeAnalyzedField = (idSuffix: string) => (
    <CheckboxRow
      id={`include-analyzed-${idSuffix}`}
      checked={includeAnalyzed}
      onChange={setIncludeAnalyzed}
      label="Inclure les articles déjà analysés"
    />
  )

  const retrieveButton = (fullWidth = true) => (
    <Button
      variant="neutral"
      onClick={handleRetrieveArticles}
      disabled={retrievingArticles || !isFormValid}
      style={{
        marginTop: '16px',
        width: fullWidth ? '100%' : undefined,
        padding: '10px 12px',
        fontSize: '13px'
      }}
    >
      <Download style={{ width: '14px', height: '14px' }} />
      {retrievingArticles ? 'Récupération...' : 'Récupérer les articles'}
    </Button>
  )

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
        animation: 'fadeIn 0.2s ease-in-out',
        maxWidth: '860px',
        margin: '0 auto',
        padding: '0 16px'
      }}
    >
      <div>
        <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#f5f5f5' }}>Récupération d'articles</h2>
        <p style={{ color: '#a0a0a0', marginTop: '4px', fontSize: '13px' }}>
          Récupérer des articles pour analyse
        </p>
      </div>

      {/* Mode Selection */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
        <h3 style={sectionTitleStyle}>Source d'articles</h3>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {(Object.keys(modeMeta) as Mode[]).map((m) => (
            <Button
              key={m}
              variant={mode === m ? 'primary' : 'neutral'}
              onClick={() => !modeMeta[m].disabled && setMode(m)}
              disabled={modeMeta[m].disabled}
              style={{ 
                flex: '1 1 auto', 
                minWidth: '110px', 
                padding: '10px', 
                fontSize: '13px',
                opacity: modeMeta[m].disabled ? 0.5 : 1,
                cursor: modeMeta[m].disabled ? 'not-allowed' : 'pointer'
              }}
            >
              {modeMeta[m].icon}
              {modeMeta[m].label}
            </Button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
        <h3 style={sectionTitleStyle}>{sectionTitles[mode]}</h3>

        {mode === 'category' && (
          <div>
            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle}>Catégorie prédéfinie</label>
              <select
                value={selectedCategory}
                onChange={(e) => {
                  setSelectedCategory(e.target.value)
                  if (e.target.value !== 'custom') setCategory(e.target.value)
                }}
                disabled={loadingCategories}
                style={inputStyle}
              >
                <option value="custom">Autre (personnalisé)</option>
                {predefinedCategories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            {selectedCategory === 'custom' && (
              <div style={{ marginBottom: '16px' }}>
                <label style={labelStyle}>Nom de la catégorie personnalisée</label>
                <input
                  type="text"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="Ex: Article à wikifier/Liste complète"
                  style={inputStyle}
                />
              </div>
            )}

            <p style={helpStyle}>L'analyse recherchera tous les articles de cette catégorie</p>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {maxArticlesField}
              <CheckboxRow
                id="recursive"
                checked={recursive}
                onChange={setRecursive}
                label="Inclure les sous-catégories"
              />
              {excludePublishedField('category')}
              {includeAnalyzedField('category')}
            </div>

            {retrieveButton(false)}
            {articlesRetrieved && <ArticlesRetrievedBadge count={articles.length} />}
          </div>
        )}

        {mode === 'manual' && (
          <div>
            <label style={labelStyle}>Titres d'articles (un par ligne)</label>
            <textarea
              value={manualTitles}
              onChange={(e) => setManualTitles(e.target.value)}
              placeholder={'Paris\nLondres\nBerlin'}
              rows={10}
              style={{ ...inputStyle, fontFamily: 'monospace', resize: 'vertical' }}
            />
            <p style={helpStyle}>Entrez un titre d'article par ligne</p>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {excludePublishedField('manual')}
              {includeAnalyzedField('manual')}
            </div>

            {retrieveButton(true)}
            {articlesRetrieved && <ArticlesRetrievedBadge count={articles.length} />}
          </div>
        )}

        {mode === 'petscan' && (
          <div>
            <label style={labelStyle}>PetScan ID</label>
            <input
              type="text"
              value={petScanId}
              onChange={(e) => setPetScanId(e.target.value)}
              placeholder="Ex: 123456"
              style={inputStyle}
            />
            <p style={helpStyle}>Entrez l'ID de la requête PetScan (nombre entier)</p>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {maxArticlesField}
              {excludePublishedField('petscan')}
              {includeAnalyzedField('petscan')}
            </div>

            {retrieveButton(true)}
            {articlesRetrieved && <ArticlesRetrievedBadge count={articles.length} />}
          </div>
        )}

        {mode === 'file' && (
          <div>
            <label style={labelStyle}>Chemin du fichier</label>
            <input
              type="text"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              placeholder="Ex: /path/to/articles.txt"
              style={inputStyle}
            />
            <p style={helpStyle}>
              Entrez le chemin vers un fichier contenant des titres d'articles (un par ligne)
            </p>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {maxArticlesField}
              {includeAnalyzedField('file')}
            </div>

            {retrieveButton(true)}
            {articlesRetrieved && <ArticlesRetrievedBadge count={articles.length} />}
          </div>
        )}

        {mode === 'user-contribs' && (
          <div>
            <label style={labelStyle}>Nom d'utilisateur</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Ex: Exemple"
              style={inputStyle}
            />
            <p style={helpStyle}>Entrez le nom d'utilisateur Wikipédia</p>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {maxArticlesField}
              {excludePublishedField('user')}
              {includeAnalyzedField('user')}
            </div>

            {retrieveButton(true)}
            {articlesRetrieved && <ArticlesRetrievedBadge count={articles.length} />}
          </div>
        )}

        {mode === 'article' && (
          <div>
            <label style={labelStyle}>Titre de l'article</label>
            <input
              type="text"
              value={articleTitle}
              onChange={(e) => setArticleTitle(e.target.value)}
              placeholder="Ex: Paris"
              style={inputStyle}
            />
            <p style={helpStyle}>L'analyse sera effectuée sur cet article spécifique</p>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            color: '#ef4444',
            fontSize: '13px',
            padding: '10px 12px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <AlertTriangle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          {error}
        </div>
      )}

      {/* Articles List - Only show for retrieval modes */}
      {articlesRetrieved && articles.length > 0 && isRetrievalMode && mode !== 'user-contribs' && (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ ...sectionTitleStyle, marginBottom: 0 }}>
              Articles récupérés ({articles.length})
            </h3>
            <Button variant="neutral" onClick={handleSelectAll} style={{ padding: '6px 10px', fontSize: '11px' }}>
              {selectedArticles.size === articles.length ? 'Désélectionner tout' : 'Sélectionner tout'}
            </Button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '400px', overflowY: 'auto' }}>
            {articles.map((article, index) => (
              <div
                key={article.page_id ?? `${article.title}-${index}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 12px',
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '6px',
                  gap: '12px'
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: '13px',
                      color: '#f5f5f5',
                      fontWeight: 500,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}
                  >
                    {article.title}
                  </div>
                  {article.page_id && (
                    <div style={{ fontSize: '11px', color: '#666666' }}>Page ID: {article.page_id}</div>
                  )}
                </div>
                <Button
                  variant={selectedArticles.has(article.title) ? 'primary' : 'neutral'}
                  onClick={() => handleToggleArticle(article.title)}
                  style={{ padding: '6px 10px', fontSize: '11px', flexShrink: 0 }}
                >
                  {selectedArticles.has(article.title) ? 'Sélectionné' : 'Sélectionner'}
                </Button>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '12px', fontSize: '11px', color: '#666666' }}>
            {selectedArticles.size > 0
              ? `${selectedArticles.size} article(s) sélectionné(s)`
              : 'Aucun article sélectionné'}
          </div>
        </div>
      )}

      {/* Start Button */}
      {((mode === 'article' && articleTitle.trim().length > 0) ||
        (articlesRetrieved && articles.length > 0 && mode !== 'user-contribs' && mode !== 'article')) && (
        <Button
          variant="neutral"
          onClick={handleStartAnalysis}
          disabled={analyzingSingleArticle || retrievingArticles}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center', fontSize: '13px' }}
        >
          <Search style={{ width: '14px', height: '14px' }} />
          {mode === 'article' && analyzingSingleArticle ? 'Analyse en cours...' : 
           mode === 'article' ? "Lancer l'analyse" : 
           retrievingArticles ? 'Ajout à la file...' : 
           selectedArticles.size > 0 ? `Analyser ${selectedArticles.size} article(s)` : 'Voir les articles récupérés'}
        </Button>
      )}

      {/* Warning message for disabled user-contribs mode */}
      {mode === 'user-contribs' && (
        <div style={{ 
          padding: '12px 16px', 
          backgroundColor: 'rgba(239, 68, 68, 0.1)', 
          border: '1px solid rgba(239, 68, 68, 0.3)', 
          borderRadius: '6px',
          color: '#ef4444',
          fontSize: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertTriangle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          <span>Le mode Contributions est actuellement désactivé.</span>
        </div>
      )}
    </div>
  )
}