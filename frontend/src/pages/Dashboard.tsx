import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { FileText, AlertTriangle, CheckCircle2, Clock, Activity, Database, Radar, RefreshCw, ArrowUpRight, WifiOff } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { systemApi } from '../api/system.api'
import { articlesApi } from '../api/articles.api'
import { statsApi } from '../api/stats.api'
import { authApi } from '../api/auth.api'

interface ActivityItem {
  article: string
  action: string
  time: string
  tone: string
}

const STATUS_CONFIG: Record<string, { action: string; tone: string }> = {
  published: { action: 'Publié', tone: 'var(--accent-green)' },
  analyzing: { action: 'Analyse en cours', tone: 'var(--accent-yellow)' },
  pending: { action: 'En attente', tone: 'var(--text-muted)' },
  rejected: { action: 'Rejeté', tone: 'var(--accent-red)' },
  error: { action: 'Erreur', tone: 'var(--accent-red)' },
}
const DEFAULT_STATUS = { action: 'Analyse terminée', tone: 'var(--accent-cyan)' }

const CONNECTED_LABELS = new Set(['Opérationnel', 'Connectée', 'Opérationnels', 'Connecté'])

// Nombre de tentatives de refetch automatique en cas d'échec réseau (avec backoff),
// évite de laisser le dashboard "mort" silencieusement après une erreur transitoire.
const AUTO_RETRY_DELAYS_MS = [4000, 10000, 20000]

/** Formate une différence de temps en français, de façon sûre (jamais NaN / Invalid Date). */
function formatRelativeTime(rawDate: unknown): string {
  let date: Date | null = null

  if (typeof rawDate === 'string' || typeof rawDate === 'number') {
    const parsed = new Date(rawDate)
    if (!isNaN(parsed.getTime())) date = parsed
  }

  if (!date) return 'À l\'instant'

  const diffMs = Date.now() - date.getTime()
  if (diffMs < 0) return 'À l\'instant'

  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'À l\'instant'
  if (diffMins < 60) return diffMins === 1 ? 'il y a 1 min' : `il y a ${diffMins} min`
  if (diffHours < 24) return diffHours === 1 ? 'il y a 1 heure' : `il y a ${diffHours} heures`
  return diffDays === 1 ? 'il y a 1 jour' : `il y a ${diffDays} jours`
}

function getGreeting(hour: number): string {
  if (hour < 5) return 'Bonsoir'
  if (hour < 12) return 'Bonjour'
  if (hour < 18) return 'Bon après-midi'
  return 'Bonsoir'
}

/** Formate un nombre de façon sûre, avec repli explicite si la valeur est absente/invalide. */
function safeNumber(value: unknown): string | null {
  if (typeof value !== 'number' || !isFinite(value)) return null
  return value.toLocaleString('fr-FR')
}

