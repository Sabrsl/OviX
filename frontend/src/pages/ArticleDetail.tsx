import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  RefreshCw,
  Edit,
  Trash2,
  ExternalLink,
  Hash,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertTriangle,
  Save,
  X,
  Link,
  Eye,
} from 'lucide-react'
import { historyApi } from '../api/history.api'
import { diffApi } from '../api/diff.api'
import { publicationApi } from '../api/publication.api'
import { articlesApi } from '../api/articles.api'
import { AnalyzerBadges } from '../components/AnalyzerBadges'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ArticleStatus = 'pending' | 'analyzed' | 'published' | string

interface ArticleInfo {
  title: string
  status: ArticleStatus
  analysis_date: string
  mode: string
  changes_count: number
  character_count?: number
  total_links?: number
  dead_links_count?: number
  corrected_links_count?: number
  human_verified?: boolean
  summary?: string
  normalization_changes_count?: number
  normalization_ignored_count?: number
  normalization_reports?: string
  analyzers_status?: Record<string, string>
  typo_corrections_count?: number
}

interface ArticleListItem {
  title?: string
  article_title?: string
  job_id?: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message
  if (typeof err === 'object' && err !== null) {
    const anyErr = err as any
    if (typeof anyErr.userMessage === 'string') return anyErr.userMessage
    if (typeof anyErr.message === 'string') return anyErr.message
  }
  return fallback
}

function getWikipediaUrl(title: string) {
  return `https://fr.wikipedia.org/wiki/${encodeURIComponent(title)}`
}

function formatCharacterCount(count: number) {
  return count.toLocaleString('fr-FR')
}

function formatDate(iso?: string) {
  if (!iso) return 'N/A'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'N/A'
  return d.toLocaleString('fr-FR')
}

function statusLabel(status: ArticleStatus) {
  switch (status) {
    case 'published':
      return 'Publié'
    case 'analyzed':
      return 'Analysé'
    default:
      return 'En attente'
  }
}

// ---------------------------------------------------------------------------
// Small presentational pieces
// ---------------------------------------------------------------------------

function InfoCard({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-6">
      <h3 className="mb-3 text-[11px] font-medium uppercase tracking-wider text-neutral-500">
        {title}
      </h3>
      {children}
    </div>
  )
}

function StatPill({ label, value, accent, statusColor }: { label: string; value: React.ReactNode; accent?: boolean; statusColor?: 'green' | 'blue' | 'amber' | 'purple' }) {
  const colorClass = statusColor === 'green' ? 'text-green-500' :
                      statusColor === 'blue' ? 'text-blue-500' :
                      statusColor === 'amber' ? 'text-amber-500' :
                      statusColor === 'purple' ? 'text-purple-500' :
                      accent ? 'text-blue-500' : 'text-neutral-100'
  return (
    <div>
      <div className="mb-1 text-[11px] text-neutral-500">{label}</div>
      <div className={`text-xs font-medium ${colorClass}`}>
        {value}
      </div>
    </div>
  )
}

function NavButton({
  direction,
  onClick,
  disabled,
}: {
  direction: 'prev' | 'next'
  onClick: () => void
  disabled: boolean
}) {
  const Icon = direction === 'prev' ? ChevronLeft : ChevronRight
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={direction === 'prev' ? 'Article précédent' : 'Article suivant'}
      className={`flex items-center gap-1.5 rounded-md border border-neutral-800 px-2.5 py-1.5 text-xs transition-colors
        ${disabled ? 'cursor-not-allowed text-neutral-600' : 'cursor-pointer text-neutral-300 hover:bg-neutral-800'}
        bg-neutral-900`}
    >
      {direction === 'prev' && <Icon className="h-4 w-4" />}
      {direction === 'prev' ? 'Précédent' : 'Suivant'}
      {direction === 'next' && <Icon className="h-4 w-4" />}
    </button>
  )
}

