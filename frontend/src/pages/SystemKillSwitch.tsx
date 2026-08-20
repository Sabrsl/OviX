import { Shield, AlertTriangle } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { systemApi } from '../api/system.api'

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
} as const

export default function SystemKillSwitch() {
  const [killSwitchStatus, setKillSwitchStatus] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)
  const [reason, setReason] = useState('')
  const [showReasonForm, setShowReasonForm] = useState(false)
  const [username, setUsername] = useState<string>('')
  const [isPolling, setIsPolling] = useState(false) // Auto-poll disabled by default to prevent UI blocking
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStatus = async (isInitial = false) => {
    if (isInitial) setLoading(true)
    setError(null)
    try {
      const status = await systemApi.getKillSwitchStatus()
      setKillSwitchStatus(status)
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la récupération du statut')
    } finally {
      if (isInitial) setLoading(false)
    }
  }

  const fetchUsername = async () => {
    try {
      const { authApi } = await import('../api/auth.api')
      const authStatus = await authApi.getStatus()
      setUsername(authStatus.username || 'Unknown')
    } catch (err) {
      console.error('Failed to fetch username:', err)
      setUsername('Unknown')
    }
  }

  const activateKillSwitch = async () => {
    if (!reason.trim()) {
      setError('Veuillez spécifier une raison pour l\'activation')
      setShowReasonForm(true)
      return
    }

    if (!confirm(`Êtes-vous sûr de vouloir activer l'arrêt d'urgence ?\n\nRaison: ${reason}\n\nCela arrêtera immédiatement toutes les opérations Wikipédia.`)) {
      return
    }

    setActivating(true)
    try {
      await systemApi.activateKillSwitch(reason, username)
      setReason('')
      setShowReasonForm(false)
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de l\'activation')
    } finally {
      setActivating(false)
    }
  }

  const deactivateKillSwitch = async () => {
    if (!confirm('Êtes-vous sûr de vouloir désactiver l\'arrêt d\'urgence ?')) {
      return
    }

    setActivating(true)
    try {
      await systemApi.deactivateKillSwitch('Désactivation manuelle via interface web', username)
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la désactivation')
    } finally {
      setActivating(false)
    }
  }

  // P1 CRITICAL FIX: Auto-polling for real-time Kill Switch status updates
  useEffect(() => {
    if (isPolling) {
      pollingIntervalRef.current = setInterval(() => {
        fetchStatus()
      }, 5000) // Poll every 5 seconds
    } else {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [isPolling])

  useEffect(() => {
    fetchStatus(true)
    fetchUsername()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const isActive = killSwitchStatus?.enabled || false

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.35s ease-out' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '19px', fontWeight: 600, color: COLORS.textPrimary, letterSpacing: '-0.01em', margin: 0 }}>
            Arrêt d'urgence
          </h2>
          <p style={{ color: COLORS.textSecondary, marginTop: '3px', fontSize: '12.5px' }}>
            Arrêt d'urgence pour toutes les opérations Wikipédia
          </p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            color: COLORS.danger,
            fontSize: '12.5px',
            padding: '10px 14px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            borderRadius: '7px',
            animation: 'fadeIn 0.2s ease-out',
          }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <SkeletonPanel />
      ) : (
        <>
          {/* Status card */}
          <div
            style={{
              backgroundColor: COLORS.bgPanel,
              border: `1px solid ${isActive ? COLORS.danger : COLORS.border}`,
              borderRadius: '10px',
              padding: '20px',
              transition: 'border-color 0.2s',
              animation: 'fadeInUp 0.3s ease-out 0ms both',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
              <div
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '9px',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: isActive ? 'rgba(239, 68, 68, 0.1)' : COLORS.bgSubtle,
                }}
              >
                <Shield style={{ width: '18px', height: '18px', color: isActive ? COLORS.danger : COLORS.textMuted }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3 style={{ fontSize: '15px', fontWeight: 500, color: COLORS.textPrimary, marginBottom: '10px', marginTop: 0 }}>
                  Statut de l'arrêt d'urgence
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                  <div
                    style={{
                      width: '7px',
                      height: '7px',
                      backgroundColor: isActive ? COLORS.danger : COLORS.success,
                      borderRadius: '50%',
                    }}
                  />
                  <span style={{ color: COLORS.textSecondary, fontSize: '13px' }}>
                    {isActive ? "Actif — système à l'arrêt" : 'Inactif — système opérationnel'}
                  </span>
                </div>

                {isActive && (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                      backgroundColor: COLORS.bgInput,
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: '7px',
                      padding: '12px 14px',
                      marginBottom: '14px',
                    }}
                  >
                    {killSwitchStatus?.reason && (
                      <DetailRow label="Raison" value={killSwitchStatus.reason} />
                    )}
                    {killSwitchStatus?.requested_by && (
                      <DetailRow label="Activé par" value={killSwitchStatus.requested_by} />
                    )}
                    {killSwitchStatus?.requested_at && (
                      <DetailRow label="Activé le" value={new Date(killSwitchStatus.requested_at).toLocaleString('fr-FR')} />
                    )}
                    {killSwitchStatus?.trigger_source && (
                      <DetailRow label="Source" value={killSwitchStatus.trigger_source} />
                    )}
                  </div>
                )}

                <p style={{ fontSize: '12.5px', color: COLORS.textMuted, marginBottom: '16px', lineHeight: '150%' }}>
                  L'arrêt d'urgence permet d'arrêter immédiatement toutes les opérations Wikipédia en cas d'urgence.
                  Lorsqu'il est activé, aucune nouvelle publication ne sera traitée.
                </p>

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <SecondaryButton onClick={() => fetchStatus()} disabled={activating}>
                    {activating ? 'Chargement...' : 'Actualiser'}
                  </SecondaryButton>
                  <button
                    onClick={() => setIsPolling(!isPolling)}
                    style={{
                      padding: '9px 15px',
                      backgroundColor: isPolling ? COLORS.success : COLORS.bgSubtle,
                      border: `1px solid ${isPolling ? COLORS.success : COLORS.border}`,
                      borderRadius: '6px',
                      color: isPolling ? '#ffffff' : COLORS.textSecondary,
                      fontSize: '12.5px',
                      fontWeight: 500,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'background-color 0.15s, border-color 0.15s, color 0.15s',
                    }}
                  >
                    <span
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        backgroundColor: isPolling ? '#ffffff' : COLORS.textMuted,
                        animation: isPolling ? 'pulse 1.5s ease-in-out infinite' : 'none',
                      }}
                    />
                    {isPolling ? 'Suivi actif' : 'Suivi inactif'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Action card */}
          <div
            style={{
              backgroundColor: COLORS.bgPanel,
              border: `1px solid ${isActive ? COLORS.danger : 'rgba(245, 158, 11, 0.3)'}`,
              borderRadius: '10px',
              padding: '20px',
              animation: 'fadeInUp 0.3s ease-out 60ms both',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
              <div
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '9px',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: isActive ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                }}
              >
                <AlertTriangle style={{ width: '18px', height: '18px', color: isActive ? COLORS.danger : COLORS.warning }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3 style={{ fontSize: '15px', fontWeight: 500, color: COLORS.textPrimary, marginBottom: '8px', marginTop: 0 }}>
                  {isActive ? "Désactivation de l'arrêt d'urgence" : "Activation d'urgence"}
                </h3>
                <p style={{ fontSize: '12.5px', color: COLORS.textMuted, marginBottom: '16px', lineHeight: '150%' }}>
                  {isActive
                    ? "Désactivez l'arrêt d'urgence pour reprendre les opérations Wikipédia normales."
                    : "Activez l'arrêt d'urgence uniquement en cas d'urgence. Cela arrêtera immédiatement toutes les opérations Wikipédia en cours et planifiées."}
                </p>

                {!isActive && showReasonForm && (
                  <div style={{ marginBottom: '16px', animation: 'fadeIn 0.2s ease-out' }}>
                    <label style={{ display: 'block', fontSize: '12.5px', color: COLORS.textSecondary, marginBottom: '7px' }}>
                      Raison de l'activation (obligatoire)
                    </label>
                    <textarea
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      rows={3}
                      placeholder="Décrivez la raison de l'activation de l'arrêt d'urgence..."
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        backgroundColor: COLORS.bgInput,
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: '7px',
                        color: COLORS.textPrimary,
                        fontSize: '12.5px',
                        resize: 'vertical',
                        outline: 'none',
                        boxSizing: 'border-box',
                        fontFamily: 'inherit',
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
                  </div>
                )}

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {!isActive && !showReasonForm && (
                    <SecondaryButton onClick={() => setShowReasonForm(true)}>
                      Spécifier une raison
                    </SecondaryButton>
                  )}
                  <button
                    onClick={isActive ? deactivateKillSwitch : activateKillSwitch}
                    disabled={activating || (!isActive && !showReasonForm)}
                    style={{
                      padding: '9px 16px',
                      backgroundColor: isActive ? COLORS.accent : COLORS.danger,
                      border: `1px solid ${isActive ? COLORS.accent : COLORS.danger}`,
                      borderRadius: '6px',
                      color: '#ffffff',
                      fontSize: '12.5px',
                      fontWeight: 500,
                      cursor: activating || (!isActive && !showReasonForm) ? 'not-allowed' : 'pointer',
                      opacity: activating || (!isActive && !showReasonForm) ? 0.5 : 1,
                      transition: 'filter 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      if (activating || (!isActive && !showReasonForm)) return
                      e.currentTarget.style.filter = 'brightness(1.1)'
                    }}
                    onMouseLeave={(e) => (e.currentTarget.style.filter = 'brightness(1)')}
                  >
                    {activating ? 'Traitement...' : isActive ? "Désactiver l'arrêt d'urgence" : "Activer l'arrêt d'urgence"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @media (prefers-reduced-motion: reduce) {
          * { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
        }
      `}</style>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ fontSize: '12.5px', color: COLORS.textMuted, display: 'flex', gap: '6px' }}>
      <span style={{ color: COLORS.textSecondary, fontWeight: 500, flexShrink: 0 }}>{label} :</span>
      <span style={{ color: COLORS.textMuted }}>{value}</span>
    </div>
  )
}

function SecondaryButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '9px 15px',
        backgroundColor: COLORS.bgSubtle,
        border: `1px solid ${COLORS.border}`,
        borderRadius: '6px',
        color: COLORS.textSecondary,
        fontSize: '12.5px',
        fontWeight: 500,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        transition: 'background-color 0.15s, border-color 0.15s, color 0.15s',
      }}
      onMouseEnter={(e) => {
        if (disabled) return
        e.currentTarget.style.backgroundColor = '#1f1f1f'
        e.currentTarget.style.borderColor = '#3a3a3a'
        e.currentTarget.style.color = COLORS.textPrimary
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = COLORS.bgSubtle
        e.currentTarget.style.borderColor = COLORS.border
        e.currentTarget.style.color = COLORS.textSecondary
      }}
    >
      {children}
    </button>
  )
}

function SkeletonPanel() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {[0, 1].map((i) => (
        <div
          key={i}
          style={{
            backgroundColor: COLORS.bgPanel,
            border: `1px solid ${COLORS.border}`,
            borderRadius: '10px',
            padding: '20px',
            display: 'flex',
            gap: '14px',
            animation: `fadeIn 0.3s ease-out ${i * 80}ms both`,
          }}
        >
          <div style={{ width: '38px', height: '38px', borderRadius: '9px', backgroundColor: '#1e1e1e', animation: 'pulse 1.5s ease-in-out infinite', flexShrink: 0 }} />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ width: '35%', height: '13px', borderRadius: '4px', backgroundColor: '#222', animation: 'pulse 1.5s ease-in-out infinite' }} />
            <div style={{ width: '55%', height: '11px', borderRadius: '4px', backgroundColor: '#1e1e1e', animation: 'pulse 1.5s ease-in-out infinite' }} />
            <div style={{ width: '90%', height: '11px', borderRadius: '4px', backgroundColor: '#1e1e1e', animation: 'pulse 1.5s ease-in-out infinite', marginTop: '6px' }} />
          </div>
        </div>
      ))}
    </div>
  )
}