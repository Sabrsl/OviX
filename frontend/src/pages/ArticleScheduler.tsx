import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  Play, Pause, Square, RefreshCw, Inbox, Settings, 
  CheckCircle, XCircle, Clock, AlertTriangle, Loader2, Info 
} from 'lucide-react'
import { articleSchedulerApi } from '../api/system.api'
import { articlesApi } from '../api/articles.api'

interface ArticleSchedulerConfig {
  article_count: number
  publish_automatically: boolean
  dry_run: boolean
}

interface ArticleSchedulerStatus {
  is_active: boolean
  is_paused: boolean
  session_id?: string
  total_articles: number
  processed_articles: number
  current_article?: string
  current_step?: string
  progress_percentage: number
  articles_analyzed: number
  articles_corrected: number
  articles_published: number
  articles_error: number
  started_at?: string
  estimated_completion?: string
  config?: ArticleSchedulerConfig
}

interface ArticleProgress {
  title: string
  status: string
  current_step?: string
  progress: number
  started_at?: string
  completed_at?: string
  error_message?: string
}

interface ArticleToAnalyze {
  id: string
  title: string
  page_id?: number
  revision_id?: number
  source: string
  source_details: string
  priority: string
  added_at: string
  status: string
}

// Color palette matching existing pages
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
  purple: '#8b5cf6'
} as const

