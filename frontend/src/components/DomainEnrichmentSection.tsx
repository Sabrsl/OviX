/**
 * Domain Enrichment Section Component
 *
 * Modular component for domain enrichment UI in Settings page.
 * Provides controls for starting/pausing/resuming/canceling enrichment,
 * displaying progress, and previewing/writing changes.
 */

import { useCallback, useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Play, Pause, Square, RefreshCw, Eye, RotateCcw, Settings, CheckCircle, AlertTriangle, X, Save } from 'lucide-react'
import {
  domainEnrichmentApi,
  CategoryConfig,
  EnrichmentStatus,
  PreviewEntry,
  PreviewResponse,
} from '../api/domain_enrichment.api'
import Button from './Button'

// Design tokens matching Settings page
const colors = {
  bgPanel: '#161616',
  bgInput: '#1a1a1a',
  border: '#2a2a2a',
  textPrimary: '#f5f5f5',
  textSecondary: '#e0e0e0',
  textMuted: '#a0a0a0',
  accent: '#3b82f6',
  success: '#10b981',
  successSoft: 'rgba(16, 185, 129, 0.1)',
  successBorder: 'rgba(16, 185, 129, 0.3)',
  error: '#ef4444',
  errorSoft: 'rgba(239, 68, 68, 0.1)',
  errorBorder: 'rgba(239, 68, 68, 0.3)',
  warning: '#f59e0b',
  warningSoft: 'rgba(245, 158, 11, 0.1)',
  warningBorder: 'rgba(245, 158, 11, 0.3)',
}

const POLL_INTERVAL_MS = 2000
const PREVIEW_ROW_LIMIT = 20

// Default categories — could be lifted to props/config later without breaking callers
const DEFAULT_CATEGORIES: CategoryConfig[] = [
  { wiki: 'fr', category: 'Média français', priority: 1 },
  { wiki: 'fr', category: 'Agence de presse', priority: 1 },
  { wiki: 'fr', category: 'Entreprise de télécommunications', priority: 2 },
]

type ActionKey = 'start' | 'pause' | 'resume' | 'cancel' | 'preview' | 'write' | 'reset' | null

interface Notice {
  type: 'success' | 'error'
  message: string
}

/** Extracts a human-readable message from unknown errors (axios or otherwise). */
function getErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === 'object') {
    const anyErr = error as any
    const apiMessage = anyErr?.response?.data?.message || anyErr?.response?.data?.error
    if (typeof apiMessage === 'string' && apiMessage.trim()) return apiMessage
    if (typeof anyErr?.message === 'string' && anyErr.message.trim()) return anyErr.message
  }
  return fallback
}

