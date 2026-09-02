import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  XCircle,
  RefreshCw,
  Pause,
  Play,
  Loader2,
} from 'lucide-react'
import { analysisApi } from '../api/analysis.api'
import type { AnalysisJob, AnalysisProgress } from '../api/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JobStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled' | string

// Extend AnalysisJob to include 'paused' status for local UI support
type LocalAnalysisJob = Omit<AnalysisJob, 'status'> & { status: JobStatus }

interface Issue {
  issue_type: string
  description?: string
  severity?: 'high' | 'medium' | 'low' | string
  original_text?: string
  suggested_text?: string
}

interface Results {
  stats?: {
    total_issues?: number
    high_severity?: number
    medium_severity?: number
    low_severity?: number
  }
  issues?: Issue[]
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

function truncate(text: string, max = 100) {
  return text.length > max ? `${text.slice(0, max)}...` : text
}

const STATUS_META: Record<string, { label: string; color: string; icon: typeof CheckCircle }> = {
  completed: { label: 'Terminé', color: '#10b981', icon: CheckCircle },
  running: { label: 'En cours', color: '#3b82f6', icon: Clock },
  pending: { label: 'En attente', color: '#666666', icon: Clock },
  paused: { label: 'En pause', color: '#f59e0b', icon: Pause },
  failed: { label: 'Échoué', color: '#ef4444', icon: XCircle },
  cancelled: { label: 'Annulé', color: '#666666', icon: XCircle },
}

function statusMeta(status: JobStatus) {
  return STATUS_META[status] || { label: status || 'Inconnu', color: '#666666', icon: Clock }
}

const SEVERITY_COLOR: Record<string, string> = {
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#10b981',
}

// ---------------------------------------------------------------------------
// Small presentational pieces
// ---------------------------------------------------------------------------

function PageHeader({ children }: { children?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
      <div>
        <h2 style={{ fontSize: '20px', fontWeight: 600, color: '#f5f5f5' }}>Résultats d'Analyse</h2>
        <p style={{ color: '#a0a0a0', marginTop: '4px', fontSize: '13px' }}>Voir et gérer les résultats d'analyse</p>
      </div>
      {children}
    </div>
  )
}

function Panel({ children, center = false }: { children: React.ReactNode; center?: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: center ? 'center' : 'flex-start',
        padding: '48px',
        backgroundColor: '#161616',
        borderRadius: '8px',
        border: '1px solid #2a2a2a',
      }}
    >
      {children}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ backgroundColor: '#1a1a1a', padding: '16px', borderRadius: '6px' }}>
      <div style={{ fontSize: '11px', color: '#666666', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '20px', fontWeight: 600, color }}>{value}</div>
    </div>
  )
}