function PageShell({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-6 duration-200 animate-in fade-in">{children}</div>
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 text-sm text-neutral-400 transition-colors hover:text-neutral-200"
    >
      <ArrowLeft className="h-5 w-5" />
      Retour
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ArticleDetail() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const articleTitle = searchParams.get('title')
  const jobId = searchParams.get('jobId')

  const [article, setArticle] = useState<ArticleInfo | null>(null)
  const [originalContent, setOriginalContent] = useState('')
  const [correctedContent, setCorrectedContent] = useState('')
  const [diffHtml, setDiffHtml] = useState('')

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [isPublished, setIsPublished] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [dryRun, setDryRun] = useState(true)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [reanalyzing, setReanalyzing] = useState(false)
  const [ignoring, setIgnoring] = useState(false)
  const [regeneratingDiff, setRegeneratingDiff] = useState(false)
  const [togglingVerified, setTogglingVerified] = useState(false)

  const [characterCount, setCharacterCount] = useState(0)
  const [articlesList, setArticlesList] = useState<ArticleListItem[]>([])
  const [currentIndex, setCurrentIndex] = useState(-1)

  // Manual edit mode: unlocks the wikicode textarea in place instead of navigating away.
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)

  // Edit summary for publication
  const [editSummary, setEditSummary] = useState('Correction de liens morts via OVIX')
  const [isEditingSummary, setIsEditingSummary] = useState(false)
  const [tempSummary, setTempSummary] = useState('')

  const handleStartEditSummary = () => {
    setTempSummary(editSummary)
    setIsEditingSummary(true)
  }

  const handleSaveSummary = async () => {
    if (!articleTitle) return
    try {
      await articlesApi.updateArticleSummary(articleTitle, tempSummary)
      setEditSummary(tempSummary)
      setIsEditingSummary(false)
    } catch (err) {
      console.error('Failed to save summary:', err)
      alert('Erreur lors de l\'enregistrement du résumé')
    }
  }

  const handleCancelSummary = () => {
    setTempSummary(editSummary)
    setIsEditingSummary(false)
  }

  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!articleTitle) {
      setLoading(false)
      setError("Aucun titre d'article fourni.")
      return
    }
    fetchArticleDetails(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [articleTitle, jobId])

  useEffect(() => {
    const diffContent = document.querySelector('.diff-content')
    if (!diffContent) return

    const handleClick = (e: Event) => {
      const target = e.target as HTMLElement
      if (!target.classList.contains('copy-url-btn')) return
      e.preventDefault()
      e.stopPropagation()
      const url = target.getAttribute('data-url')
      if (!url) return

      navigator.clipboard
        .writeText(url)
        .then(() => {
          const originalText = target.textContent
          target.textContent = '✓'
          target.style.backgroundColor = 'rgba(16, 185, 129, 0.4)'
          setTimeout(() => {
            target.textContent = originalText
            target.style.backgroundColor = ''
          }, 1000)
        })
        .catch((err) => {
          console.error('Failed to copy URL:', err)
        })
    }

    diffContent.addEventListener('click', handleClick)
    return () => diffContent.removeEventListener('click', handleClick)
  }, [diffHtml])

  const fetchFromAnalyzedTracker = useCallback(async (title: string) => {
    try {
      // Try to get data from SQLite database via analysis results endpoint
      const response = await fetch(`/api/articles/results/${encodeURIComponent(title)}`)
      if (response.ok) {
        const data = await response.json()
        
        if (data && data.original_content && data.corrected_content) {
          setOriginalContent(data.original_content)
          setCorrectedContent(data.corrected_content)
          setCharacterCount(data.character_count || data.original_content.length)

          try {
            const diff = await diffApi.generateDiff({
              original: data.original_content,
              corrected: data.corrected_content,
              diff_type: 'html',
            })
            setDiffHtml(diff.html_diff || diff.diff || '')
          } catch (err) {
            console.error('Failed to generate diff:', err)
          }

          // Parse analyzers_status (now contains analysis config) if it's a JSON string
          let parsedAnalysisConfig = data.analyzers_status
          if (typeof data.analyzers_status === 'string') {
            try {
              parsedAnalysisConfig = JSON.parse(data.analyzers_status)
            } catch (e) {
              console.error('Failed to parse analyzers_status:', e)
              parsedAnalysisConfig = null
            }
          }

          setArticle({
            title,
            status: data.status || 'analyzed',
            analysis_date: data.analysis_date || new Date().toISOString(),
            mode: data.mode || 'unknown',
            changes_count: data.changes_count || 0,
            character_count: data.character_count || 0,
            total_links: data.total_links,
            dead_links_count: data.dead_links_count,
            corrected_links_count: data.corrected_links_count,
            human_verified: data.human_verified,
            summary: data.summary,
            normalization_changes_count: data.normalization_changes_count,
            normalization_ignored_count: data.normalization_ignored_count,
            normalization_reports: data.normalization_reports,
            analyzers_status: parsedAnalysisConfig,
            typo_corrections_count: data.typo_corrections_count,
          })
          setEditSummary(data.summary || 'Correction de liens morts via OVIX')
          return
        }
      }

      // Fallback to old API if SQLite endpoint fails
      const result = await articlesApi.getArticleAnalysisResult(title)

      if (!result.success) {
        setArticle({
          title,
          status: 'pending',
          analysis_date: new Date().toISOString(),
          mode: 'unknown',
          changes_count: 0,
          normalization_changes_count: 0,
          normalization_ignored_count: 0,
        })
        return
      }

      if (result.corrected_content) {
        setCorrectedContent(result.corrected_content)
        setCharacterCount(result.character_count || 0)

        let original = result.original_content as string | undefined

        if (!original) {
          try {
            const articleData = await articlesApi.getArticleContent(title)
            original = articleData?.content
          } catch (err) {
            console.error('Failed to fetch original content from Wikipedia:', err)
          }
        }

        if (original) {
          setOriginalContent(original)
          try {
            const diff = await diffApi.generateDiff({
              original,
              corrected: result.corrected_content,
              diff_type: 'html',
            })
            setDiffHtml(diff.html_diff || diff.diff || '')
          } catch (err) {
            console.error('Failed to generate diff:', err)
          }
        }

        // Parse analyzers_status (now contains analysis config) if it's a JSON string
        let parsedAnalysisConfig = result.analyzers_status
        if (typeof result.analyzers_status === 'string') {
          try {
            parsedAnalysisConfig = JSON.parse(result.analyzers_status)
          } catch (e) {
            console.error('Failed to parse analyzers_status:', e)
            parsedAnalysisConfig = null
          }
        }

        setArticle({
          title,
          status: result.status || 'analyzed',
          analysis_date: result.analysis_date || new Date().toISOString(),
          mode: result.mode || 'unknown',
          changes_count: result.changes_count || 0,
          character_count: result.character_count || 0,
          total_links: result.total_links,
          dead_links_count: result.dead_links_count,
          corrected_links_count: result.corrected_links_count,
          human_verified: result.human_verified,
          normalization_changes_count: result.normalization_changes_count,
          normalization_ignored_count: result.normalization_ignored_count,
          normalization_reports: result.normalization_reports,
          analyzers_status: parsedAnalysisConfig,
          typo_corrections_count: result.typo_corrections_count,
        })
        setEditSummary(result.summary || 'Correction de liens morts via OVIX')
      } else {
        setArticle({
          title,
          status: result.status || 'pending',
          analysis_date: result.analysis_date || new Date().toISOString(),
          mode: result.mode || 'unknown',
          changes_count: result.changes_count || 0,
          character_count: result.character_count || 0,
          normalization_changes_count: result.normalization_changes_count,
          normalization_ignored_count: result.normalization_ignored_count,
          normalization_reports: result.normalization_reports,
        })
        setEditSummary(result.summary || 'Correction de liens morts via OVIX')
      }
    } catch (err) {
      console.error('Failed to fetch from AnalyzedTracker:', err)
      setArticle({
        title,
        status: 'pending',
        analysis_date: new Date().toISOString(),
        mode: 'unknown',
        changes_count: 0,
        normalization_changes_count: 0,
        normalization_ignored_count: 0,
      })
    }
  }, [])

  const fetchArticleDetails = useCallback(async (isInitial = false) => {
    if (!articleTitle) return

    const requestId = ++requestIdRef.current
    if (isInitial) {
      setLoading(true)
    }
    setError(null)
    setActionError(null)

    try {
      try {
        const analyzedHistory = await historyApi.getAnalyzedHistory()
        const normalizedItems: ArticleListItem[] = (analyzedHistory.items || []).map((item: any) => ({
          ...item,
          title: item.title || item.article_title,
        }))
        if (requestId !== requestIdRef.current) return
        setArticlesList(normalizedItems)
        const index = normalizedItems.findIndex(
          (item) => (item.title || item.article_title) === articleTitle
        )
        setCurrentIndex(index)
      } catch (err) {
        console.error('Failed to fetch articles list:', err)
      }

      try {
        const publishedHistory = await historyApi.getPublishedHistory()
        const publishedSet = new Set(publishedHistory.items?.map((item: any) => item.title) || [])
        if (requestId !== requestIdRef.current) return
        setIsPublished(publishedSet.has(articleTitle))
      } catch (err) {
        console.error('Failed to fetch published history:', err)
      }

      if (jobId) {
        try {
          const { analysisApi } = await import('../api/analysis.api')
          const results = await analysisApi.getAnalysisResults(jobId)
          if (requestId !== requestIdRef.current) return

          setOriginalContent(results.original_content || '')
          setCorrectedContent(results.corrected_content || '')

          const content = results.original_content || results.corrected_content || ''
          setCharacterCount(content.length)

          if (results.original_content && results.corrected_content) {
            try {
              const diff = await diffApi.generateDiff({
                original: results.original_content,
                corrected: results.corrected_content,
                diff_type: 'html',
              })
              if (requestId !== requestIdRef.current) return
              setDiffHtml(diff.diff || diff.html_diff || '')
            } catch (err) {
              console.error('Failed to generate diff:', err)
            }
          }

          setArticle({
            title: articleTitle,
            status: 'analyzed',
            analysis_date: new Date().toISOString(),
            mode: 'api',
            changes_count: results.successful_repairs || 0,
            character_count: content.length,
            normalization_changes_count: results.normalization_changes_count,
            normalization_ignored_count: results.normalization_ignored_count,
            normalization_reports: results.normalization_reports,
          })
          setEditSummary((results as any).summary || 'Correction de liens morts via OVIX')
        } catch (err) {
          console.error('Failed to fetch analysis results:', err)
          await fetchFromAnalyzedTracker(articleTitle)
        }
      } else {
        await fetchFromAnalyzedTracker(articleTitle)
      }
    } catch (err) {
      if (requestId !== requestIdRef.current) return
      setError(getErrorMessage(err, "Erreur lors de la récupération des détails de l'article"))
    } finally {
      if (requestId === requestIdRef.current && isInitial) setLoading(false)
    }
  }, [articleTitle, jobId, fetchFromAnalyzedTracker])

  const handlePublish = async () => {
    if (!articleTitle || !correctedContent || publishing) return

    if (dryRun) {
      setActionError(null)
      setPublishing(true)
      try {
        await publicationApi.validatePublication({
          article_title: articleTitle,
          corrected_content: correctedContent,
          original_content: originalContent,
          summary: editSummary,
          dry_run: true,
        })
        alert('Dry-run effectué avec succès')
      } catch (err: any) {
        // Don't show error for kill switch warnings during dry-run
        if (err.message && err.message.includes('Kill switch')) {
          alert('Dry-run effectué (Kill switch activé mais non bloquant pour dry-run)')
        } else {
          setActionError('Erreur lors de la publication : ' + getErrorMessage(err, 'erreur inconnue'))
        }
      } finally {
        setPublishing(false)
      }
    } else {
      setShowConfirmDialog(true)
    }
  }

  const executePublish = async () => {
    if (!articleTitle || !correctedContent || publishing) return

    setActionError(null)
    setPublishing(true)
    try {
      const result = await publicationApi.publish({
        article_title: articleTitle,
        corrected_content: correctedContent,
        original_content: originalContent,
        summary: editSummary,
        dry_run: false,
      })

      if (result.success && result.publication_id) {
        // Use SSE to receive real-time updates
        const cleanup = publicationApi.streamPublicationStatus(
          result.publication_id,
          (data) => {
            console.log('Publication status update:', data)

            if (data.error) {
              setActionError('Erreur lors de la publication : ' + data.error)
              setPublishing(false)
              return
            }

            if (data.status === 'completed') {
              setIsPublished(true)
              alert('Article publié avec succès')
              setShowConfirmDialog(false)
              fetchArticleDetails() // Refresh to get updated data
              setPublishing(false)
              cleanup()
            } else if (data.status === 'failed') {
              setActionError('Erreur lors de la publication : ' + (data.error || data.message || 'erreur inconnue'))
              setPublishing(false)
              cleanup()
            }
          },
          (error) => {
            console.error('SSE error:', error)
            setActionError('Erreur de connexion au serveur de publication')
            setPublishing(false)
          }
        )

        // Cleanup on unmount or if component is destroyed
        return cleanup
      } else {
        // Show detailed error message from API
        const errorMsg = result.message || 'Échec de la publication'
        setActionError('Erreur lors de la publication : ' + errorMsg)
        setPublishing(false)
      }
    } catch (err: any) {
      // Don't show error for kill switch warnings during publication
      if (err.message && err.message.includes('Kill switch')) {
        setActionError('Publication bloquée par le Kill Switch')
      } else {
        setActionError('Erreur lors de la publication : ' + getErrorMessage(err, 'erreur inconnue'))
      }
      setPublishing(false)
    }
  }

  const handleRegenerateDiff = async () => {
    if (!originalContent || !correctedContent || regeneratingDiff) return
    setRegeneratingDiff(true)
    setActionError(null)
    try {
      const diff = await diffApi.generateDiff({
        original: originalContent,
        corrected: correctedContent,
        diff_type: 'html',
      })
      setDiffHtml(diff.html_diff || diff.diff || '')
    } catch (err) {
      setActionError('Erreur lors de la génération du diff : ' + getErrorMessage(err, 'erreur inconnue'))
    } finally {
      setRegeneratingDiff(false)
    }
  }

  const handleReanalyze = async () => {
    if (!articleTitle || reanalyzing) return
    setReanalyzing(true)
    setActionError(null)
    try {
      const response = await articlesApi.analyzeArticle(articleTitle, 'regex')
      
      // Poll for analysis completion if we got a job_id
      if (response.job_id) {
        const { analysisApi } = await import('../api/analysis.api')
        let attempts = 0
        const maxAttempts = 60 // 5 minutes max (60 * 5 seconds)
        
        while (attempts < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, 5000)) // Wait 5 seconds
          
          try {
            const jobStatus = await analysisApi.getAnalysisStatus(response.job_id)
            if (jobStatus.status === 'completed' || jobStatus.status === 'failed') {
              break
            }
          } catch (err) {
            console.error('Failed to check job status:', err)
            break
          }
          
          attempts++
        }
      }
      
      await fetchArticleDetails()
    } catch (err) {
      setActionError("Erreur lors de l'analyse : " + getErrorMessage(err, 'erreur inconnue'))
    } finally {
      setReanalyzing(false)
    }
  }

  const handleIgnore = async () => {
    if (!articleTitle || ignoring) return
    if (!window.confirm(`Ignorer définitivement « ${articleTitle} » ?`)) return
    setIgnoring(true)
    setActionError(null)
    try {
      await articlesApi.ignoreArticle(articleTitle)
      navigate(-1)
    } catch (err) {
      setActionError("Erreur lors de l'ignor : " + getErrorMessage(err, 'erreur inconnue'))
      setIgnoring(false)
    }
  }

  const handleToggleVerified = async () => {
    if (!articleTitle || togglingVerified) return
    setTogglingVerified(true)
    setActionError(null)
    try {
      const response = await articlesApi.toggleHumanVerified(articleTitle)
      if (response.success) {
        await fetchArticleDetails()
      }
    } catch (err) {
      setActionError("Erreur lors du changement de statut : " + getErrorMessage(err, 'erreur inconnue'))
    } finally {
      setTogglingVerified(false)
    }
  }

  // Unlocks the wikicode editing area in place (no navigation away).
  const handleStartManualEdit = () => {
    setEditedContent(correctedContent || originalContent || '')
    setActionError(null)
    setIsEditing(true)
  }

  const handleCancelManualEdit = () => {
    setIsEditing(false)
    setEditedContent('')
  }

  // Saves the manually edited wikicode as the corrected content and
  // regenerates the diff, without leaving the page.
  const handleSaveManualEdit = async () => {
    if (!articleTitle || savingEdit) return
    setSavingEdit(true)
    setActionError(null)
    try {
      if (typeof (articlesApi as any).updateArticleContent === 'function') {
        await (articlesApi as any).updateArticleContent(articleTitle, editedContent)
      }

      setCorrectedContent(editedContent)
      setCharacterCount(editedContent.length)

      if (originalContent) {
        try {
          const diff = await diffApi.generateDiff({
            original: originalContent,
            corrected: editedContent,
            diff_type: 'html',
          })
          setDiffHtml(diff.html_diff || diff.diff || '')
        } catch (err) {
          console.error('Failed to regenerate diff after manual edit:', err)
        }
      }

      setIsEditing(false)
    } catch (err) {
      setActionError("Erreur lors de l'enregistrement : " + getErrorMessage(err, 'erreur inconnue'))
    } finally {
      setSavingEdit(false)
    }
  }

  const goToArticle = (item: ArticleListItem) => {
    const params = new URLSearchParams()
    params.set('title', item.title || item.article_title || '')
    // Only pass job_id if it's a real migrated job ID (starts with 'migrated_')
    if (item.job_id && item.job_id.startsWith('migrated_')) {
      params.set('jobId', item.job_id)
    }
    navigate(`/article/detail?${params.toString()}`)
  }

  const handlePreviousArticle = () => {
    if (currentIndex > 0) goToArticle(articlesList[currentIndex - 1])
  }

  const handleNextArticle = () => {
    if (currentIndex < articlesList.length - 1) goToArticle(articlesList[currentIndex + 1])
  }

  const displayedCharCount = useMemo(
    () => (characterCount > 0 ? characterCount : originalContent.length),
    [characterCount, originalContent.length]
  )

  const editedCharCount = editedContent.length

  // -------------------------------------------------------------------------
  // Render states
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <PageShell>
        <BackButton onClick={() => navigate(-1)} />
        <div className="flex items-center justify-center gap-3 rounded-lg border border-neutral-800 bg-neutral-900 p-12 text-sm text-neutral-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Chargement...
        </div>
      </PageShell>
    )
  }

  if (error) {
    return (
      <PageShell>
        <BackButton onClick={() => navigate(-1)} />
        <div className="flex flex-col items-center gap-3 rounded-lg border border-red-900/40 bg-neutral-900 p-12 text-center text-sm">
          <AlertTriangle className="h-6 w-6 text-red-500" />
          <div className="text-red-400">{error}</div>
          <button
            type="button"
            onClick={() => fetchArticleDetails()}
            className="mt-2 flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-800 px-3.5 py-2 text-xs text-neutral-200 hover:bg-neutral-700"
          >
            <RefreshCw className="h-4 w-4" />
            Réessayer
          </button>
        </div>
      </PageShell>
    )
  }

  if (!article) {
    return (
      <PageShell>
        <BackButton onClick={() => navigate(-1)} />
        <div className="flex justify-center rounded-lg border border-neutral-800 bg-neutral-900 p-12 text-sm text-neutral-500">
          Article non trouvé
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <BackButton onClick={() => navigate(-1)} />
          <div>
            <h2 className="text-lg font-semibold text-neutral-100">{articleTitle}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-4">
              <p className="text-xs text-neutral-400">Détails de l'article analysé</p>
              {characterCount > 0 && (
                <div className="flex items-center gap-1 text-[11px] text-neutral-500">
                  <Hash className="h-3.5 w-3.5" />
                  {formatCharacterCount(characterCount)} caractères
                </div>
              )}
              {article.total_links !== undefined && article.total_links !== null && (
                <div className="flex items-center gap-1 text-[11px] text-neutral-500">
                  <Link className="h-3.5 w-3.5" />
                  {article.total_links} liens
                </div>
              )}
              {article.dead_links_count !== undefined && article.dead_links_count !== null && (
                <div className="flex items-center gap-1 text-[11px] text-red-500">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {article.dead_links_count} liens morts
                </div>
              )}
              {article.corrected_links_count !== undefined && article.corrected_links_count !== null && (
                <div className="flex items-center gap-1 text-[11px] text-emerald-500">
                  <CheckCircle className="h-3.5 w-3.5" />
                  {article.corrected_links_count} liens corrigés
                </div>
              )}
              {article.human_verified !== undefined && article.human_verified !== null && (
                <div className={`flex items-center gap-1 text-[11px] ${article.human_verified ? 'text-blue-500' : 'text-neutral-500'}`}>
                  <Eye className="h-3.5 w-3.5" />
                  {article.human_verified ? 'Vérifié par humain' : 'Non vérifié'}
                  <button
                    type="button"
                    onClick={handleToggleVerified}
                    disabled={togglingVerified || isPublished}
                    className="ml-1 text-[9px] text-neutral-400 hover:text-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Basculer le statut de vérification"
                  >
                    {togglingVerified ? '...' : '✎'}
                  </button>
                </div>
              )}
              {article.normalization_changes_count !== undefined && article.normalization_changes_count !== null && article.normalization_changes_count > 0 && (
                <div className="flex items-center gap-1 text-[11px] text-purple-500">
                  <CheckCircle className="h-3.5 w-3.5" />
                  {article.normalization_changes_count} normalisations appliquées
                </div>
              )}
              {article.typo_corrections_count !== undefined && article.typo_corrections_count !== null && article.typo_corrections_count > 0 && (
                <div className="flex items-center gap-1 text-[11px] text-blue-500">
                  <CheckCircle className="h-3.5 w-3.5" />
                  {article.typo_corrections_count} corrections typo (XML)
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {articlesList.length > 1 && (
            <div className="flex items-center gap-2">
              <NavButton direction="prev" onClick={handlePreviousArticle} disabled={currentIndex <= 0} />
              <NavButton
                direction="next"
                onClick={handleNextArticle}
                disabled={currentIndex < 0 || currentIndex >= articlesList.length - 1}
              />
            </div>
          )}

          <a
            href={getWikipediaUrl(articleTitle!)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-md bg-blue-500/10 px-3 py-1.5 text-xs text-blue-500 transition-colors hover:bg-blue-500/20"
          >
            <ExternalLink className="h-4 w-4" />
            Voir sur Wikipédia
          </a>

          <span className={`flex items-center gap-2 text-xs font-medium ${
            article.status === 'published' ? 'text-green-500' :
            article.status === 'analyzed' ? 'text-blue-500' :
            'text-amber-500'
          }`}>
            <Clock className="h-4 w-4" />
            {statusLabel(article.status)}
          </span>
        </div>

        {article.analyzers_status && Object.keys(article.analyzers_status).length > 0 && (
          <div className="mt-2">
            <AnalyzerBadges analysisConfig={article.analyzers_status} typoCorrectionsCount={article.typo_corrections_count} />
          </div>
        )}
      </div>

      {actionError && (
        <div className="flex items-start gap-2 rounded-lg border border-red-900/40 bg-red-950/30 p-3 text-xs text-red-400">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Article Info */}
      <InfoCard title="Informations">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {(characterCount > 0 || originalContent.length > 0) && (
            <StatPill label="Caractères" value={formatCharacterCount(displayedCharCount)} accent />
          )}
          <StatPill label="Statut" value={statusLabel(article.status)} statusColor={
            article.status === 'published' ? 'green' :
            article.status === 'analyzed' ? 'blue' :
            'amber'
          } />
          <StatPill label="Date d'analyse" value={formatDate(article.analysis_date)} />
          <StatPill label="Type de correction" value={article.mode === 'ia' ? 'IA' : article.mode === 'regex' ? 'Règles' : article.mode || 'Règles'} />
          <StatPill label="Modifications" value={article.corrected_links_count ?? 0} />
          {article.normalization_changes_count !== undefined && article.normalization_changes_count !== null && article.normalization_changes_count > 0 && (
            <StatPill label="Normalisations" value={article.normalization_changes_count} statusColor="purple" />
          )}
          {article.typo_corrections_count !== undefined && article.typo_corrections_count !== null && article.typo_corrections_count > 0 && (
            <StatPill label="Corrections typo (XML)" value={article.typo_corrections_count} statusColor="blue" />
          )}
          {article.normalization_ignored_count !== undefined && article.normalization_ignored_count !== null && article.normalization_ignored_count > 0 && (
            <StatPill label="Normalisations ignorées" value={article.normalization_ignored_count} statusColor="amber" />
          )}
        </div>
      </InfoCard>

      {/* Normalization Details */}
      {article.normalization_reports && (
        <InfoCard title="Détails des normalisations">
          <div className="max-h-[300px] overflow-auto rounded-md border border-neutral-800 bg-black p-4 text-xs">
            {(() => {
              try {
                const reports = JSON.parse(article.normalization_reports)
                return reports.map((report: any, index: number) => (
                  <div key={index} className="mb-4 last:mb-0">
                    <div className="mb-2 font-medium text-purple-400">
                      {report.template_name}
                    </div>
                    {report.parameter_changes && Object.keys(report.parameter_changes).length > 0 && (
                      <div className="mb-2">
                        <div className="mb-1 text-neutral-500">Paramètres modifiés:</div>
                        {Object.entries(report.parameter_changes).map(([param, changes]: [string, any]) => {
                          const [before, after] = Array.isArray(changes) ? changes : [changes, changes]
                          return (
                            <div key={param} className="mb-1 text-neutral-300">
                              <span className="text-red-400">{before}</span>
                              <span className="mx-1 text-neutral-500">→</span>
                              <span className="text-green-400">{after}</span>
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {report.ignored_occurrences && report.ignored_occurrences.length > 0 && (
                      <div>
                        <div className="mb-1 text-neutral-500">Paramètres ignorés:</div>
                        {report.ignored_occurrences.map(([param, reason]: [string, string], idx: number) => (
                          <div key={idx} className="mb-1 text-neutral-400">
                            {param}: <span className="text-neutral-500">{reason}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              } catch (e) {
                return <div className="text-red-400">Erreur lors de l'affichage des rapports de normalisation</div>
              }
            })()}
          </div>
        </InfoCard>
      )}

      {/* Manual wikicode edit — unlocked in place, no navigation away */}
      {isEditing && (
        <InfoCard title="Modification manuelle du wikicode">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-1 text-[11px] text-neutral-500">
              <Hash className="h-3.5 w-3.5" />
              {formatCharacterCount(editedCharCount)} caractères
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCancelManualEdit}
                disabled={savingEdit}
                className="flex items-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-800 px-3 py-1.5 text-[11px] text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" />
                Annuler
              </button>
              <button
                type="button"
                onClick={handleSaveManualEdit}
                disabled={savingEdit}
                className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {savingEdit ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                {savingEdit ? 'Enregistrement...' : 'Enregistrer'}
              </button>
            </div>
          </div>
          <textarea
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            disabled={savingEdit}
            spellCheck={false}
            className="h-[500px] w-full resize-y rounded-md border border-neutral-800 bg-black p-4 font-mono text-xs leading-relaxed text-neutral-200 outline-none focus:border-blue-600 disabled:opacity-60"
          />
        </InfoCard>
      )}

      {/* Diff Section */}
      {diffHtml && !isEditing && (
        <InfoCard title="Diff des modifications">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-xs text-neutral-500">
              🔴 texte barré = supprimé · 🟢 texte en gras = ajouté
            </div>
            <button
              type="button"
              onClick={handleRegenerateDiff}
              disabled={regeneratingDiff}
              className="flex items-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-800 px-3 py-1.5 text-[11px] text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${regeneratingDiff ? 'animate-spin' : ''}`} />
              {regeneratingDiff ? 'Régénération...' : 'Régénérer'}
            </button>
          </div>
          <div
            className="diff-content max-h-[500px] overflow-auto rounded-md border border-neutral-800 bg-black p-4 text-xs leading-relaxed"
            dangerouslySetInnerHTML={{ __html: diffHtml }}
          />
        </InfoCard>
      )}

      {/* Edit Summary */}
      <InfoCard title="Résumé d'édition (envoyé sur Wikipédia)">
        <div className="relative">
          {!isEditingSummary ? (
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 rounded-md border border-neutral-800 bg-black p-4 text-xs text-neutral-300">
                {editSummary || "Correction de liens morts via OVIX"}
              </div>
              <button
                type="button"
                onClick={handleStartEditSummary}
                disabled={publishing}
                className="shrink-0 rounded-md border border-neutral-800 bg-neutral-800 p-2 text-neutral-400 transition-colors hover:bg-neutral-700 hover:text-neutral-200 disabled:cursor-not-allowed disabled:opacity-50"
                title="Modifier le résumé"
              >
                <Edit className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <textarea
                value={tempSummary}
                onChange={(e) => setTempSummary(e.target.value)}
                disabled={publishing}
                placeholder="Correction de liens morts via OVIX"
                className="w-full rounded-md border border-neutral-800 bg-black p-4 text-xs text-neutral-300 outline-none focus:border-blue-600 disabled:opacity-60 resize-y"
                rows={3}
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={handleCancelSummary}
                  disabled={publishing}
                  className="flex items-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-800 px-3 py-1.5 text-[11px] text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <X className="h-3.5 w-3.5" />
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={handleSaveSummary}
                  disabled={publishing}
                  className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" />
                  Enregistrer
                </button>
              </div>
            </div>
          )}
        </div>
      </InfoCard>

      {/* Actions */}
      <InfoCard title="Actions">
        <div className="flex flex-wrap items-center gap-3">
          {correctedContent && (
            <>
              <button
                type="button"
                onClick={handlePublish}
                disabled={isPublished || publishing || isEditing}
                className="flex items-center gap-2 rounded-md bg-blue-600 px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {publishing && <Loader2 className="h-4 w-4 animate-spin" />}
                {publishing ? 'Publication en cours...' : isPublished ? 'Déjà publié' : 'Publier'}
              </button>

              <label className="flex items-center gap-2 text-xs text-neutral-400">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  disabled={isPublished}
                  className="h-4 w-4 rounded border-neutral-700 bg-neutral-900 accent-blue-600"
                />
                Dry-run (test sans publier)
              </label>
            </>
          )}

          <button
            type="button"
            onClick={handleReanalyze}
            disabled={reanalyzing || isEditing}
            className="flex items-center gap-2 rounded-md bg-amber-600 px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-amber-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {reanalyzing && <Loader2 className="h-4 w-4 animate-spin" />}
            {reanalyzing ? 'Analyse en cours...' : 'Réanalyser'}
          </button>

          <button
            type="button"
            onClick={handleStartManualEdit}
            disabled={isPublished || isEditing}
            className="flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-800 px-3.5 py-2 text-xs text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Edit className="h-4 w-4" />
            Modifier manuellement
          </button>

          <button
            type="button"
            onClick={handleIgnore}
            disabled={isPublished || ignoring || isEditing}
            className="flex items-center gap-2 rounded-md border border-red-900/40 bg-red-950/30 px-3.5 py-2 text-xs text-red-400 transition-colors hover:bg-red-950/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {ignoring ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            {ignoring ? 'Ignor en cours...' : 'Ignorer'}
          </button>
        </div>
      </InfoCard>

      {/* Confirmation modale */}
      {showConfirmDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in"
          onClick={(e) => {
            if (e.target === e.currentTarget && !publishing) setShowConfirmDialog(false)
          }}
        >
          <div
            className="w-full max-w-md rounded-lg border border-neutral-700 bg-neutral-900 p-6 shadow-2xl animate-in zoom-in-95"
            role="alertdialog"
            aria-modal="true"
          >
            <div className="mb-4 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-950/50 border border-red-900/50">
                <AlertTriangle className="h-5 w-5 text-red-500" />
              </div>
              <h3 className="text-lg font-semibold text-neutral-100">Confirmer la publication</h3>
            </div>
            <p className="mb-6 text-sm text-neutral-400 leading-relaxed">
              Vous êtes sur le point de publier l'article <strong className="text-neutral-200">{articleTitle}</strong> sur
              Wikipédia.
              <br />
              <br />
              <span className="text-red-400 font-semibold">Cette action est irréversible.</span>
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowConfirmDialog(false)}
                disabled={publishing}
                className="flex items-center gap-2 rounded-md border border-neutral-700 bg-neutral-800 px-4 py-2 text-sm text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={executePublish}
                disabled={publishing}
                className="flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {publishing && <Loader2 className="h-4 w-4 animate-spin" />}
                {publishing ? 'Publication...' : 'Confirmer la publication'}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  )
}