export default function Dashboard() {
  const [now, setNow] = useState(() => new Date())
  const [isOffline, setIsOffline] = useState(() => typeof navigator !== 'undefined' ? !navigator.onLine : false)
  const mountedRef = useRef(true)
  const retryAttemptRef = useRef(0)
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // isAuthenticated doit refléter en temps réel l'état du token/session (contexte d'auth).
  // Tant que ce flag ne change pas quand l'utilisateur se connecte, le dashboard
  // ne saura jamais qu'il doit relancer les appels avec le nouveau token.

  const systemStatus = useApi(() => systemApi.getSystemStatus(), false)
  const articleStats = useApi(() => statsApi.getArticleStats(), false)
  const analysisStats = useApi(() => statsApi.getAnalysisStats(), false)
  const publicationStats = useApi(() => statsApi.getPublicationStats(), false)
  const healthCheck = useApi(() => systemApi.healthCheck(), false)
  const articleHistory = useApi(() => articlesApi.getArticleHistory(5), false)

  const greeting = useMemo(() => getGreeting(now.getHours()), [now])
  const timeStr = useMemo(
    () => now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    [now]
  )
  const dateStr = useMemo(
    () => now.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' }),
    [now]
  )

  useEffect(() => {
    mountedRef.current = true
    const t = setInterval(() => {
      if (mountedRef.current) setNow(new Date())
    }, 30000)
    return () => {
      mountedRef.current = false
      clearInterval(t)
    }
  }, [])

  // Suivi de la connectivité réseau du navigateur — affiche un bandeau clair plutôt
  // que de laisser l'utilisateur face à des tuiles à "0" sans explication.
  useEffect(() => {
    const handleOnline = () => setIsOffline(false)
    const handleOffline = () => setIsOffline(true)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  const refetchAll = useCallback(() => {
    systemStatus.refetch()
    articleStats.refetch()
    analysisStats.refetch()
    publicationStats.refetch()
    healthCheck.refetch()
    articleHistory.refetch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Chargement initial au montage.
  useEffect(() => {
    refetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // WikipediaConnection émet 'auth:success' juste après une connexion réussie
  // (window.dispatchEvent(new CustomEvent('auth:success'))). On écoute cet événement
  // pour rafraîchir automatiquement toutes les données du dashboard — avant ce correctif,
  // le montage initial figeait les appels une fois pour toutes : si l'utilisateur se
  // connectait après coup, le dashboard gardait les anciennes données/erreurs (401)
  // jusqu'à un clic manuel sur "Actualiser".
  useEffect(() => {
    const handleAuthSuccess = () => {
      retryAttemptRef.current = 0
      refetchAll()
    }
    window.addEventListener('auth:success', handleAuthSuccess)
    return () => window.removeEventListener('auth:success', handleAuthSuccess)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Vérification périodique de la validité de la session Wikipedia
  // pour s'assurer que le statut de connexion affiché est toujours à jour
  useEffect(() => {
    const validateWikipediaSession = async () => {
      try {
        const validation = await authApi.validateSession()
        if (!validation.valid || !validation.authenticated) {
          // La session n'est plus valide, rafraîchir le statut système
          console.log('[Dashboard] Wikipedia session validation failed, refreshing system status')
          systemStatus.refetch()
        }
      } catch (err) {
        console.warn('[Dashboard] Session validation check failed', err)
      }
    }

    // Validation toutes les 2 heures
    const interval = setInterval(validateWikipediaSession, 7200000)

    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const hasAnyError = Boolean(
    systemStatus.error || articleStats.error || analysisStats.error ||
    publicationStats.error || healthCheck.error || articleHistory.error
  )
  const isAnyLoading = systemStatus.loading || articleStats.loading || analysisStats.loading ||
    publicationStats.loading || healthCheck.loading || articleHistory.loading

  // Retry automatique avec backoff progressif en cas d'échec, tant que l'onglet est
  // visible et que le navigateur est en ligne. Se réinitialise dès qu'un cycle réussit.
  useEffect(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current)
      retryTimeoutRef.current = null
    }

    if (!hasAnyError || isAnyLoading || isOffline) {
      if (!hasAnyError) retryAttemptRef.current = 0
      return
    }

    const attempt = retryAttemptRef.current
    if (attempt >= AUTO_RETRY_DELAYS_MS.length) return

    retryTimeoutRef.current = setTimeout(() => {
      if (!mountedRef.current) return
      retryAttemptRef.current = attempt + 1
      refetchAll()
    }, AUTO_RETRY_DELAYS_MS[attempt])

    return () => {
      if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAnyError, isAnyLoading, isOffline])

  const recentActivity: ActivityItem[] = useMemo(() => {
    const data = articleHistory.data
    if (!Array.isArray(data) || data.length === 0) return []

    return data.slice(0, 4).map((item: any): ActivityItem => {
      const rawDate = item?.analysis_date ?? item?.published_date ?? null
      const { action, tone } = STATUS_CONFIG[item?.status as string] ?? DEFAULT_STATUS

      return {
        article: item?.title || item?.article_title || 'Article inconnu',
        action,
        time: formatRelativeTime(rawDate),
        tone,
      }
    })
  }, [articleHistory.data])

  const isRefreshing = isAnyLoading

  // Chaque tuile suit le loading de SA propre source — une API lente ne doit pas
  // afficher "0" figé pendant qu'une autre API répond plus vite. Une valeur manquante
  // ou invalide affiche "—" plutôt qu'un "0" trompeur.
  const stats = useMemo(() => {
    const a = articleStats.data
    const an = analysisStats.data
    const p = publicationStats.data
    const articleLoading = articleStats.loading && !a
    const analysisLoading = analysisStats.loading && !an
    const publicationLoading = publicationStats.loading && !p
    const articleFailed = Boolean(articleStats.error) && !a
    const analysisFailed = Boolean(analysisStats.error) && !an
    const publicationFailed = Boolean(publicationStats.error) && !p

    const publicationRateValue = typeof p?.publication_rate === 'number' && isFinite(p.publication_rate)
      ? `${p.publication_rate.toFixed(1)}%`
      : null

    return [
      {
        name: 'Articles analysés',
        value: safeNumber(a?.analyzed),
        icon: FileText,
        accent: 'var(--accent-cyan)',
        isLoading: articleLoading,
        isFailed: articleFailed,
      },
      {
        name: 'Articles publiés',
        value: safeNumber(a?.published),
        icon: CheckCircle2,
        accent: 'var(--accent-green)',
        isLoading: articleLoading,
        isFailed: articleFailed,
      },
      {
        name: 'En attente',
        value: safeNumber(a?.pending),
        icon: Clock,
        accent: 'var(--accent-yellow)',
        isLoading: articleLoading,
        isFailed: articleFailed,
      },
      {
        name: 'Liens morts détectés',
        value: safeNumber(an?.dead_links_detected),
        icon: AlertTriangle,
        accent: 'var(--accent-red)',
        isLoading: analysisLoading,
        isFailed: analysisFailed,
      },
      {
        name: 'Liens morts corrigés',
        value: safeNumber(an?.dead_links_corrected),
        icon: CheckCircle2,
        accent: 'var(--accent-green)',
        isLoading: analysisLoading,
        isFailed: analysisFailed,
      },
      {
        name: 'Taux de publication',
        value: publicationRateValue,
        icon: Activity,
        accent: 'var(--accent-purple)',
        isLoading: publicationLoading,
        isFailed: publicationFailed,
      },
    ]
  }, [
    articleStats.data, articleStats.loading, articleStats.error,
    analysisStats.data, analysisStats.loading, analysisStats.error,
    publicationStats.data, publicationStats.loading, publicationStats.error,
  ])

  const systemStatusItems = useMemo(() => [
    {
      name: 'API',
      status: healthCheck.data?.status === 'healthy' ? 'Opérationnel' : 'Erreur',
      icon: Activity,
    },
    {
      name: 'Wikipedia',
      status: systemStatus.data?.wikipedia?.connected ? 'Connecté' : 'Non connecté',
      icon: Activity,
    },
    {
      name: 'Base de données',
      status: healthCheck.data?.services?.database === 'ok' ? 'Connectée' : 'Déconnectée',
      icon: Database,
    },
    {
      name: 'Trackers',
      status: (healthCheck.data?.services?.published_tracker === 'ok' && healthCheck.data?.services?.analyzed_tracker === 'ok')
        ? 'Opérationnels'
        : 'Erreur',
      icon: Radar,
    },
  ], [healthCheck.data, systemStatus.data])

  const hasHealthError = Boolean(healthCheck.error) && !healthCheck.loading
  const hasStatsError = Boolean(articleStats.error || analysisStats.error || publicationStats.error) && !articleStats.loading && !analysisStats.loading && !publicationStats.loading
  const hasSystemError = Boolean(systemStatus.error) && !systemStatus.loading
  const hasActivityError = Boolean(articleHistory.error) && !articleHistory.loading

  const okCount = systemStatusItems.filter(i => CONNECTED_LABELS.has(i.status)).length
  const isHealthLoading = healthCheck.loading && !healthCheck.data
  const allOk = !isHealthLoading && okCount === systemStatusItems.length

  return (
    <div className="flex flex-col gap-md text-md animate-fadeIn">
      {isOffline && (
        <div className="alert alert-error" role="status" aria-live="polite">
          <WifiOff className="icon-sm flex-shrink-0" />
          Connexion internet indisponible. Les données affichées peuvent être obsolètes.
        </div>
      )}

      {/* Header strip */}
      <div
        className="flex items-center justify-between gap-md"
        style={{
          padding: '16px 22px',
          borderRadius: '10px',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          background: 'linear-gradient(to right, var(--bg-secondary), rgba(17, 17, 17, 0.4))',
        }}
      >
        <div className="flex items-center gap-sm" style={{ height: '100%' }}>
          <span className="relative flex" style={{ width: '8px', height: '8px' }} aria-hidden="true">
            {!isHealthLoading && (
              <span className={`absolute inline-flex rounded-full ${allOk ? 'status-dot-online' : 'status-dot-offline'}`} style={{ width: '100%', height: '100%', opacity: 0.75 }} />
            )}
            <span className={`relative status-dot ${isHealthLoading ? 'status-dot-loading' : allOk ? 'status-dot-online' : 'status-dot-offline'}`} />
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '2px' }}>
            <h2 className="text-secondary font-semibold" style={{ fontSize: '15px', lineHeight: 1, margin: 0, padding: 0 }}>{greeting}</h2>
            <p className="text-muted capitalize" style={{ fontSize: '11px', lineHeight: 1, margin: 0, padding: 0 }}>
              {dateStr} · {timeStr}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => { retryAttemptRef.current = 0; refetchAll() }}
          disabled={isRefreshing}
          aria-busy={isRefreshing}
          aria-label="Actualiser les données du tableau de bord"
          className="btn btn-secondary btn-sm transition-normal"
          style={{ padding: '6px 10px', fontSize: '11px' }}
        >
          <RefreshCw className={`icon-sm ${isRefreshing ? 'animate-spin' : ''}`} />
          Actualiser
        </button>
      </div>

      {/* Main grid: status rail (left) + stats (right) */}
      <div className="grid grid-cols-3 gap-md" style={{ alignItems: 'stretch' }}>
        {/* System Status — vertical rail */}
        <div className="card col-span-1 p-lg" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="flex items-center justify-between mb-lg">
            <h3 className="text-muted uppercase font-semibold" style={{ fontSize: '10px', letterSpacing: '0.1em' }}>Système</h3>
            {(hasHealthError || hasSystemError) && <AlertTriangle className="icon-sm text-accent-red" aria-label="Erreur système" />}
          </div>
          <div className="flex flex-col gap-lg">
            {systemStatusItems.map((item) => {
              const Icon = item.icon
              const isConnected = CONNECTED_LABELS.has(item.status)
              const isLoading = isHealthLoading
              return (
                <div key={item.name} className="flex items-center gap-sm transition-normal">
                  <div className={`icon-wrapper ${isConnected ? 'icon-wrapper-green' : 'icon-wrapper-red'}`} style={{ width: '30px', height: '30px', flexShrink: 0 }}>
                    <Icon className="icon-sm" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-secondary line-tight truncate font-medium" style={{ fontSize: '10.5px' }}>{item.name}</div>
                    {isLoading ? (
                      <div className="loading-skeleton mt-xs" style={{ height: '7px', width: '56px', borderRadius: '999px' }} />
                    ) : (
                      <div
                        className={`${isConnected ? 'text-accent-green' : 'text-accent-red'} line-tight truncate mt-xs`}
                        style={{ fontSize: '9px' }}
                        title={item.status}
                      >
                        {item.status}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Stats — 3x2 compact tiles */}
        <div className="col-span-2 grid grid-cols-3 gap-sm" style={{ alignContent: 'stretch', gridTemplateRows: 'repeat(2, 1fr)' }}>
          {stats.map((stat) => {
            const Icon = stat.icon
            return (
              <div
                key={stat.name}
                className="card transition-normal p-md"
                style={{ minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%' }}
                title={stat.isFailed ? `${stat.name} — données indisponibles` : stat.name}
              >
                <div className="flex items-center justify-between mb-md">
                  <div className="icon-wrapper" style={{ width: '26px', height: '26px', backgroundColor: `${stat.accent}18`, flexShrink: 0 }}>
                    <Icon className="icon-sm" style={{ color: stat.accent, flexShrink: 0 }} />
                  </div>
                  {stat.isFailed && (
                    <AlertTriangle className="icon-sm text-accent-red" style={{ opacity: 0.7 }} aria-label="Données indisponibles" />
                  )}
                </div>
                {stat.isLoading ? (
                  <div className="loading-skeleton mb-xs" style={{ height: '20px', width: '48px' }} />
                ) : (
                  <div
                    className={`font-semibold tabular-nums truncate ${stat.value === null ? 'text-muted' : 'text-primary'}`}
                    style={{ fontSize: '19px', lineHeight: 1 }}
                  >
                    {stat.value ?? '—'}
                  </div>
                )}
                <div className="text-muted mt-xs line-tight truncate" style={{ fontSize: '10.5px' }}>{stat.name}</div>
              </div>
            )
          })}
        </div>
      </div>

      {hasStatsError && (
        <div className="alert alert-error" role="alert">
          <AlertTriangle className="icon-sm flex-shrink-0" />
          <span>Impossible de charger certaines statistiques.</span>
          <button
            type="button"
            onClick={() => { retryAttemptRef.current = 0; refetchAll() }}
            className="btn btn-ghost btn-sm"
            style={{ marginLeft: 'auto', fontSize: '10.5px', padding: '4px 8px' }}
          >
            Réessayer
          </button>
        </div>
      )}

      {/* Recent Activity — timeline style */}
      <div className="card p-lg" style={{ overflow: 'hidden' }}>
        <div className="flex items-center justify-between mb-lg">
          <h3 className="text-muted uppercase font-semibold" style={{ fontSize: '10px', letterSpacing: '0.1em' }}>Activité récente</h3>
          <button type="button" className="btn btn-ghost btn-sm transition-normal" style={{ fontSize: '10.5px', padding: '4px 8px' }}>
            Tout voir <ArrowUpRight className="icon-sm" />
          </button>
        </div>
        <div className="relative flex flex-col">
          <div className="absolute" style={{ left: '3px', top: '6px', bottom: '6px', width: '1px', backgroundColor: 'var(--border-color)' }} />
          {articleHistory.loading && !articleHistory.data ? (
            [0, 1, 2].map((i) => (
              <div key={i} className="relative flex items-center justify-between gap-md" style={{ padding: '9px 0 9px 20px' }}>
                <span className="absolute" style={{ left: '0px', top: '50%', transform: 'translateY(-50%)', backgroundColor: 'var(--text-muted)', borderRadius: '999px', width: '6px', height: '6px', boxShadow: '0 0 0 16px var(--dot-halo-bg)' }} />
                <div className="min-w-0 flex-1">
                  <div className="loading-skeleton" style={{ height: '11px', width: '128px' }} />
                  <div className="loading-skeleton mt-xs" style={{ height: '9px', width: '80px' }} />
                </div>
              </div>
            ))
          ) : hasActivityError ? (
            <div className="flex items-center gap-sm py-sm text-accent-red" style={{ fontSize: '11px', paddingLeft: '20px' }}>
              <AlertTriangle className="icon-sm flex-shrink-0" />
              <span>Impossible de charger l'activité récente.</span>
              <button
                type="button"
                onClick={() => articleHistory.refetch()}
                className="btn btn-ghost btn-sm"
                style={{ fontSize: '10px', padding: '2px 6px' }}
              >
                Réessayer
              </button>
            </div>
          ) : recentActivity.length > 0 ? (
            recentActivity.map((activity, index) => (
              <div
                key={`${activity.article}-${index}`}
                className="relative flex items-center justify-between gap-md transition-normal"
                style={{
                  padding: '9px 0 9px 20px',
                  borderBottom: index < recentActivity.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                }}
              >
                <span
                  className="absolute"
                  style={{
                    left: '0px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    backgroundColor: activity.tone,
                    borderRadius: '999px',
                    width: '6px',
                    height: '6px',
                    boxShadow: '0 0 0 16px var(--dot-halo-bg)'
                  }}
                />
                <div className="min-w-0" style={{ flex: '1 1 auto', overflow: 'hidden' }}>
                  <div className="truncate text-secondary font-medium" style={{ fontSize: '12px' }} title={activity.article}>{activity.article}</div>
                  <div className="truncate mt-xs" style={{ fontSize: '10.5px', color: activity.tone }}>{activity.action}</div>
                </div>
                <div className="flex-shrink-0 whitespace-nowrap text-muted" style={{ fontSize: '10px' }}>{activity.time}</div>
              </div>
            ))
          ) : (
            <div className="text-muted italic" style={{ fontSize: '11px', paddingLeft: '20px' }}>Aucune activité récente</div>
          )}
        </div>
      </div>
    </div>
  )
}