function IssueCard({ issue }: { issue: Issue }) {
  const color = SEVERITY_COLOR[issue.severity || ''] || '#10b981'
  return (
    <div style={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '6px', padding: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <AlertTriangle style={{ width: '15px', height: '15px', color, flexShrink: 0 }} />
        <span style={{ fontSize: '13px', color: '#f5f5f5', fontWeight: 500 }}>{issue.issue_type}</span>
      </div>
      {issue.description && (
        <div style={{ fontSize: '12px', color: '#666666', marginBottom: '8px' }}>{issue.description}</div>
      )}
      {issue.original_text && (
        <div style={{ fontSize: '12px', color: '#888888', marginBottom: '6px' }}>
          <strong>Original :</strong> {truncate(issue.original_text)}
        </div>
      )}
      {issue.suggested_text && (
        <div style={{ fontSize: '12px', color: '#10b981' }}>
          <strong>Suggestion :</strong> {truncate(issue.suggested_text)}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AnalysisResults() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const jobId = searchParams.get('jobId')

  const [job, setJob] = useState<LocalAnalysisJob | null>(null)
  const [results, setResults] = useState<Results | null>(null)
  // Distinct de `loading` (chargement du job) : suit spécifiquement le chargement
  // des résultats détaillés, pour ne jamais confondre "en cours de récupération"
  // avec "échec définitif" dans le rendu — c'est ce qui causait l'impression que
  // les résultats "disparaissaient" au retour sur la page.
  const [resultsLoading, setResultsLoading] = useState(false)
  // Empêche le filet de sécurité de retenter indéfiniment si getAnalysisResults
  // échoue systématiquement (ex: 404/500 persistant) — sans ce flag, l'effet de
  // sécurité relance fetchResults à chaque render tant que `results` reste null,
  // ce qui spamme l'API en boucle. Reset à false à chaque nouveau jobId/retry manuel.
  const [resultsFetchFailed, setResultsFetchFailed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [actionPending, setActionPending] = useState<'pause' | 'resume' | 'cancel' | null>(null)

  // Guards against stale async responses overwriting newer state
  // (e.g. component re-fetches while a previous request is still in flight).
  const requestIdRef = useRef(0)

  const fetchResults = useCallback(
    async (requestId: number) => {
      if (!jobId) return
      setResultsLoading(true)
      try {
        const resultsData = await analysisApi.getAnalysisResults(jobId)
        if (requestId !== requestIdRef.current) return
        const issues = resultsData.issues || []
        // Use stats directly from backend response instead of recalculating
        const backendStats = resultsData.stats || {}
        const transformedResults: Results = {
          stats: {
            total_issues: backendStats.total_issues || resultsData.dead_links_count || 0,
            high_severity: backendStats.high_severity || 0,
            medium_severity: backendStats.medium_severity || 0,
            low_severity: backendStats.low_severity || 0,
          },
          issues: issues.map(link => ({
            issue_type: link.issue_type || 'dead_link',
            description: link.description || 'Problème détecté',
            severity: link.severity || 'medium',
            original_text: link.original_text,
            suggested_text: link.suggested_text,
          })),
        }
        setResults(transformedResults)
        setError(null)
        setResultsFetchFailed(false)
      } catch (err) {
        if (requestId !== requestIdRef.current) return
        setError(getErrorMessage(err, 'Erreur lors de la récupération des résultats'))
        setResultsFetchFailed(true)
      } finally {
        if (requestId === requestIdRef.current) setResultsLoading(false)
      }
    },
    [jobId]
  )

  const fetchJobStatus = useCallback(
    async (opts: { silent?: boolean } = {}) => {
      if (!jobId) return
      const requestId = ++requestIdRef.current
      if (!opts.silent) setRefreshing(true)

      try {
        const jobData = await analysisApi.getAnalysisStatus(jobId)
        if (requestId !== requestIdRef.current) return

        // Garde-fou : si on a déjà un statut "completed" avec des résultats chargés,
        // on ignore toute réponse qui reviendrait en arrière (running/pending) —
        // ça peut arriver avec un cache serveur ou une race sur un refetch manuel,
        // et ça faisait disparaître instantanément le bloc Résultats déjà affiché.
        setJob(prevJob => {
          const wasCompletedWithResults = prevJob?.status === 'completed'
          const regressing =
            wasCompletedWithResults &&
            jobData.status !== 'completed' &&
            (jobData.status === 'running' || jobData.status === 'pending')
          return regressing ? prevJob : jobData
        })
        setError(null)

        if (jobData.status === 'completed') {
          setAutoRefresh(false)
          await fetchResults(requestId)
        }
      } catch (err) {
        if (requestId !== requestIdRef.current) return
        setError(getErrorMessage(err, 'Erreur lors de la récupération du statut'))
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    },
    [jobId, fetchResults]
  )

  // Remonte à `null` à chaque montage/changement de jobId : indispensable pour
  // ne pas afficher les résultats d'un job précédent pendant le chargement du nouveau.
  useEffect(() => {
    setJob(null)
    setResults(null)
    setError(null)
    setResultsFetchFailed(false)

    if (!jobId) {
      setLoading(false)
      return
    }
    setLoading(true)
    fetchJobStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  // Filet de sécurité : si le job est déjà "completed" (statut connu) mais que les
  // résultats ne sont pas encore en mémoire et qu'aucun chargement n'est en cours —
  // typiquement au retour sur la page après une navigation ailleurs — on les
  // recharge automatiquement au lieu de laisser l'UI dans un état vide/erroné.
  // `resultsFetchFailed` empêche une boucle de retry infinie si l'API échoue
  // systématiquement ; le bouton "Réessayer" le remet à false pour retenter.
  useEffect(() => {
    if (job?.status === 'completed' && !results && !resultsLoading && !resultsFetchFailed && jobId) {
      fetchResults(requestIdRef.current)
    }
  }, [job?.status, results, resultsLoading, resultsFetchFailed, jobId, fetchResults])

  // Use SSE streaming for real-time status updates instead of polling
  useEffect(() => {
    if (!autoRefresh || !jobId) return

    const status = job?.status
    const isActive = status === 'running' || status === 'pending'
    const isCompleted = status === 'completed' || status === 'failed'

    // If already completed, don't start streaming
    if (isCompleted) return

    // If not active and not completed, don't start streaming
    if (!isActive && status) return

    const cleanup = analysisApi.streamAnalysisStatus(
      jobId,
      (statusUpdate) => {
        setJob(prevJob => {
          const wasCompletedWithResults = prevJob?.status === 'completed'
          const regressing =
            wasCompletedWithResults &&
            statusUpdate.status !== 'completed' &&
            (statusUpdate.status === 'running' || statusUpdate.status === 'pending')
          return regressing ? prevJob : statusUpdate
        })
        setError(null)

        if (statusUpdate.status === 'completed') {
          setAutoRefresh(false)
          fetchResults(requestIdRef.current)
        }
      },
      () => {
        // On complete
        setLoading(false)
        setRefreshing(false)
      },
      (error) => {
        // On error
        setError(error)
        setLoading(false)
        setRefreshing(false)
      }
    )

    return cleanup
  }, [autoRefresh, jobId, job?.status, fetchResults])

  const cancelJob = async () => {
    if (!jobId || actionPending) return
    if (!window.confirm('Êtes-vous sûr de vouloir annuler cette analyse ?')) return

    setActionPending('cancel')
    setActionError(null)
    try {
      await analysisApi.cancelAnalysis(jobId)
      await fetchJobStatus()
    } catch (err) {
      setActionError("Erreur lors de l'annulation : " + getErrorMessage(err, 'erreur inconnue'))
    } finally {
      setActionPending(null)
    }
  }

  const pauseJob = async () => {
    if (!jobId || actionPending) return
    setActionPending('pause')
    setActionError(null)
    try {
      await analysisApi.pauseAnalysis(jobId)
      await fetchJobStatus()
    } catch (err) {
      setActionError('Erreur lors de la pause : ' + getErrorMessage(err, 'erreur inconnue'))
    } finally {
      setActionPending(null)
    }
  }

  const resumeJob = async () => {
    if (!jobId || actionPending) return
    setActionPending('resume')
    setActionError(null)
    try {
      await analysisApi.resumeAnalysis(jobId)
      await fetchJobStatus()
    } catch (err) {
      setActionError('Erreur lors de la reprise : ' + getErrorMessage(err, 'erreur inconnue'))
    } finally {
      setActionPending(null)
    }
  }

  // ---------------------------------------------------------------------------
  // Render states
  // ---------------------------------------------------------------------------

  if (!jobId) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <PageHeader />
        <Panel center>
          <div style={{ textAlign: 'center', color: '#666666', fontSize: '14px' }}>Aucune analyse sélectionnée</div>
        </Panel>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <PageHeader />
        <Panel center>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#666666', fontSize: '14px' }}>
            <Loader2 style={{ width: '18px', height: '18px' }} className="animate-spin" />
            Chargement...
          </div>
        </Panel>
      </div>
    )
  }

  if (error && !job) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <PageHeader />
        <Panel center>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', textAlign: 'center' }}>
            <AlertTriangle style={{ width: '22px', height: '22px', color: '#ef4444' }} />
            <div style={{ color: '#ef4444', fontSize: '14px' }}>{error}</div>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setLoading(true)
                fetchJobStatus()
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}
            >
              <RefreshCw style={{ width: '14px', height: '14px' }} />
              Réessayer
            </button>
          </div>
        </Panel>
      </div>
    )
  }

  // Safety net: loading is false, no fatal error, but job is still missing
  // (e.g. unexpected empty response) — avoid crashing on job.status below.
  if (!job) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <PageHeader />
        <Panel center>
          <div style={{ textAlign: 'center', color: '#666666', fontSize: '14px' }}>Aucune donnée disponible</div>
        </Panel>
      </div>
    )
  }

  const meta = statusMeta(job.status)
  const StatusIcon = meta.icon
  const isActiveStatus = job.status === 'running' || job.status === 'pending'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <PageHeader>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary"
            onClick={() => fetchJobStatus()}
            disabled={refreshing}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', opacity: refreshing ? 0.6 : 1 }}
          >
            <RefreshCw style={{ width: '14px', height: '14px' }} className={refreshing ? 'animate-spin' : ''} />
            Actualiser
          </button>
          {job.status === 'running' && (
            <>
              <button
                className="btn btn-secondary"
                onClick={pauseJob}
                disabled={actionPending !== null}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', opacity: actionPending ? 0.6 : 1 }}
              >
                {actionPending === 'pause' ? (
                  <Loader2 style={{ width: '14px', height: '14px' }} className="animate-spin" />
                ) : (
                  <Pause style={{ width: '14px', height: '14px' }} />
                )}
                Pause
              </button>
              <button
                className="btn btn-danger"
                onClick={cancelJob}
                disabled={actionPending !== null}
                style={{ fontSize: '13px', opacity: actionPending ? 0.6 : 1 }}
              >
                Annuler
              </button>
            </>
          )}
          {job.status === 'paused' && (
            <button
              className="btn btn-primary"
              onClick={resumeJob}
              disabled={actionPending !== null}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', opacity: actionPending ? 0.6 : 1 }}
            >
              {actionPending === 'resume' ? (
                <Loader2 style={{ width: '14px', height: '14px' }} className="animate-spin" />
              ) : (
                <Play style={{ width: '14px', height: '14px' }} />
              )}
              Relancer
            </button>
          )}
        </div>
      </PageHeader>

      {actionError && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
            padding: '12px 16px',
            backgroundColor: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '8px',
            color: '#ef4444',
            fontSize: '13px',
          }}
        >
          <AlertTriangle style={{ width: '14px', height: '14px', marginTop: '2px', flexShrink: 0 }} />
          <span>{actionError}</span>
        </div>
      )}

      {error && job && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            backgroundColor: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.3)',
            borderRadius: '8px',
            color: '#f59e0b',
            fontSize: '13px',
          }}
        >
          <AlertTriangle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          <span>{error} — les données affichées peuvent être obsolètes.</span>
        </div>
      )}

      {/* Job Status Card */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ padding: '12px', backgroundColor: '#1a1a1a', borderRadius: '8px' }}>
            <StatusIcon style={{ width: '20px', height: '20px', color: meta.color }} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3
              style={{
                fontSize: '15px',
                fontWeight: 500,
                color: '#f5f5f5',
                marginBottom: '4px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {job.article_title || 'Article'}
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '13px', color: meta.color, fontWeight: 500 }}>{meta.label}</span>
              <span style={{ fontSize: '13px', color: '#666666' }}>
                • {job.started_at ? new Date(job.started_at).toLocaleString('fr-FR') : 'En attente'}
              </span>
            </div>
          </div>
        </div>

        {/* Progress */}
        {job.status === 'running' && typeof job.progress === 'number' && (
          <div style={{ marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '13px', color: '#a0a0a0' }}>{job.message || 'Traitement en cours...'}</span>
              <span style={{ fontSize: '13px', color: '#666666' }}>{Math.round(job.progress * 100)}%</span>
            </div>
            <div style={{ width: '100%', height: '4px', backgroundColor: '#2a2a2a', borderRadius: '2px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, job.progress * 100))}%`,
                  height: '100%',
                  backgroundColor: '#3b82f6',
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
          </div>
        )}

        {job.status === 'pending' && (
          <div style={{ marginTop: '16px', fontSize: '13px', color: '#a0a0a0' }}>
            En file d'attente, le traitement va démarrer sous peu...
          </div>
        )}
      </div>

      {/* Results */}
      {job.status === 'completed' && results ? (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
          <h3
            style={{
              fontSize: '12px',
              fontWeight: 500,
              color: '#666666',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '16px',
            }}
          >
            Résultats
          </h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <StatCard label="Total problèmes" value={results.stats?.total_issues || 0} color="#f5f5f5" />
            <StatCard label="Haute sévérité" value={results.stats?.high_severity || 0} color="#ef4444" />
            <StatCard label="Moyenne sévérité" value={results.stats?.medium_severity || 0} color="#f59e0b" />
            <StatCard label="Faible sévérité" value={results.stats?.low_severity || 0} color="#10b981" />
          </div>

          {results.issues && results.issues.length > 0 ? (
            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 500, color: '#a0a0a0', marginBottom: '12px' }}>Problèmes détectés</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {results.issues.map((issue, index) => (
                  <IssueCard key={index} issue={issue} />
                ))}
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '32px', color: '#666666', fontSize: '13px' }}>Aucun problème détecté</div>
          )}
        </div>
      ) : job.status === 'completed' && resultsLoading ? (
        // Job terminé, résultats en cours de (re)chargement — au retour sur la page
        // par exemple. Distinct de l'état d'échec pour ne pas afficher un faux
        // message d'erreur pendant une requête normale en vol.
        <Panel center>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#666666', fontSize: '13px' }}>
            <Loader2 style={{ width: '16px', height: '16px' }} className="animate-spin" />
            Chargement des résultats...
          </div>
        </Panel>
      ) : job.status === 'completed' && !results ? (
        // Completed, aucun chargement en cours, et toujours pas de résultats —
        // véritable échec (le filet de sécurité ci-dessus aura déjà tenté un retry).
        <Panel center>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', textAlign: 'center' }}>
            <AlertTriangle style={{ width: '20px', height: '20px', color: '#f59e0b' }} />
            <div style={{ color: '#a0a0a0', fontSize: '13px' }}>
              Analyse terminée, mais les résultats n'ont pas pu être chargés.
            </div>
            <button
              className="btn btn-secondary"
              onClick={() => {
                setResultsFetchFailed(false)
                fetchResults(requestIdRef.current)
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}
            >
              <RefreshCw style={{ width: '14px', height: '14px' }} />
              Réessayer
            </button>
          </div>
        </Panel>
      ) : isActiveStatus ? (
        <Panel center>
          <div style={{ textAlign: 'center', color: '#666666' }}>
            <RefreshCw
              style={{ width: '28px', height: '28px', color: '#3b82f6', margin: '0 auto 16px' }}
              className="animate-spin"
            />
            <div style={{ fontSize: '13px' }}>
              {job.status === 'pending' ? "En attente de démarrage..." : 'Analyse en cours...'}
            </div>
          </div>
        </Panel>
      ) : job.status === 'paused' ? (
        <Panel center>
          <div style={{ textAlign: 'center', color: '#666666' }}>
            <Pause style={{ width: '28px', height: '28px', color: '#f59e0b', margin: '0 auto 16px' }} />
            <div style={{ fontSize: '13px' }}>Analyse en pause</div>
          </div>
        </Panel>
      ) : job.status === 'failed' ? (
        <Panel center>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', textAlign: 'center' }}>
            <XCircle style={{ width: '28px', height: '28px', color: '#ef4444' }} />
            <div style={{ fontSize: '13px', color: '#ef4444' }}>L'analyse a échoué</div>
            {job.message && <div style={{ fontSize: '12px', color: '#666666' }}>{job.message}</div>}
          </div>
        </Panel>
      ) : job.status === 'cancelled' ? (
        <Panel center>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', textAlign: 'center' }}>
            <XCircle style={{ width: '28px', height: '28px', color: '#666666' }} />
            <div style={{ fontSize: '13px', color: '#666666' }}>Analyse annulée</div>
          </div>
        </Panel>
      ) : (
        // Unknown/unhandled status — still shown, never a silent blank.
        <Panel center>
          <div style={{ textAlign: 'center', color: '#666666', fontSize: '13px' }}>
            Statut : {meta.label}
          </div>
        </Panel>
      )}
    </div>
  )
}