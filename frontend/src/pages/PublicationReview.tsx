import { useCallback, useEffect, useRef, useState, forwardRef } from 'react'
import { AlertTriangle, FileText, Eye, EyeOff, Send, ShieldCheck, Loader2 } from 'lucide-react'
import { publicationApi } from '../api/publication.api'
import { diffApi } from '../api/diff.api'
import { useNavigate, useSearchParams } from 'react-router-dom'

// ============================================================
// Types
// ============================================================

interface DiffStats {
  changes_count?: number
  additions?: number
  deletions?: number
}

interface DiffResult {
  diff: string
  stats?: DiffStats
}

interface ValidationResult {
  valid: boolean
  errors?: string[]
  warnings?: string[]
}

interface PublishResponse {
  success: boolean
  error?: string
}

interface ApiErrorLike {
  message?: string
  userMessage?: string
}

function getErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object') {
    const e = err as ApiErrorLike
    return e.userMessage || e.message || fallback
  }
  return fallback
}

const DEFAULT_SUMMARY = 'Réparation de liens morts via OviX'

// ============================================================
// Design tokens
// ============================================================

const colors = {
  bg: '#0a0a0a',
  surface: '#161616',
  surfaceRaised: '#1a1a1a',
  border: '#2a2a2a',
  borderHover: '#3a3a3a',
  borderFocus: '#6b8afd',
  text: '#f5f5f5',
  textMuted: '#a0a0a0',
  textFaint: '#666666',
  accent: '#6b8afd',
  danger: '#ff6b6b',
  dangerBg: 'rgba(239, 68, 68, 0.08)',
  dangerBorder: 'rgba(239, 68, 68, 0.35)',
  warning: '#f59e0b',
  warningBg: 'rgba(245, 158, 11, 0.08)',
  warningBorder: 'rgba(245, 158, 11, 0.35)',
  success: '#22c55e',
}

const transition = 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)'