export default function ArticleScheduler() {
  const navigate = useNavigate()
  
  // Scheduler state
  const [schedulerStatus, setSchedulerStatus] = useState<ArticleSchedulerStatus | null>(null)
  const [articlesToAnalyze, setArticlesToAnalyze] = useState<ArticleToAnalyze[]>([])
  const [scheduledArticles, setScheduledArticles] = useState<ArticleProgress[]>([])
  
  // UI state
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  
  // Configuration form
  const [config, setConfig] = useState<ArticleSchedulerConfig>({
    article_count: 10,
    publish_automatically: false,
    dry_run: true
  })
  
  // Fetch scheduler status
  const fetchSchedulerStatus = useCallback(async () => {
    try {
      const status = await articleSchedulerApi.getStatus()
      setSchedulerStatus(status)
    } catch (err: any) {
      console.error('Failed to fetch scheduler status:', err)
    }
  }, [])
  
  // Fetch articles to analyze
  const fetchArticlesToAnalyze = useCallback(async () => {
    try {
      const response = await articlesApi.getArticlesToAnalyze()
      if (response.success) {
        setArticlesToAnalyze(response.articles)
      }
    } catch (err: any) {
      console.error('Failed to fetch articles to analyze:', err)
    }
  }, [])
  
  // Fetch scheduled articles progress
  const fetchScheduledArticles = useCallback(async () => {
    try {
      const response = await articleSchedulerApi.getScheduledArticles()
      if (response.success) {
        setScheduledArticles(response.articles)
      }
    } catch (err: any) {
      console.error('Failed to fetch scheduled articles:', err)
    }
  }, [])
  
  // Initial data fetch
  useEffect(() => {
    const loadInitialData = async () => {
      setLoading(true)
      await Promise.all([
        fetchSchedulerStatus(),
        fetchArticlesToAnalyze()
      ])
      setLoading(false)
    }
    
    loadInitialData()
  }, [fetchSchedulerStatus, fetchArticlesToAnalyze])
  
  // Polling for real-time updates
  useEffect(() => {
    if (isPolling) {
      const interval = setInterval(() => {
        fetchSchedulerStatus()
        fetchScheduledArticles()
      }, 2000) // Poll every 2 seconds
      
      return () => clearInterval(interval)
    }
  }, [isPolling, fetchSchedulerStatus, fetchScheduledArticles])
  
  // Auto-start polling when scheduler becomes active
  useEffect(() => {
    if (schedulerStatus?.is_active && !isPolling) {
      setIsPolling(true)
    } else if (!schedulerStatus?.is_active && isPolling) {
      setIsPolling(false)
    }
  }, [schedulerStatus?.is_active, isPolling])
  
  // Start scheduler
  const handleStart = async (count: number) => {
    setActionLoading(true)
    setError(null)
    
    try {
      const startConfig = {
        ...config,
        article_count: count
      }
      
      const result = await articleSchedulerApi.start(startConfig)
      
      if (result.success) {
        setIsPolling(true)
        await fetchSchedulerStatus()
        await fetchScheduledArticles()
      } else {
        setError(result.message)
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to start scheduler')
    } finally {
      setActionLoading(false)
    }
  }
  
  // Pause scheduler
  const handlePause = async () => {
    setActionLoading(true)
    try {
      const result = await articleSchedulerApi.pause()
      if (result.success) {
        await fetchSchedulerStatus()
      } else {
        setError(result.message)
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to pause scheduler')
    } finally {
      setActionLoading(false)
    }
  }
  
  // Resume scheduler
  const handleResume = async () => {
    setActionLoading(true)
    try {
      const result = await articleSchedulerApi.resume()
      if (result.success) {
        await fetchSchedulerStatus()
      } else {
        setError(result.message)
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to resume scheduler')
    } finally {
      setActionLoading(false)
    }
  }
  
  // Stop scheduler
  const handleStop = async () => {
    if (!confirm('Êtes-vous sûr de vouloir arrêter le scheduler ?')) {
      return
    }
    
    setActionLoading(true)
    try {
      const result = await articleSchedulerApi.stop()
      if (result.success) {
        setIsPolling(false)
        await fetchSchedulerStatus()
        await fetchArticlesToAnalyze()
        setScheduledArticles([])
      } else {
        setError(result.message)
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to stop scheduler')
    } finally {
      setActionLoading(false)
    }
  }
  
  // Calculate available articles count
  const availableArticlesCount = useMemo(() => {
    return articlesToAnalyze.filter(a => a.status === 'pending').length
  }, [articlesToAnalyze])
  
  // Calculate max articles for selection
  const maxArticles = Math.min(config.article_count, availableArticlesCount)
  
  // Format date
  const formatDate = (dateString?: string) => {
    if (!dateString) return '—'
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return '—'
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }
  
  // Get status badge with coherent colors
  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; label: string; icon: any; bgColor: string }> = {
      pending: { color: '#f59e0b', label: 'En attente', icon: Clock, bgColor: 'rgba(245, 158, 11, 0.15)' },
      analyzing: { color: '#3b82f6', label: 'Analyse', icon: Loader2, bgColor: 'rgba(59, 130, 246, 0.15)' },
      corrected: { color: '#8b5cf6', label: 'Corrigé', icon: CheckCircle, bgColor: 'rgba(139, 92, 246, 0.15)' },
      ready_to_publish: { color: '#10b981', label: 'Prêt à publier', icon: CheckCircle, bgColor: 'rgba(16, 185, 129, 0.15)' },
      published: { color: '#10b981', label: 'Publié', icon: CheckCircle, bgColor: 'rgba(16, 185, 129, 0.15)' },
      dry_run: { color: '#8b5cf6', label: 'Dry Run', icon: CheckCircle, bgColor: 'rgba(139, 92, 246, 0.15)' },
      no_corrections: { color: '#6b7280', label: 'Aucune correction', icon: Clock, bgColor: 'rgba(107, 114, 128, 0.15)' },
      error: { color: '#ef4444', label: 'Erreur', icon: XCircle, bgColor: 'rgba(239, 68, 68, 0.15)' }
    }
    
    const config = statusConfig[status] || statusConfig.pending
    const Icon = config.icon
    
    return (
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '3px 8px',
        borderRadius: '6px',
        backgroundColor: config.bgColor,
        color: config.color,
        fontSize: '11px',
        fontWeight: 500,
        border: `1px solid ${config.color}30`
      }}>
        <Icon style={{ width: '12px', height: '12px' }} />
        {config.label}
      </div>
    )
  }

  // Get progress bar color based on status
  const getProgressColor = (status: string) => {
    const colorMap: Record<string, string> = {
      pending: '#f59e0b',
      analyzing: '#3b82f6',
      corrected: '#8b5cf6',
      ready_to_publish: '#10b981',
      published: '#10b981',
      dry_run: '#8b5cf6',
      no_corrections: '#6b7280',
      error: '#ef4444'
    }
    return colorMap[status] || '#f59e0b'
  }
  
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: COLORS.textPrimary }}>Scheduler</h2>
          <p style={{ color: COLORS.textSecondary, marginTop: '4px' }}>Traitement semi-automatique des articles en attente</p>
        </div>
        <SkeletonBlock />
      </div>
    )
  }
  
  const isActive = schedulerStatus?.is_active || false
  const isPaused = schedulerStatus?.is_paused || false
  
  return (
    <>
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
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
          50% { opacity: 0.5; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
        }
      `}</style>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '24px', fontWeight: 600, color: COLORS.textPrimary, margin: 0 }}>Scheduler</h2>
            <p style={{ color: COLORS.textSecondary, marginTop: '4px', fontSize: '14px' }}>
              Traitement semi-automatique des articles en attente
            </p>
          </div>
          <button
            onClick={() => {
              fetchSchedulerStatus()
              fetchArticlesToAnalyze()
            }}
            disabled={actionLoading}
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
              cursor: actionLoading ? 'not-allowed' : 'pointer',
              opacity: actionLoading ? 0.6 : 1,
              transition: 'background-color 0.15s, border-color 0.15s, color 0.15s, transform 0.1s',
            }}
            onMouseEnter={(e) => {
              if (actionLoading) return
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
            <RefreshCw style={{ width: '12px', height: '12px' }} />
            Actualiser
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 14px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: '7px',
            color: COLORS.danger,
            fontSize: '12.5px'
          }}>
            <AlertTriangle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
            {error}
          </div>
        )}

        {/* Articles Available Card */}
        <div style={{
          backgroundColor: COLORS.bgPanel,
          border: `1px solid ${COLORS.border}`,
          borderRadius: '9px',
          padding: '20px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <div>
            <div style={{ fontSize: '12px', color: COLORS.textSecondary, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>
              Articles en attente
            </div>
            <div style={{ fontSize: '36px', fontWeight: 600, color: COLORS.textPrimary, letterSpacing: '-0.02em' }}>
              {availableArticlesCount}
            </div>
            <div style={{ fontSize: '12px', color: COLORS.textMuted, marginTop: '4px' }}>
              articles disponibles
            </div>
          </div>
          
          {isActive && schedulerStatus && (
            <>
              <div>
                <div style={{ fontSize: '12px', color: COLORS.textSecondary, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>
                  Progression
                </div>
                <div style={{ fontSize: '36px', fontWeight: 600, color: COLORS.accent, letterSpacing: '-0.02em' }}>
                  {schedulerStatus.processed_articles} / {schedulerStatus.total_articles}
                </div>
                <div style={{ fontSize: '12px', color: COLORS.textMuted, marginTop: '4px' }}>
                  {schedulerStatus.progress_percentage.toFixed(0)}%
                </div>
              </div>

              <div>
                <div style={{ fontSize: '12px', color: COLORS.textSecondary, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>
                  Statut
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '8px',
                    height: '8px',
                    backgroundColor: isPaused ? COLORS.warning : COLORS.success,
                    borderRadius: '50%',
                    animation: isPaused ? 'none' : 'pulse 1.5s ease-in-out infinite'
                  }} />
                  <span style={{ fontSize: '16px', color: COLORS.textPrimary, fontWeight: 500 }}>
                    {isPaused ? 'En pause' : 'Actif'}
                  </span>
                </div>
                {schedulerStatus.current_step && (
                  <div style={{ fontSize: '12px', color: COLORS.textMuted, marginTop: '4px' }}>
                    {schedulerStatus.current_step}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Show stats even when not active if there are completed stats */}
          {!isActive && schedulerStatus && (schedulerStatus.articles_analyzed > 0 || schedulerStatus.articles_corrected > 0 || schedulerStatus.articles_published > 0 || schedulerStatus.articles_error > 0) && (
            <div style={{ gridColumn: '1 / -1', marginTop: '16px', paddingTop: '16px', borderTop: `1px solid ${COLORS.border}` }}>
              <div style={{ fontSize: '12px', color: COLORS.textSecondary, marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>
                Statistiques de la dernière session
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
                <StatCard label="Analysés" value={schedulerStatus.articles_analyzed} color={COLORS.accent} />
                <StatCard label="Corrigés" value={schedulerStatus.articles_corrected} color={COLORS.warning} />
                <StatCard label="Publiés" value={schedulerStatus.articles_published} color={COLORS.success} />
                <StatCard label="Erreurs" value={schedulerStatus.articles_error} color={COLORS.danger} />
              </div>
              <button
                onClick={() => {
                  setSchedulerStatus(null)
                }}
                style={{
                  marginTop: '12px',
                  padding: '6px 12px',
                  backgroundColor: COLORS.bgSubtle,
                  border: `1px solid ${COLORS.border}`,
                  borderRadius: '6px',
                  color: COLORS.textSecondary,
                  fontSize: '11px',
                  cursor: 'pointer',
                  transition: 'background-color 0.15s, border-color 0.15s, color 0.15s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#3a3a3a'
                  e.currentTarget.style.color = COLORS.textPrimary
                  e.currentTarget.style.backgroundColor = '#1f1f1f'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = COLORS.border
                  e.currentTarget.style.color = COLORS.textSecondary
                  e.currentTarget.style.backgroundColor = COLORS.bgSubtle
                }}
              >
                Effacer les statistiques
              </button>
            </div>
          )}
        </div>

        {/* Configuration Card */}
        {!isActive && (
          <div style={{
            backgroundColor: COLORS.bgPanel,
            border: `1px solid ${COLORS.border}`,
            borderRadius: '9px',
            padding: '20px'
          }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              marginBottom: '16px',
              fontSize: '14px',
              fontWeight: 500,
              color: COLORS.textSecondary,
              textTransform: 'uppercase',
              letterSpacing: '0.04em'
            }}>
              <Settings style={{ width: '14px', height: '14px' }} />
              Configuration
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
              {/* Article Count */}
              <div>
                <label style={{ display: 'block', fontSize: '12px', color: COLORS.textSecondary, marginBottom: '8px' }}>
                  Nombre d'articles
                </label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="number"
                    min="1"
                    max={availableArticlesCount}
                    value={config.article_count}
                    onChange={(e) => setConfig({ ...config, article_count: Math.min(Math.max(1, parseInt(e.target.value) || 1), availableArticlesCount) })}
                    disabled={availableArticlesCount === 0}
                    style={{
                      flex: 1,
                      padding: '8px 12px',
                      backgroundColor: COLORS.bgInput,
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: '6px',
                      color: COLORS.textPrimary,
                      fontSize: '14px',
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
                  <button
                    onClick={() => setConfig({ ...config, article_count: availableArticlesCount })}
                    disabled={availableArticlesCount === 0}
                    style={{
                      padding: '8px 12px',
                      backgroundColor: COLORS.bgSubtle,
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: '6px',
                      color: COLORS.textSecondary,
                      fontSize: '12px',
                      cursor: availableArticlesCount === 0 ? 'not-allowed' : 'pointer',
                      opacity: availableArticlesCount === 0 ? 0.5 : 1
                    }}
                  >
                    Tous
                  </button>
                </div>
                <div style={{ fontSize: '11px', color: COLORS.textMuted, marginTop: '4px' }}>
                  {config.article_count} articles seront traités sur {availableArticlesCount} disponibles
                </div>
              </div>
              
              {/* Publish Automatically */}
              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={config.publish_automatically}
                    onChange={(e) => setConfig({ ...config, publish_automatically: e.target.checked })}
                    style={{ cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '13px', color: COLORS.textPrimary }}>
                    Publication automatique
                  </span>
                </label>
                <div style={{ fontSize: '11px', color: COLORS.textMuted, marginTop: '4px', marginLeft: '20px' }}>
                  {config.publish_automatically 
                    ? 'Les articles validés seront publiés automatiquement' 
                    : 'Les articles seront analysés mais non publiés automatiquement'}
                </div>
              </div>
              
              {/* Dry Run */}
              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={config.dry_run}
                    onChange={(e) => setConfig({ ...config, dry_run: e.target.checked })}
                    style={{ cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '13px', color: COLORS.textPrimary }}>
                    Dry Run
                  </span>
                </label>
                <div style={{ fontSize: '11px', color: COLORS.textMuted, marginTop: '4px', marginLeft: '20px' }}>
                  {config.dry_run 
                    ? 'Aucune modification réelle sur Wikipédia' 
                    : 'Les publications seront effectives sur Wikipédia'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Active Processing Card */}
        {isActive && schedulerStatus && (
          <div style={{
            backgroundColor: COLORS.bgPanel,
            border: `1px solid ${COLORS.purple}`,
            borderRadius: '9px',
            padding: '20px'
          }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              marginBottom: '16px',
              fontSize: '14px',
              fontWeight: 500,
              color: COLORS.purple,
              textTransform: 'uppercase',
              letterSpacing: '0.04em'
            }}>
              <Loader2 style={{ width: '14px', height: '14px', animation: 'spin 1s linear infinite' }} />
              Traitement en cours
            </div>
            
            {/* Progress Bar */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{
                height: '8px',
                backgroundColor: COLORS.bgInput,
                borderRadius: '4px',
                overflow: 'hidden',
                border: `1px solid ${COLORS.border}`
              }}>
                <div style={{
                  height: '100%',
                  width: `${schedulerStatus.progress_percentage}%`,
                  backgroundColor: COLORS.accent,
                  transition: 'width 0.3s ease'
                }} />
              </div>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                fontSize: '11px', 
                color: COLORS.textMuted, 
                marginTop: '4px' 
              }}>
                <span>{schedulerStatus.progress_percentage.toFixed(0)}%</span>
                <span>{schedulerStatus.processed_articles} / {schedulerStatus.total_articles} articles</span>
              </div>
            </div>
            
            {/* Statistics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '16px' }}>
              <StatCard label="Analysés" value={schedulerStatus.articles_analyzed} color={COLORS.accent} />
              <StatCard label="Corrigés" value={schedulerStatus.articles_corrected} color={COLORS.warning} />
              <StatCard label="Publiés" value={schedulerStatus.articles_published} color={COLORS.success} />
              <StatCard label="Erreurs" value={schedulerStatus.articles_error} color={COLORS.danger} />
            </div>
            
            {/* Current Article */}
            {schedulerStatus.current_article && (
              <div style={{
                padding: '12px',
                backgroundColor: COLORS.bgInput,
                borderRadius: '6px',
                fontSize: '13px',
                color: COLORS.textSecondary
              }}>
                <span style={{ color: COLORS.textMuted }}>Article actuel: </span>
                <span style={{ color: COLORS.textPrimary, fontWeight: 500 }}>{schedulerStatus.current_article}</span>
              </div>
            )}
          </div>
        )}

        {/* Control Buttons */}
        <div style={{
          backgroundColor: COLORS.bgPanel,
          border: `1px solid ${COLORS.border}`,
          borderRadius: '9px',
          padding: '20px'
        }}>
          <div style={{ 
            fontSize: '14px',
            fontWeight: 500,
            color: COLORS.textSecondary,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: '16px'
          }}>
            Actions
          </div>
          
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {!isActive ? (
              <>
                <button
                  onClick={() => handleStart(config.article_count)}
                  disabled={actionLoading || availableArticlesCount === 0}
                  style={{
                    padding: '10px 20px',
                    backgroundColor: COLORS.accent,
                    border: 'none',
                    borderRadius: '7px',
                    color: '#ffffff',
                    fontSize: '14px',
                    fontWeight: 500,
                    cursor: (actionLoading || availableArticlesCount === 0) ? 'not-allowed' : 'pointer',
                    opacity: (actionLoading || availableArticlesCount === 0) ? 0.5 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'filter 0.15s, transform 0.1s'
                  }}
                  onMouseEnter={(e) => {
                    if (actionLoading || availableArticlesCount === 0) return
                    e.currentTarget.style.filter = 'brightness(1.1)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.filter = 'brightness(1)'
                  }}
                  onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.97)')}
                  onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                >
                  <Play style={{ width: '16px', height: '16px' }} />
                  Analyser {config.article_count} articles
                </button>
                
                <button
                  onClick={() => {
                    if (confirm(`Vous êtes sur le point de lancer l'analyse de ${availableArticlesCount} articles. Continuer ?`)) {
                      handleStart(availableArticlesCount)
                    }
                  }}
                  disabled={actionLoading || availableArticlesCount === 0}
                  style={{
                    padding: '10px 20px',
                    backgroundColor: COLORS.success,
                    border: 'none',
                    borderRadius: '7px',
                    color: '#ffffff',
                    fontSize: '14px',
                    fontWeight: 500,
                    cursor: (actionLoading || availableArticlesCount === 0) ? 'not-allowed' : 'pointer',
                    opacity: (actionLoading || availableArticlesCount === 0) ? 0.5 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    transition: 'filter 0.15s, transform 0.1s'
                  }}
                  onMouseEnter={(e) => {
                    if (actionLoading || availableArticlesCount === 0) return
                    e.currentTarget.style.filter = 'brightness(1.1)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.filter = 'brightness(1)'
                  }}
                  onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.97)')}
                  onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                >
                  <Play style={{ width: '16px', height: '16px' }} />
                  Analyser tous
                </button>
              </>
            ) : isPaused ? (
              <button
                onClick={handleResume}
                disabled={actionLoading}
                style={{
                  padding: '10px 20px',
                  backgroundColor: COLORS.success,
                  border: 'none',
                  borderRadius: '7px',
                  color: '#ffffff',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: actionLoading ? 'not-allowed' : 'pointer',
                  opacity: actionLoading ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'filter 0.15s, transform 0.1s'
                }}
                onMouseEnter={(e) => {
                  if (actionLoading) return
                  e.currentTarget.style.filter = 'brightness(1.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.filter = 'brightness(1)'
                }}
                onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.97)')}
                onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
              >
                <Play style={{ width: '16px', height: '16px' }} />
                Reprendre
              </button>
            ) : (
              <button
                onClick={handlePause}
                disabled={actionLoading}
                style={{
                  padding: '10px 20px',
                  backgroundColor: COLORS.warning,
                  border: 'none',
                  borderRadius: '7px',
                  color: '#ffffff',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: actionLoading ? 'not-allowed' : 'pointer',
                  opacity: actionLoading ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'filter 0.15s, transform 0.1s'
                }}
                onMouseEnter={(e) => {
                  if (actionLoading) return
                  e.currentTarget.style.filter = 'brightness(1.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.filter = 'brightness(1)'
                }}
                onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.97)')}
                onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
              >
                <Pause style={{ width: '16px', height: '16px' }} />
                Pause
              </button>
            )}
            
            {isActive && (
              <button
                onClick={handleStop}
                disabled={actionLoading}
                style={{
                  padding: '10px 20px',
                  backgroundColor: COLORS.danger,
                  border: 'none',
                  borderRadius: '7px',
                  color: '#ffffff',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: actionLoading ? 'not-allowed' : 'pointer',
                  opacity: actionLoading ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'filter 0.15s, transform 0.1s'
                }}
                onMouseEnter={(e) => {
                  if (actionLoading) return
                  e.currentTarget.style.filter = 'brightness(1.1)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.filter = 'brightness(1)'
                }}
                onMouseDown={(e) => (e.currentTarget.style.transform = 'scale(0.97)')}
                onMouseUp={(e) => (e.currentTarget.style.transform = 'scale(1)')}
              >
                <Square style={{ width: '16px', height: '16px' }} />
                Arrêter
              </button>
            )}
          </div>
        </div>

        {/* Articles Progress List */}
        {isActive && scheduledArticles.length > 0 && (
          <div style={{
            backgroundColor: COLORS.bgPanel,
            border: `1px solid ${COLORS.border}`,
            borderRadius: '9px',
            padding: '20px'
          }}>
            <div style={{ 
              fontSize: '14px',
              fontWeight: 500,
              color: COLORS.textSecondary,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: '16px'
            }}>
              Progression des articles
            </div>
            
            {/* Mode Indicators - Small badges */}
            {schedulerStatus && (
              <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                {schedulerStatus.config?.publish_automatically && (
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '3px 8px',
                    backgroundColor: 'rgba(16, 185, 129, 0.15)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    borderRadius: '4px',
                    color: '#10b981',
                    fontSize: '10px',
                    fontWeight: 500
                  }}>
                    <CheckCircle style={{ width: '10px', height: '10px' }} />
                    Auto
                  </div>
                )}
                {schedulerStatus.config?.dry_run && (
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '3px 8px',
                    backgroundColor: 'rgba(139, 92, 246, 0.15)',
                    border: '1px solid rgba(139, 92, 246, 0.3)',
                    borderRadius: '4px',
                    color: '#8b5cf6',
                    fontSize: '10px',
                    fontWeight: 500
                  }}>
                    <AlertTriangle style={{ width: '10px', height: '10px' }} />
                    Dry Run
                  </div>
                )}
              </div>
            )}
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {scheduledArticles.map((article, index) => (
                <div
                  key={article.title || index}
                  style={{
                    padding: '12px 14px',
                    backgroundColor: COLORS.bgInput,
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    animation: `fadeInUp 0.3s ease-out ${Math.min(index * 50, 300)}ms both`
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: '14px',
                      color: COLORS.textPrimary,
                      fontWeight: 500,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      marginBottom: '4px'
                    }}>
                      {article.title}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: COLORS.textMuted }}>
                      {getStatusBadge(article.status)}
                      <span>Progress: {article.progress.toFixed(0)}%</span>
                    </div>
                  </div>
                  
                  {/* Progress Bar */}
                  <div style={{ width: '100px', height: '4px', backgroundColor: COLORS.bgSubtle, borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${article.progress}%`,
                      backgroundColor: getProgressColor(article.status),
                      transition: 'width 0.3s ease'
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!isActive && availableArticlesCount === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '48px 20px',
            color: COLORS.textSecondary,
            backgroundColor: COLORS.bgPanel,
            border: `1px dashed ${COLORS.border}`,
            borderRadius: '9px',
            animation: 'fadeIn 0.3s ease-out'
          }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                backgroundColor: COLORS.bgSubtle,
                border: `1px solid ${COLORS.border}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px'
              }}
            >
              <Inbox style={{ width: '20px', height: '20px', color: COLORS.textMuted }} />
            </div>
            <div style={{ marginBottom: '8px', fontSize: '15px', fontWeight: 500, color: COLORS.textPrimary }}>
              Aucun article en attente
            </div>
            <div style={{ fontSize: '12px', color: COLORS.textMuted }}>
              Ajoutez des articles à la file d'analyse pour commencer le traitement
            </div>
          </div>
        )}
      </div>
    </>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  // Simple approach using opacity with background color
  return (
    <div style={{
      backgroundColor: 'rgba(255, 255, 255, 0.05)',
      borderRadius: '6px',
      padding: '12px',
      border: `1px solid ${color}40`,
      boxShadow: `0 0 0 1px ${color}10`
    }}>
      <div style={{ fontSize: '11px', color: COLORS.textMuted, marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: '20px', fontWeight: 600, color, letterSpacing: '-0.01em' }}>
        {value}
      </div>
    </div>
  )
}

function SkeletonBlock() {
  return (
    <div style={{ 
      height: '200px', 
      backgroundColor: COLORS.bgPanel, 
      border: `1px solid ${COLORS.border}`, 
      borderRadius: '9px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      animation: 'pulse 1.5s ease-in-out infinite'
    }}>
      <div style={{ color: COLORS.textMuted, fontSize: '14px' }}>Chargement...</div>
    </div>
  )
}