export default function DomainEnrichmentSection() {
  const [status, setStatus] = useState<EnrichmentStatus | null>(null)
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [pendingAction, setPendingAction] = useState<ActionKey>(null)
  const [dryRun, setDryRun] = useState(true)
  const [maxPages, setMaxPages] = useState<string>('')
  const [customCategory, setCustomCategory] = useState<string>('')
  const [customWiki, setCustomWiki] = useState<string>('fr')
  const [keepWww, setKeepWww] = useState(false)
  const [sequentialWrite, setSequentialWrite] = useState(false)
  const [categoryList, setCategoryList] = useState<string>('')
  const [useCategoryList, setUseCategoryList] = useState(false)

  const mountedRef = useRef(true)
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const isBusy = pendingAction !== null

  const showNotice = useCallback((n: Notice) => {
    if (!mountedRef.current) return
    setNotice(n)
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current)
    noticeTimerRef.current = setTimeout(() => {
      if (mountedRef.current) setNotice(null)
    }, 6000)
  }, [])

  const loadStatus = useCallback(async () => {
    try {
      const response = await domainEnrichmentApi.getStatus()
      if (!mountedRef.current) return
      setStatus(response)
      setStatusError(null)
    } catch (error) {
      if (!mountedRef.current) return
      console.error('Failed to load enrichment status:', error)
      setStatusError(getErrorMessage(error, "Impossible de récupérer le statut de l'enrichissement."))
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    loadStatus()
    const interval = setInterval(loadStatus, POLL_INTERVAL_MS)
    return () => {
      mountedRef.current = false
      clearInterval(interval)
      if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current)
    }
  }, [loadStatus])

  const maxPagesError =
    maxPages !== '' && (!/^\d+$/.test(maxPages) || parseInt(maxPages, 10) <= 0)
      ? 'Doit être un entier positif'
      : null

  const handleStart = async () => {
    if (maxPagesError) {
      showNotice({ type: 'error', message: 'Corrigez le champ "Max pages" avant de démarrer.' })
      return
    }
    try {
      setPendingAction('start')
      const maxPagesNum = maxPages ? parseInt(maxPages, 10) : undefined
      
      // Parse category list if enabled, otherwise use custom category or defaults
      let categories: CategoryConfig[]
      if (useCategoryList && categoryList.trim()) {
        // Parse category list (one per line, format: "wiki:category" or just "category")
        const lines = categoryList.trim().split('\n').filter(line => line.trim())
        categories = lines.map((line, index) => {
          const parts = line.split(':').map(p => p.trim())
          // Check if first part is a namespace prefix (not a wiki code)
          const namespacePrefixes = ['catégorie', 'category', 'wikipedia', 'file', 'image', 'template', 'modèle']
          if (parts.length === 2 && !namespacePrefixes.includes(parts[0].toLowerCase())) {
            return { wiki: parts[0], category: parts[1], priority: index + 1 }
          } else {
            // Either single part or namespace prefix - use default wiki and strip namespace if present
            let categoryName = line
            if (parts.length > 1 && namespacePrefixes.includes(parts[0].toLowerCase())) {
              categoryName = parts.slice(1).join(':').trim()
            }
            return { wiki: customWiki, category: categoryName, priority: index + 1 }
          }
        })
      } else if (customCategory.trim()) {
        categories = [{ wiki: customWiki, category: customCategory.trim(), priority: 1 }]
      } else {
        categories = DEFAULT_CATEGORIES
      }
      
      await domainEnrichmentApi.startEnrichment({
        categories,
        dry_run: dryRun,
        max_pages: maxPagesNum,
        keep_www: keepWww,
        sequential_write: sequentialWrite,
      })
      await loadStatus()
    } catch (error) {
      console.error('Failed to start enrichment:', error)
      showNotice({ type: 'error', message: getErrorMessage(error, "Échec du démarrage de l'enrichissement.") })
    } finally {
      if (mountedRef.current) setPendingAction(null)
    }
  }

  const handlePause = async () => {
    try {
      setPendingAction('pause')
      await domainEnrichmentApi.pauseEnrichment()
      await loadStatus()
    } catch (error) {
      console.error('Failed to pause enrichment:', error)
      showNotice({ type: 'error', message: getErrorMessage(error, 'Échec de la mise en pause.') })
    } finally {
      if (mountedRef.current) setPendingAction(null)
    }
  }

  const handleResume = async () => {
    try {
      setPendingAction('resume')
      await domainEnrichmentApi.resumeEnrichment()
      await loadStatus()
    } catch (error) {
      console.error('Failed to resume enrichment:', error)
      showNotice({ type: 'error', message: getErrorMessage(error, 'Échec de la reprise.') })
    } finally {
      if (mountedRef.current) setPendingAction(null)
    }
  }

  const handleCancel = async () => {
    try {
      setPendingAction('cancel')
      await domainEnrichmentApi.cancelEnrichment()
      setPreview(null)
      await loadStatus()
    } catch (error) {
      console.error('Failed to cancel enrichment:', error)
      showNotice({ type: 'error', message: getErrorMessage(error, "Échec de l'annulation.") })
    } finally {
      if (mountedRef.current) setPendingAction(null)
    }
  }

  const handlePreview = async () => {
    try {
      setPendingAction('preview')
      const response = await domainEnrichmentApi.getPreview()
      if (mountedRef.current) setPreview(response)
    } catch (error) {
      console.error('Failed to get preview:', error)
      showNotice({ type: 'error', message: getErrorMessage(error, "Échec du chargement de l'aperçu.") })
    } finally {
      if (mountedRef.current) setPendingAction(null)
    }
  }

  const handleWrite = async () => {
    if (!preview?.new_entries?.length) return

    try {
      setPendingAction('write')
      const result = await domainEnrichmentApi.writeToYaml({ entries: preview.new_entries })
      if (!mountedRef.current) return
      showNotice({
        type: 'success',
        message: result?.message || `Écriture réussie (${result?.entries_count ?? preview.new_entries.length} entrées).`,
      })
      setPreview(null)
      await loadStatus()
    } catch (error) {
      console.error('Failed to write to YAML:', error)
      showNotice({ type: 'error', message: getErrorMessage(error, "Erreur lors de l'écriture.") })
    } finally {
      if (mountedRef.current) setPendingAction(null)
    }
  }

  const handleReset = async () => {
    try {
      setPendingAction('reset')
      await domainEnrichmentApi.resetEnrichment()
      setPreview(null)
      await loadStatus()
      showNotice({ type: 'success', message: 'Service réinitialisé avec succès.' })
    } catch (error) {
      console.error('Failed to reset enrichment:', error)
      showNotice({ type: 'error', message: getErrorMessage(error, "Échec de la réinitialisation.") })
    } finally {
      if (mountedRef.current) setPendingAction(null)
    }
  }

  const isRunning = status?.state === 'running'
  const isPaused = status?.state === 'paused'
  const isIdle = status?.state === 'idle'
  const isCompleted = status?.state === 'completed'

  const iconStyle = { width: '14px', height: '14px' }
  const spinningIconStyle = { ...iconStyle, animation: 'de-spin 0.8s linear infinite' }

  return (
    <div style={{ maxWidth: '860px', margin: '0 auto' }}>
      <style>{`
        @keyframes de-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>

      {/* Notice banner (success / error) */}
      {notice && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 14px',
            marginBottom: '16px',
            borderRadius: '8px',
            fontSize: '11.5px',
            backgroundColor: notice.type === 'success' ? colors.successSoft : colors.errorSoft,
            border: `1px solid ${notice.type === 'success' ? colors.successBorder : colors.errorBorder}`,
            color: notice.type === 'success' ? colors.success : colors.error,
          }}
        >
          {notice.type === 'success' ? (
            <CheckCircle style={iconStyle} />
          ) : (
            <AlertTriangle style={iconStyle} />
          )}
          <span style={{ flex: 1 }}>{notice.message}</span>
          <button
            onClick={() => setNotice(null)}
            aria-label="Fermer"
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'inherit',
              display: 'flex',
              padding: 0,
            }}
          >
            <X style={{ width: '13px', height: '13px' }} />
          </button>
        </div>
      )}

      {/* Status fetch error */}
      {statusError && !status && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 14px',
            marginBottom: '16px',
            borderRadius: '8px',
            fontSize: '11.5px',
            backgroundColor: colors.errorSoft,
            border: `1px solid ${colors.errorBorder}`,
            color: colors.error,
          }}
        >
          <AlertTriangle style={iconStyle} />
          <span style={{ flex: 1 }}>{statusError}</span>
          <Button onClick={loadStatus} style={{ padding: '5px 10px', fontSize: '10.5px' }}>
            <RefreshCw style={iconStyle} />
            Réessayer
          </Button>
        </div>
      )}

      {/* Header with navigation button */}
      <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '15.5px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
            Enrichissement automatique
          </h2>
          <p style={{ fontSize: '10.5px', color: colors.textMuted, margin: '4px 0 0' }}>
            Enrichir domain_to_site_name depuis Wikidata
          </p>
        </div>
        <Link to="/domains/management">
          <Button variant="neutral">
            <Settings style={iconStyle} />
            Gestion des domaines
          </Button>
        </Link>
      </div>

      {/* Controls */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '11px',
            color: colors.textSecondary,
            opacity: isIdle ? 1 : 0.5,
          }}
        >
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            disabled={!isIdle || isBusy}
            style={{ cursor: !isIdle || isBusy ? 'not-allowed' : 'pointer' }}
          />
          Dry-run
        </label>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '11px',
            color: colors.textSecondary,
            opacity: isIdle ? 1 : 0.5,
          }}
        >
          <input
            type="checkbox"
            checked={keepWww}
            onChange={(e) => setKeepWww(e.target.checked)}
            disabled={!isIdle || isBusy}
            style={{ cursor: !isIdle || isBusy ? 'not-allowed' : 'pointer' }}
          />
          Garder www ( variantes ajoutées auto)
        </label>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '11px',
            color: colors.textSecondary,
            opacity: isIdle ? 1 : 0.5,
          }}
        >
          <input
            type="checkbox"
            checked={sequentialWrite}
            onChange={(e) => setSequentialWrite(e.target.checked)}
            disabled={!isIdle || isBusy}
            style={{ cursor: !isIdle || isBusy ? 'not-allowed' : 'pointer' }}
          />
          Écriture séquentielle (robuste aux crashs)
        </label>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '11px',
            color: colors.textSecondary,
            opacity: isIdle ? 1 : 0.5,
          }}
        >
          <span>Max pages:</span>
          <input
            type="number"
            min={1}
            value={maxPages}
            onChange={(e) => setMaxPages(e.target.value)}
            disabled={!isIdle || isBusy}
            placeholder="Illimité"
            style={{
              width: '80px',
              padding: '6px 10px',
              backgroundColor: colors.bgInput,
              border: `1px solid ${maxPagesError ? colors.error : colors.border}`,
              borderRadius: '6px',
              color: colors.textPrimary,
              fontSize: '11px',
              cursor: !isIdle || isBusy ? 'not-allowed' : 'text',
            }}
          />
        </label>
        {maxPagesError && (
          <span style={{ fontSize: '10px', color: colors.error }}>{maxPagesError}</span>
        )}

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', opacity: isIdle ? 1 : 0.5 }}>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '11px',
              color: colors.textSecondary,
            }}
          >
            <input
              type="checkbox"
              checked={useCategoryList}
              onChange={(e) => setUseCategoryList(e.target.checked)}
              disabled={!isIdle || isBusy}
              style={{ cursor: !isIdle || isBusy ? 'not-allowed' : 'pointer' }}
            />
            Liste de catégories
          </label>
        </div>

        {useCategoryList ? (
          <div style={{ opacity: isIdle ? 1 : 0.5, width: '100%' }}>
            <textarea
              value={categoryList}
              onChange={(e) => setCategoryList(e.target.value)}
              disabled={!isIdle || isBusy}
              placeholder="Une catégorie par ligne&#10;Format: wiki:catégorie ou juste catégorie&#10;Exemples:&#10;fr:Média français&#10;Agence de presse&#10;en:News websites"
              style={{
                width: '100%',
                minHeight: '80px',
                padding: '8px 10px',
                backgroundColor: colors.bgInput,
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                color: colors.textPrimary,
                fontSize: '11px',
                cursor: !isIdle || isBusy ? 'not-allowed' : 'text',
                resize: 'vertical',
                fontFamily: 'monospace',
              }}
            />
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', opacity: isIdle ? 1 : 0.5 }}>
            <select
              value={customWiki}
              onChange={(e) => setCustomWiki(e.target.value)}
              disabled={!isIdle || isBusy}
              style={{
                padding: '6px 10px',
                backgroundColor: colors.bgInput,
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                color: colors.textPrimary,
                fontSize: '11px',
                cursor: !isIdle || isBusy ? 'not-allowed' : 'pointer',
              }}
            >
              <option value="fr">fr</option>
              <option value="en">en</option>
              <option value="de">de</option>
              <option value="es">es</option>
              <option value="it">it</option>
            </select>
            <input
              type="text"
              value={customCategory}
              onChange={(e) => setCustomCategory(e.target.value)}
              disabled={!isIdle || isBusy}
              placeholder="Catégorie personnalisée"
              style={{
                width: '200px',
                padding: '6px 10px',
                backgroundColor: colors.bgInput,
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                color: colors.textPrimary,
                fontSize: '11px',
                cursor: !isIdle || isBusy ? 'not-allowed' : 'text',
              }}
            />
          </div>
        )}

        {isIdle && (
          <>
            <Button
              onClick={handleStart}
              disabled={isBusy || !!maxPagesError}
              variant="primary"
            >
              {pendingAction === 'start' ? <RefreshCw style={spinningIconStyle} /> : <Play style={iconStyle} />}
              Démarrer
            </Button>
          </>
        )}

        {isRunning && (
          <>
            <Button
              onClick={handlePause}
              disabled={isBusy}
              variant="neutral"
            >
              {pendingAction === 'pause' ? <RefreshCw style={spinningIconStyle} /> : <Pause style={iconStyle} />}
              Pause
            </Button>
            <Button
              onClick={handleCancel}
              disabled={isBusy}
              variant="danger"
            >
              {pendingAction === 'cancel' ? <RefreshCw style={spinningIconStyle} /> : <Square style={iconStyle} />}
              Annuler
            </Button>
          </>
        )}

        {isPaused && (
          <>
            <Button
              onClick={handleResume}
              disabled={isBusy}
              variant="primary"
            >
              {pendingAction === 'resume' ? <RefreshCw style={spinningIconStyle} /> : <Play style={iconStyle} />}
              Reprendre
            </Button>
          </>
        )}

        {isCompleted && (
          <>
            <Button
              onClick={handlePreview}
              disabled={isBusy}
              variant="neutral"
            >
              {pendingAction === 'preview' && <RefreshCw style={spinningIconStyle} />}
              Voir aperçu
            </Button>
            <Button
              onClick={handleReset}
              disabled={isBusy}
              variant="neutral"
            >
              <RefreshCw style={pendingAction === 'reset' ? spinningIconStyle : iconStyle} />
              Réinitialiser
            </Button>
          </>
        )}
      </div>

      {/* Status */}
      {status && (
        <div
          style={{
            padding: '16px',
            backgroundColor: colors.bgInput,
            border: `1px solid ${colors.border}`,
            borderRadius: '8px',
            marginBottom: '20px',
          }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
              gap: '12px',
              fontSize: '11px',
            }}
          >
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>État</div>
              <div style={{ color: colors.textPrimary, fontWeight: 500, textTransform: 'capitalize' }}>
                {status.state}
              </div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>Catégorie actuelle</div>
              <div style={{ color: colors.textPrimary, fontWeight: 500 }}>{status.current_category || '-'}</div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>Pages analysées</div>
              <div style={{ color: colors.textPrimary, fontWeight: 500 }}>
                {status.pages_analyzed} / {status.total_pages || '?'}
              </div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>Ignorés (déjà analysés)</div>
              <div style={{ color: colors.textSecondary, fontWeight: 500 }}>{status.skipped}</div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>P856 trouvés</div>
              <div style={{ color: colors.textPrimary, fontWeight: 500 }}>{status.p856_found}</div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>Nouveaux domaines</div>
              <div style={{ color: colors.success, fontWeight: 500 }}>{status.new_domains}</div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>Déjà présents</div>
              <div style={{ color: colors.textSecondary, fontWeight: 500 }}>{status.already_present}</div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>Conflits</div>
              <div style={{ color: status.conflicts > 0 ? colors.warning : colors.textSecondary, fontWeight: 500 }}>
                {status.conflicts}
              </div>
            </div>
            <div>
              <div style={{ color: colors.textMuted, marginBottom: '4px' }}>Erreurs</div>
              <div style={{ color: status.errors > 0 ? colors.error : colors.textSecondary, fontWeight: 500 }}>
                {status.errors}
              </div>
            </div>
          </div>

          {status.total_pages > 0 && (
            <div style={{ marginTop: '14px' }}>
              <div
                style={{
                  height: '6px',
                  borderRadius: '999px',
                  backgroundColor: colors.border,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, (status.pages_analyzed / status.total_pages) * 100)}%`,
                    backgroundColor: isRunning ? colors.accent : colors.success,
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>
            </div>
          )}

          {status.recent_activity.length > 0 && (
            <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: `1px solid ${colors.border}` }}>
              <div style={{ color: colors.textMuted, marginBottom: '8px', fontSize: '10px' }}>Activité récente</div>
              <div style={{ maxHeight: '120px', overflowY: 'auto', fontSize: '10px', color: colors.textSecondary }}>
                {status.recent_activity.map((activity, i) => (
                  <div key={i} style={{ padding: '2px 0' }}>
                    {activity}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Preview */}
      {preview && (
        <div
          style={{
            padding: '16px',
            backgroundColor: colors.successSoft,
            border: `1px solid ${colors.successBorder}`,
            borderRadius: '8px',
            marginBottom: '20px',
          }}
        >
          <h3 style={{ fontSize: '12px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 12px' }}>
            Aperçu des modifications
          </h3>

          <div style={{ marginBottom: '16px', display: 'flex', gap: '20px', fontSize: '11px', flexWrap: 'wrap' }}>
            <div>
              <span style={{ color: colors.success, fontWeight: 500 }}>{preview.summary.total}</span> nouvelles
              entrées
            </div>
            <div>
              <span style={{ color: colors.textSecondary }}>{preview.summary.already_present}</span> déjà présentes
            </div>
            <div>
              <span style={{ color: colors.warning }}>{preview.summary.conflicts}</span> conflits
            </div>
            {preview.summary.review_required > 0 && (
              <div>
                <span style={{ color: colors.warning }}>{preview.summary.review_required}</span> à vérifier
              </div>
            )}
            {preview.summary.errors > 0 && (
              <div>
                <span style={{ color: colors.error }}>{preview.summary.errors}</span> erreurs
              </div>
            )}
          </div>

          {preview.new_entries.length === 0 ? (
            <div style={{ fontSize: '11px', color: colors.textMuted, marginBottom: '16px' }}>
              Aucune nouvelle entrée à écrire.
            </div>
          ) : (
            <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '16px' }}>
              {preview.new_entries.slice(0, PREVIEW_ROW_LIMIT).map((entry: PreviewEntry, i: number) => (
                <div
                  key={`${entry.domain}-${i}`}
                  style={{ padding: '6px 0', borderBottom: `1px solid ${colors.border}`, fontSize: '10px' }}
                >
                  <span style={{ color: colors.success }}>+ {entry.domain}</span>
                  <span style={{ color: colors.textMuted }}> → </span>
                  <span style={{ color: colors.textPrimary }}>{entry.site_name}</span>
                </div>
              ))}
              {preview.new_entries.length > PREVIEW_ROW_LIMIT && (
                <div style={{ padding: '6px 0', fontSize: '10px', color: colors.textMuted }}>
                  ... et {preview.new_entries.length - PREVIEW_ROW_LIMIT} autres
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px' }}>
            <Button
              onClick={handleWrite}
              disabled={isBusy || preview.new_entries.length === 0}
              variant="primary"
              style={{ backgroundColor: colors.success, color: '#ffffff', border: '1px solid #10b981' }}
            >
              {pendingAction === 'write' ? <RefreshCw style={spinningIconStyle} /> : <Save style={iconStyle} />}
              Confirmer l'écriture
            </Button>
            <Button
              onClick={() => setPreview(null)}
              disabled={isBusy}
              variant="neutral"
            >
              Fermer l'aperçu
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}