const styles = {
  page: { display: 'flex', flexDirection: 'column', gap: '20px', animation: 'fadeIn 0.25s ease-out' } as const,
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' } as const,
  title: { fontSize: '22px', fontWeight: 650, color: colors.text, margin: 0, letterSpacing: '-0.01em' } as const,
  subtitle: {
    color: colors.textMuted,
    marginTop: '6px',
    fontSize: '14px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  } as const,
  backBtn: {
    padding: '8px 14px',
    backgroundColor: 'transparent',
    border: `1px solid ${colors.border}`,
    borderRadius: '7px',
    color: colors.textMuted,
    fontSize: '13px',
    fontWeight: 500,
    cursor: 'pointer',
    transition,
  } as const,
  emptyState: {
    display: 'flex',
    justifyContent: 'center',
    padding: '56px 24px',
    backgroundColor: colors.surface,
    borderRadius: '10px',
    border: `1px dashed ${colors.border}`,
  } as const,
  emptyStateContent: { textAlign: 'center', color: colors.textFaint, maxWidth: '320px' } as const,
  emptyStateIcon: { width: '40px', height: '40px', color: colors.border, margin: '0 auto 16px' } as const,
  banner: {
    padding: '13px 14px',
    borderRadius: '8px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '10px',
    fontSize: '13.5px',
    lineHeight: 1.5,
    animation: 'slideIn 0.2s ease-out',
  } as const,
  bannerWarning: {
    backgroundColor: colors.warningBg,
    border: `1px solid ${colors.warningBorder}`,
    color: colors.warning,
  } as const,
  bannerError: {
    backgroundColor: colors.dangerBg,
    border: `1px solid ${colors.dangerBorder}`,
    color: colors.danger,
  } as const,
  bannerIcon: { width: '16px', height: '16px', flexShrink: 0, marginTop: '1px' } as const,
  card: {
    backgroundColor: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: '10px',
    padding: '22px',
    transition,
  } as const,
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', gap: '12px' } as const,
  cardLabel: {
    fontSize: '12.5px',
    fontWeight: 600,
    color: colors.textFaint,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    margin: 0,
  } as const,
  toggleButton: {
    padding: '7px 12px',
    backgroundColor: colors.surfaceRaised,
    border: `1px solid ${colors.border}`,
    borderRadius: '7px',
    color: colors.textMuted,
    fontSize: '13px',
    fontWeight: 500,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
    transition,
  } as const,
  diffBox: {
    backgroundColor: colors.bg,
    padding: '16px',
    borderRadius: '8px',
    maxHeight: '400px',
    overflow: 'auto',
    border: `1px solid ${colors.border}`,
  } as const,
  diffStatsRow: { display: 'flex', gap: '14px', marginBottom: '12px', flexWrap: 'wrap' } as const,
  diffStatChip: {
    fontSize: '12px',
    color: colors.textMuted,
    backgroundColor: colors.surfaceRaised,
    border: `1px solid ${colors.border}`,
    borderRadius: '5px',
    padding: '3px 8px',
    fontVariantNumeric: 'tabular-nums',
  } as const,
  diffContent: { fontSize: '13px', lineHeight: '1.65', color: colors.text } as const,
  placeholderBox: {
    textAlign: 'center',
    padding: '36px',
    color: colors.textFaint,
    fontSize: '13.5px',
  } as const,
  formGroup: { display: 'flex', flexDirection: 'column', gap: '18px' } as const,
  fieldLabel: {
    display: 'block',
    fontSize: '13.5px',
    color: colors.textMuted,
    marginBottom: '8px',
    fontWeight: 600,
  } as const,
  fieldLabelHint: { color: colors.textFaint, fontWeight: 400 } as const,
  textarea: {
    width: '100%',
    padding: '12px 13px',
    backgroundColor: colors.bg,
    border: `1px solid ${colors.border}`,
    borderRadius: '8px',
    color: colors.text,
    fontSize: '13.5px',
    resize: 'vertical',
    fontFamily: "'SF Mono', 'Fira Code', Consolas, monospace",
    boxSizing: 'border-box',
    lineHeight: 1.55,
    transition,
  } as const,
  fieldFooter: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px', gap: '12px' } as const,
  fieldHint: { fontSize: '12px', color: colors.textFaint, margin: 0 } as const,
  resetButton: {
    padding: '4px 9px',
    fontSize: '12px',
    fontWeight: 500,
    backgroundColor: 'transparent',
    border: `1px solid ${colors.border}`,
    borderRadius: '5px',
    color: colors.textMuted,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    transition,
  } as const,
  checkboxRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '11px',
    padding: '12px 14px',
    backgroundColor: colors.bg,
    borderRadius: '8px',
    border: `1px solid ${colors.border}`,
  } as const,
  checkbox: { width: '16px', height: '16px', cursor: 'pointer', accentColor: colors.accent } as const,
  checkboxLabel: { fontSize: '13.5px', color: colors.textMuted, cursor: 'pointer', userSelect: 'none' } as const,
  tip: {
    display: 'flex',
    gap: '10px',
    alignItems: 'flex-start',
    padding: '12px 14px',
    backgroundColor: colors.surfaceRaised,
    borderRadius: '8px',
    border: `1px solid ${colors.border}`,
    fontSize: '12.5px',
    color: colors.textMuted,
    lineHeight: 1.5,
  } as const,
  actions: { display: 'flex', gap: '10px', justifyContent: 'flex-end', flexWrap: 'wrap' } as const,
  btnBase: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    padding: '9px 16px',
    borderRadius: '8px',
    fontSize: '13.5px',
    fontWeight: 600,
    cursor: 'pointer',
    border: '1px solid transparent',
    transition,
  } as const,
  btnSecondary: {
    backgroundColor: colors.surfaceRaised,
    border: `1px solid ${colors.border}`,
    color: colors.textMuted,
  } as const,
  btnPrimary: {
    backgroundColor: colors.accent,
    border: `1px solid ${colors.accent}`,
    color: '#0a0a0a',
  } as const,
  btnDanger: {
    backgroundColor: colors.danger,
    border: `1px solid ${colors.danger}`,
    color: '#1a0000',
  } as const,
  btnDisabled: { opacity: 0.5, cursor: 'not-allowed' } as const,
  overlay: {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.72)',
    backdropFilter: 'blur(2px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10000,
    animation: 'fadeIn 0.15s ease-out',
    padding: '16px',
  } as const,
  dialog: {
    backgroundColor: colors.surfaceRaised,
    border: `1px solid ${colors.borderHover}`,
    borderRadius: '12px',
    padding: '26px',
    maxWidth: '420px',
    width: '100%',
    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
    animation: 'popIn 0.18s cubic-bezier(0.2, 0.9, 0.3, 1.1)',
  } as const,
  dialogIconWrap: {
    width: '40px',
    height: '40px',
    borderRadius: '10px',
    backgroundColor: colors.dangerBg,
    border: `1px solid ${colors.dangerBorder}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: '14px',
  } as const,
  dialogTitle: { fontSize: '17px', fontWeight: 650, color: colors.text, margin: '0 0 10px', letterSpacing: '-0.01em' } as const,
  dialogBody: { color: colors.textMuted, marginBottom: '22px', lineHeight: '1.55', fontSize: '13.5px' } as const,
  dialogWarning: { color: colors.danger, fontWeight: 600 } as const,
  dialogActions: { display: 'flex', gap: '10px', justifyContent: 'flex-end' } as const,
  spin: { animation: 'spin 0.7s linear infinite' } as const,
}

const keyframes = `
@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
@keyframes slideIn { from { opacity: 0; transform: translateY(-4px) } to { opacity: 1; transform: translateY(0) } }
@keyframes popIn { from { opacity: 0; transform: scale(0.96) translateY(4px) } to { opacity: 1; transform: scale(1) translateY(0) } }
@keyframes spin { to { transform: rotate(360deg) } }
`

// ============================================================
// Composants d'UI internes (boutons réutilisables, cohérents)
// ============================================================

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'secondary' | 'primary' | 'danger'
  loading?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', loading, disabled, children, style, ...rest },
  ref
) {
  const variantStyle = variant === 'primary' ? styles.btnPrimary : variant === 'danger' ? styles.btnDanger : styles.btnSecondary
  const isDisabled = disabled || loading
  return (
    <button
      ref={ref}
      type="button"
      disabled={isDisabled}
      style={{
        ...styles.btnBase,
        ...variantStyle,
        ...(isDisabled ? styles.btnDisabled : {}),
        ...style,
      }}
      onMouseEnter={(e) => {
        if (isDisabled) return
        e.currentTarget.style.filter = 'brightness(1.12)'
        e.currentTarget.style.transform = 'translateY(-1px)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.filter = 'none'
        e.currentTarget.style.transform = 'none'
      }}
      {...rest}
    >
      {loading && <Loader2 style={{ width: 14, height: 14, ...styles.spin }} aria-hidden="true" />}
      {children}
    </button>
  )
})

// ============================================================
// Composant principal
// ============================================================

export default function PublicationReview() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const articleTitle = searchParams.get('title')?.trim() || ''
  const correctedContent = searchParams.get('content') || ''

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [diff, setDiff] = useState<DiffResult | null>(null)
  const [loadingDiff, setLoadingDiff] = useState(false)
  const [dryRun, setDryRun] = useState(true)
  const [summary, setSummary] = useState(DEFAULT_SUMMARY)
  const [showDiff, setShowDiff] = useState(true)
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null)
  const [validating, setValidating] = useState(false)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)

  const confirmButtonRef = useRef<HTMLButtonElement>(null)
  const summaryTrimmed = summary.trim()
  const canSubmit = summaryTrimmed.length > 0

  // ---- Chargement du diff ----
  const loadDiff = useCallback(async () => {
    if (!articleTitle || !correctedContent) return
    setLoadingDiff(true)
    setError(null)
    try {
      const response = await diffApi.generateDiff({
        original: '',
        corrected: correctedContent,
        diff_type: 'html',
      })
      setDiff(response)
    } catch (err) {
      setError(getErrorMessage(err, 'Erreur lors de la génération du diff'))
    } finally {
      setLoadingDiff(false)
    }
  }, [articleTitle, correctedContent])

  useEffect(() => {
    loadDiff()
  }, [loadDiff])

  // Toute modification du contenu ou du résumé invalide une validation précédente,
  // pour éviter de publier avec une validation devenue obsolète.
  useEffect(() => {
    setValidationResult(null)
  }, [summary, correctedContent, dryRun])

  // ---- Accessibilité de la modale : focus + Échap ----
  useEffect(() => {
    if (!showConfirmDialog) return
    confirmButtonRef.current?.focus()
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) setShowConfirmDialog(false)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [showConfirmDialog, loading])

  // ---- Validation ----
  // Retourne le résultat frais : ne jamais relire `validationResult` (state) juste après
  // un await, React ne l'aura pas encore mis à jour (batching asynchrone). C'est ce décalage
  // qui, dans la version précédente, faisait échouer silencieusement la publication.
  const validateBeforePublish = useCallback(async (): Promise<ValidationResult | null> => {
    if (!canSubmit) {
      setError("Le résumé de l'édition ne peut pas être vide.")
      return null
    }
    setValidating(true)
    setError(null)
    try {
      const response = await diffApi.validateDiff({
        article_title: articleTitle,
        corrected_content: correctedContent,
        summary: summaryTrimmed,
        dry_run: dryRun,
      })
      setValidationResult(response)
      if (!response.valid) {
        setError('Validation échouée : ' + (response.errors?.join(', ') || 'Erreur inconnue'))
      }
      return response
    } catch (err) {
      setError(getErrorMessage(err, 'Erreur lors de la validation'))
      return null
    } finally {
      setValidating(false)
    }
  }, [articleTitle, correctedContent, summaryTrimmed, dryRun, canSubmit])

  // ---- Publication ----
  const executePublish = useCallback(async () => {
    setError(null)

    let currentValidation = validationResult
    if (!currentValidation?.valid) {
      currentValidation = await validateBeforePublish()
      if (!currentValidation?.valid) {
        setShowConfirmDialog(false)
        return
      }
    }

    setLoading(true)
    try {
      const response: PublishResponse = await publicationApi.publish({
        article_title: articleTitle,
        corrected_content: correctedContent,
        original_content: '',
        summary: summaryTrimmed,
        dry_run: dryRun,
      })

      if (response.success) {
        if (dryRun) {
          window.alert("Simulation réussie ! Aucune modification n'a été appliquée.")
        } else {
          window.alert('Publication réussie !')
          navigate('/history/published')
        }
      } else {
        setError(response.error || 'Erreur lors de la publication')
      }
    } catch (err) {
      setError(getErrorMessage(err, 'Erreur lors de la publication'))
    } finally {
      setLoading(false)
      setShowConfirmDialog(false)
    }
  }, [articleTitle, correctedContent, summaryTrimmed, dryRun, validationResult, validateBeforePublish, navigate])

  const handlePublishClick = useCallback(() => {
    if (!canSubmit) {
      setError("Le résumé de l'édition ne peut pas être vide.")
      return
    }
    if (dryRun) {
      executePublish()
    } else {
      setShowConfirmDialog(true)
    }
  }, [dryRun, executePublish, canSubmit])

  // ============================================================
  // Rendu : état vide
  // ============================================================

  if (!articleTitle) {
    return (
      <div style={styles.page}>
        <style>{keyframes}</style>
        <div>
          <h2 style={styles.title}>Révision de Publication</h2>
          <p style={styles.subtitle}>Aucun article spécifié</p>
        </div>
        <div style={styles.emptyState}>
          <div style={styles.emptyStateContent}>
            <FileText style={styles.emptyStateIcon} aria-hidden="true" />
            <div style={{ fontSize: '15px', marginBottom: '6px', color: colors.textMuted, fontWeight: 500 }}>
              Aucun article à réviser
            </div>
            <div style={{ fontSize: '13.5px' }}>Sélectionnez un article depuis l'historique pour commencer.</div>
          </div>
        </div>
      </div>
    )
  }

  // ============================================================
  // Rendu principal
  // ============================================================

  return (
    <div style={styles.page}>
      <style>{keyframes}</style>

      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Révision de Publication</h2>
          <p style={styles.subtitle}>{articleTitle}</p>
        </div>
        <Button variant="secondary" style={styles.backBtn} onClick={() => navigate('/history/analyzed')}>
          Retour
        </Button>
      </div>

      {validationResult?.warnings && validationResult.warnings.length > 0 && (
        <div style={{ ...styles.banner, ...styles.bannerWarning }} role="alert">
          <AlertTriangle style={styles.bannerIcon} aria-hidden="true" />
          <div>
            <strong>Attention :</strong> {validationResult.warnings.join(', ')}
          </div>
        </div>
      )}

      {validationResult?.valid && !error && (
        <div
          style={{
            ...styles.banner,
            backgroundColor: 'rgba(34, 197, 94, 0.08)',
            border: '1px solid rgba(34, 197, 94, 0.3)',
            color: colors.success,
          }}
          role="status"
        >
          <ShieldCheck style={styles.bannerIcon} aria-hidden="true" />
          <div>Validation réussie — prêt à publier.</div>
        </div>
      )}

      {error && (
        <div style={{ ...styles.banner, ...styles.bannerError }} role="alert">
          <AlertTriangle style={styles.bannerIcon} aria-hidden="true" />
          <div>{error}</div>
        </div>
      )}

      {/* Diff */}
      <section style={styles.card} aria-labelledby="diff-heading">
        <div style={styles.cardHeader}>
          <h3 id="diff-heading" style={styles.cardLabel}>
            Diff des modifications
          </h3>
          <button
            type="button"
            style={styles.toggleButton}
            onClick={() => setShowDiff(!showDiff)}
            aria-pressed={showDiff}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = colors.borderHover
              e.currentTarget.style.color = colors.text
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = colors.border
              e.currentTarget.style.color = colors.textMuted
            }}
          >
            {showDiff ? (
              <EyeOff style={{ width: '15px', height: '15px' }} aria-hidden="true" />
            ) : (
              <Eye style={{ width: '15px', height: '15px' }} aria-hidden="true" />
            )}
            {showDiff ? 'Masquer' : 'Afficher'}
          </button>
        </div>

        {loadingDiff ? (
          <div style={styles.placeholderBox} role="status" aria-live="polite">
            <Loader2 style={{ width: 18, height: 18, ...styles.spin, margin: '0 auto 10px', color: colors.textMuted }} />
            <div>Chargement du diff...</div>
          </div>
        ) : showDiff && diff ? (
          <div style={styles.diffBox}>
            <div style={styles.diffStatsRow}>
              <span style={styles.diffStatChip}>{diff.stats?.changes_count ?? 0} changements</span>
              <span style={{ ...styles.diffStatChip, color: colors.success }}>+{diff.stats?.additions ?? 0}</span>
              <span style={{ ...styles.diffStatChip, color: colors.danger }}>−{diff.stats?.deletions ?? 0}</span>
            </div>
            {/* HTML de confiance (généré par le backend). Si cette source devient un jour
                partiellement fournie par l'utilisateur, prévoir une sanitisation (ex: DOMPurify). */}
            <div style={styles.diffContent} dangerouslySetInnerHTML={{ __html: diff.diff }} />
          </div>
        ) : (
          <div style={styles.placeholderBox}>Diff masqué</div>
        )}
      </section>

      {/* Options */}
      <section style={styles.card} aria-labelledby="options-heading">
        <h3 id="options-heading" style={{ ...styles.cardLabel, marginBottom: '16px' }}>
          Options de publication
        </h3>

        <div style={styles.formGroup}>
          <div>
            <label htmlFor="edit-summary" style={styles.fieldLabel}>
              Résumé de l'édition <span style={styles.fieldLabelHint}>(modifiable)</span>
            </label>
            <textarea
              id="edit-summary"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={4}
              placeholder="Ex: Correction liens morts 404 - 410 - fix [[Wikipédia:Vérifiabilité|Vérifiabilité]] : domain → archive..."
              style={styles.textarea}
              aria-invalid={!canSubmit}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = colors.borderFocus
                e.currentTarget.style.boxShadow = `0 0 0 3px rgba(107, 138, 253, 0.15)`
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = colors.border
                e.currentTarget.style.boxShadow = 'none'
              }}
            />
            <div style={styles.fieldFooter}>
              <p style={styles.fieldHint}>Ce résumé sera affiché dans l'historique des modifications de l'article</p>
              <button
                type="button"
                style={styles.resetButton}
                onClick={() => setSummary(DEFAULT_SUMMARY)}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = colors.borderHover)}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = colors.border)}
              >
                Réinitialiser
              </button>
            </div>
          </div>

          <div style={styles.checkboxRow}>
            <input
              type="checkbox"
              id="dry-run"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              style={styles.checkbox}
            />
            <label htmlFor="dry-run" style={styles.checkboxLabel}>
              Mode simulation (dry-run) — Aucune modification réelle
            </label>
          </div>

          <div style={styles.tip} role="note">
            <ShieldCheck style={{ width: 15, height: 15, color: colors.textFaint, flexShrink: 0, marginTop: '1px' }} aria-hidden="true" />
            <div>
              <strong>Conseil :</strong> Commencez toujours en mode simulation pour vérifier les modifications avant
              de publier réellement.
            </div>
          </div>
        </div>
      </section>

      {/* Actions */}
      <div style={styles.actions}>
        <Button variant="secondary" onClick={validateBeforePublish} loading={validating} disabled={!canSubmit}>
          {validating ? 'Validation...' : 'Valider'}
        </Button>
        <Button variant="primary" onClick={handlePublishClick} loading={loading} disabled={validating || !canSubmit}>
          {!loading && <Send style={{ width: 14, height: 14 }} aria-hidden="true" />}
          {loading ? 'Publication...' : dryRun ? 'Simuler' : 'Publier'}
        </Button>
      </div>

      {/* Confirmation */}
      {showConfirmDialog && (
        <div
          style={styles.overlay}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && !loading) setShowConfirmDialog(false)
          }}
        >
          <div
            style={styles.dialog}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            aria-describedby="confirm-desc"
          >
            <div style={styles.dialogIconWrap}>
              <AlertTriangle style={{ width: 20, height: 20, color: colors.danger }} aria-hidden="true" />
            </div>
            <h3 id="confirm-title" style={styles.dialogTitle}>
              Confirmer la publication
            </h3>
            <div id="confirm-desc" style={styles.dialogBody}>
              <p>Vous êtes sur le point de publier l'article <strong style={{ color: colors.text }}>{articleTitle}</strong>{' '}
              sur Wikipedia.</p>
              <br />
              <div style={{ backgroundColor: colors.surface, border: `1px solid ${colors.border}`, borderRadius: '6px', padding: '12px', marginBottom: '12px' }}>
                <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '4px', fontWeight: 500 }}>
                  Résumé de l'édition :
                </div>
                <div style={{ fontSize: '13px', color: colors.text, lineHeight: '1.4', wordBreak: 'break-word' }}>
                  {summaryTrimmed || '(vide)'}
                </div>
              </div>
              <span style={styles.dialogWarning}>Cette action est irréversible.</span>
            </div>
            <div style={styles.dialogActions}>
              <Button variant="secondary" onClick={() => setShowConfirmDialog(false)} disabled={loading}>
                Annuler
              </Button>
              <Button ref={confirmButtonRef} variant="danger" onClick={executePublish} loading={loading}>
                {loading ? 'Publication...' : 'Confirmer la publication'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}