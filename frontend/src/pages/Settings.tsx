import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Settings as SettingsIcon,
  BookOpen,
  Gauge,
  Palette,
  BarChart3,
  ShieldCheck,
  FileText,
  Link2,
  Sparkles,
  Lock,
  Clock,
  ChevronDown,
  Circle,
  Type,
  ExternalLink,
} from 'lucide-react'
import { configApi, ConfigResponse, ConfigValidationResponse } from '../api/config.api'
import { authApi } from '../api/auth.api'

// ---------------------------------------------------------------------------
// Design tokens — identical palette to the original component.
// Centralised here purely so every element pulls from one source of truth;
// no new colors are introduced, only reuse / alpha variants of existing ones.
// ---------------------------------------------------------------------------
const colors = {
  bgPanel: '#161616',
  bgInput: '#1a1a1a',
  bgSubtle: '#1a1a1a',
  border: '#2a2a2a',
  borderStrong: '#3a3a3a',
  textPrimary: '#f5f5f5',
  textSecondary: '#e0e0e0',
  textMuted: '#a0a0a0',
  textDisabled: '#666666',
  accent: '#3b82f6',
  accentSoft: 'rgba(59, 130, 246, 0.12)',
  accentRing: 'rgba(59, 130, 246, 0.18)',
  success: '#10b981',
  successSoft: 'rgba(16, 185, 129, 0.1)',
  successBorder: 'rgba(16, 185, 129, 0.3)',
  error: '#ef4444',
  errorSoft: 'rgba(239, 68, 68, 0.1)',
  errorBorder: 'rgba(239, 68, 68, 0.3)',
  white: '#ffffff',
  shadow: 'rgba(0, 0, 0, 0.35)',
}

type FieldType = 'text' | 'number' | 'boolean' | 'select'

interface FieldDef {
  key: string
  label: string
  type: FieldType
  options?: string[]
  dependsOn?: string
  helper?: string
}

interface TabDef {
  id: string
  label: string
  description: string
  icon: React.ComponentType<{ style?: React.CSSProperties }>
  section: string
  fields: FieldDef[]
}

const TABS: TabDef[] = [
  {
    id: 'wikipedia',
    label: 'Wikipédia',
    description: 'Langue et projet Wikimedia ciblés par OVIX.',
    icon: BookOpen,
    section: 'wikipedia',
    fields: [
      { key: 'lang', label: 'Langue', type: 'text' },
      { key: 'family', label: 'Famille', type: 'select', options: ['wikipedia', 'wiktionary', 'wikibooks'] },
    ],
  },
  {
    id: 'rate_limiting',
    label: 'Rate limiting',
    description: 'Cadence des éditions et des requêtes envoyées à l\u2019API.',
    icon: Gauge,
    section: 'rate_limiting',
    fields: [
      { key: 'min_edit_delay', label: 'Délai minimum entre éditions (s)', type: 'number' },
      { key: 'max_edits_per_minute', label: 'Éditions max par minute', type: 'number' },
      { key: 'max_requests_per_second', label: 'Requêtes max par seconde', type: 'number' },
      { key: 'burst', label: 'Burst', type: 'number' },
    ],
  },
  {
    id: 'ui',
    label: 'Interface',
    description: 'Apparence et comportement par défaut de l\u2019interface.',
    icon: Palette,
    section: 'ui',
    fields: [
      { key: 'theme', label: 'Thème', type: 'select', options: ['light', 'dark', 'auto'] },
      { key: 'max_issues_display', label: 'Max issues affichées', type: 'number' },
      { key: 'auto_expand_high_severity', label: 'Auto-expand haute sévérité', type: 'boolean' },
      { key: 'show_diff_by_default', label: 'Afficher diff par défaut', type: 'boolean' },
      { key: 'compact_view', label: 'Vue compacte', type: 'boolean' },
    ],
  },
  {
    id: 'safety',
    label: 'Sécurité',
    description: 'Garde-fous appliqués avant toute édition en production.',
    icon: ShieldCheck,
    section: 'safety',
    fields: [
      { key: 'dry_run_default', label: 'Dry-run par défaut', type: 'boolean' },
      { key: 'require_confirmation', label: 'Confirmation requise', type: 'boolean' },
      { key: 'max_article_batch_size', label: 'Taille max batch articles', type: 'number' },
      { key: 'max_edits_per_session', label: 'Éditions max par session', type: 'number' },
      { key: 'max_change_bytes', label: 'Taille max changement (octets)', type: 'number' },
    ],
  },
  {
    id: 'logging',
    label: 'Logs',
    description: 'Niveau, destination et rotation des journaux.',
    icon: FileText,
    section: 'logging',
    fields: [
      { key: 'level', label: 'Niveau de log', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] },
      { key: 'file', label: 'Fichier de log', type: 'text' },
      { key: 'console', label: 'Logs console', type: 'boolean' },
      { key: 'max_size_mb', label: 'Taille max fichier (MB)', type: 'number' },
      { key: 'backup_count', label: 'Nombre de backups', type: 'number' },
    ],
  },
  {
    id: 'timeouts',
    label: 'Timeouts',
    description: 'Délais d\u2019attente maximum par service externe.',
    icon: Clock,
    section: 'timeouts',
    fields: [
      { key: 'wikipedia_api', label: 'Wikipedia API (s)', type: 'number' },
      { key: 'analyzer', label: 'Analyseur (s)', type: 'number' },
      { key: 'link_check', label: 'Vérification lien (s)', type: 'number' },
      { key: 'https_verification', label: 'Vérification HTTPS (s)', type: 'number' },
      { key: 'wayback_cdx', label: 'Wayback CDX (s)', type: 'number' },
      { key: 'archive_org', label: 'Archive.org (s)', type: 'number' },
    ],
  },
  {
    id: 'analysis',
    label: 'Analyse',
    description: 'Réglages des analyseurs et de leur seuil de sévérité.',
    icon: BarChart3,
    section: 'analysis',
    fields: [
      { key: 'enable_dead_link_analyzer', label: 'Analyseur de liens morts', type: 'boolean' },
      { key: 'min_severity', label: 'Sévérité minimum', type: 'select', options: ['all', 'low', 'medium', 'high', 'critical'] },
      { key: 'parallel', label: 'Analyse parallèle', type: 'boolean' },
      { key: 'analyzer_timeout', label: 'Timeout analyseur (s)', type: 'number' },
      { key: 'enable_case_normalization', label: 'Normalisation des majuscules', type: 'boolean' },
      {
        key: 'normalize_with_ai',
        label: 'Utiliser l\u2019IA pour la normalisation',
        type: 'boolean',
        dependsOn: 'enable_case_normalization',
      },
    ],
  },
  {
    id: 'references',
    label: 'Références',
    description: 'Contrôles appliqués aux références bibliographiques.',
    icon: Link2,
    section: 'references',
    fields: [
      { key: 'check_bare_refs', label: 'Vérifier références nues', type: 'boolean' },
      { key: 'check_duplicate_refs', label: 'Vérifier références dupliquées', type: 'boolean' },
      { key: 'check_uppercase_refs', label: 'Vérifier références majuscules', type: 'boolean' },
      { key: 'check_isbn_format', label: 'Vérifier format ISBN', type: 'boolean' },
      { key: 'check_template_type', label: 'Vérifier type de template', type: 'boolean' },
      { key: 'check_broken_links', label: 'Vérifier liens brisés', type: 'boolean' },
      { key: 'use_wayback_api', label: 'Utiliser API Wayback', type: 'boolean' },
      { key: 'link_check_timeout', label: 'Timeout vérification lien (s)', type: 'number' },
    ],
  },
  {
    id: 'reference_enricher',
    label: 'Enrichissement',
    description: 'Complétion automatique des paramètres de référence.',
    icon: Sparkles,
    section: 'reference_enricher_analyzer',
    fields: [
      { key: 'enabled', label: 'Activer l\u2019enrichisseur de références', type: 'boolean' },
      { key: 'timeout', label: 'Timeout vérification (s)', type: 'number' },
      { key: 'max_retries', label: 'Tentatives max', type: 'number' },
      { key: 'max_checks_per_article', label: 'Max vérifications par article', type: 'number' },
      { key: 'enable_site_fill', label: 'Remplir paramètre |site=', type: 'boolean' },
      { key: 'enable_consulte_le_fill', label: 'Remplir paramètre |consulté le=', type: 'boolean' },
    ],
  },
  {
    id: 'https_verification',
    label: 'HTTPS',
    description: 'Vérification et mise en cache de la disponibilité HTTPS.',
    icon: Lock,
    section: 'https_verification',
    fields: [
      { key: 'enabled', label: 'Vérification HTTPS activée', type: 'boolean' },
      { key: 'timeout', label: 'Timeout (secondes)', type: 'number' },
      { key: 'ttl_available', label: 'TTL disponible (jours)', type: 'number' },
      { key: 'ttl_unavailable', label: 'TTL indisponible (jours)', type: 'number' },
      { key: 'ttl_failed', label: 'TTL échoué (jours)', type: 'number' },
    ],
  },
  {
    id: 'typography_xml',
    label: 'Typographie XML',
    description: 'Correction typographique basée sur des règles XML (normalise_typo.xml).',
    icon: Type,
    section: 'typography_xml_analyzer',
    fields: [
      { key: 'enabled', label: 'Activer l\u2019analyseur XML', type: 'boolean' },
      { key: 'xml_rules_path', label: 'Chemin fichier XML règles', type: 'text', helper: 'Null pour le chemin par défaut' },
      { key: 'max_corrections_per_article', label: 'Max corrections par article', type: 'number' },
      { key: 'ignore_protected_areas', label: 'Ignorer zones protégées', type: 'boolean' },
      { key: 'case_sensitive', label: 'Sensible à la casse', type: 'boolean' },
    ],
  },
]

export default function Settings() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [successMessage, setSuccessMessage] = useState('')
  const [activeTab, setActiveTab] = useState('wikipedia')
  const [authStatus, setAuthStatus] = useState<any>(null)
  const initialConfigRef = useRef<string>('{}')

  useEffect(() => {
    loadConfig(true)
    loadAuthStatus()
  }, [])

  const loadAuthStatus = async () => {
    try {
      const status = await authApi.getStatus()
      setAuthStatus(status)
    } catch (error) {
      console.error('Failed to load auth status:', error)
    }
  }

  const loadConfig = async (isInitial = false) => {
    try {
      if (isInitial) {
        setLoading(true)
      }
      const response = await configApi.getConfig()
      if (response.success) {
        setConfig(response.config)
        initialConfigRef.current = JSON.stringify(response.config)
      }
    } catch (error) {
      console.error('Failed to load config:', error)
    } finally {
      if (isInitial) {
        setLoading(false)
      }
    }
  }

  const handleValueChange = (section: string, key: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }))
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setValidationErrors([])
      setSuccessMessage('')

      // Validate configuration
      const validation: ConfigValidationResponse = await configApi.validateConfig(config)

      if (!validation.valid) {
        setValidationErrors(validation.errors)
        return
      }

      // Save each section
      for (const [section, data] of Object.entries(config)) {
        await configApi.updateConfigSection({ section, data })
      }

      initialConfigRef.current = JSON.stringify(config)
      setSuccessMessage('Configuration sauvegardée avec succès')
      setTimeout(() => setSuccessMessage(''), 3000)
    } catch (error) {
      console.error('Failed to save config:', error)
      setValidationErrors(['Erreur lors de la sauvegarde'])
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('Êtes-vous sûr de vouloir réinitialiser la configuration aux valeurs par défaut ?')) {
      return
    }

    try {
      setLoading(true)
      await configApi.resetConfig()
      await loadConfig()
      setSuccessMessage('Configuration réinitialisée')
      setTimeout(() => setSuccessMessage(''), 3000)
    } catch (error) {
      console.error('Failed to reset config:', error)
      setValidationErrors(['Erreur lors de la réinitialisation'])
    } finally {
      setLoading(false)
    }
  }

  const isDirty = JSON.stringify(config) !== initialConfigRef.current
  const currentTab = TABS.find(t => t.id === activeTab) ?? TABS[0]

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <RefreshCw className="animate-spin" style={{ width: '32px', height: '32px', color: colors.textDisabled }} />
      </div>
    )
  }

  return (
    <div style={{ padding: '32px 24px', maxWidth: '1200px', margin: '0 auto' }}>
      <style>{`
        @keyframes ovix-fade-in {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes ovix-spin-in {
          from { opacity: 0; transform: scale(0.96); }
          to { opacity: 1; transform: scale(1); }
        }
        .ovix-panel { animation: ovix-fade-in 180ms ease-out; }
        .ovix-nav-item {
          transition: background-color 150ms ease, color 150ms ease;
        }
        .ovix-nav-item:hover:not(.is-active) {
          background-color: ${colors.bgSubtle};
          color: ${colors.textPrimary};
        }
        .ovix-btn {
          transition: background-color 150ms ease, border-color 150ms ease, opacity 150ms ease, transform 100ms ease;
        }
        .ovix-btn:active:not(:disabled) { transform: translateY(1px); }
        .ovix-btn-ghost:hover:not(:disabled) {
          background-color: ${colors.bgSubtle};
          border-color: ${colors.borderStrong};
        }
        .ovix-btn-primary:hover:not(:disabled) {
          background-color: #4a8ef8;
        }
        .ovix-field-row {
          transition: border-color 150ms ease;
        }
        .ovix-input {
          transition: border-color 150ms ease, box-shadow 150ms ease;
        }
        .ovix-input:focus {
          outline: none;
          border-color: ${colors.accent} !important;
          box-shadow: 0 0 0 3px ${colors.accentRing};
        }
        .ovix-toggle-track {
          transition: background-color 150ms ease;
        }
        .ovix-toggle-thumb {
          transition: transform 150ms ease;
        }
        @media (max-width: 760px) {
          .ovix-layout { grid-template-columns: 1fr !important; }
          .ovix-nav { flex-direction: row !important; overflow-x: auto; gap: 4px !important; }
          .ovix-nav-item { flex-shrink: 0; }
        }
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: '28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            backgroundColor: colors.bgPanel,
            border: `1px solid ${colors.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <SettingsIcon style={{ width: '20px', height: '20px', color: colors.textPrimary }} />
          </div>
          <div>
            <h1 style={{ fontSize: '15.5px', fontWeight: 600, color: colors.textPrimary, margin: 0, letterSpacing: '-0.01em' }}>
              Paramètres OVIX
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <Circle
                style={{
                  width: '5px',
                  height: '5px',
                  color: isDirty ? colors.accent : colors.textDisabled,
                  fill: isDirty ? colors.accent : colors.textDisabled,
                }}
              />
              <span style={{ fontSize: '10.5px', color: colors.textMuted }}>
                {isDirty ? 'Modifications non enregistrées' : 'À jour'}
              </span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={handleReset}
            className="ovix-btn ovix-btn-ghost"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '9px 16px',
              backgroundColor: colors.bgPanel,
              color: colors.textPrimary,
              border: `1px solid ${colors.border}`,
              borderRadius: '7px',
              cursor: 'pointer',
              fontSize: '11.5px',
              fontWeight: 500,
            }}
          >
            <RefreshCw style={{ width: '14px', height: '14px' }} />
            Réinitialiser
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="ovix-btn ovix-btn-primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '9px 18px',
              backgroundColor: colors.accent,
              color: colors.white,
              border: 'none',
              borderRadius: '7px',
              cursor: saving ? 'not-allowed' : 'pointer',
              fontSize: '11.5px',
              fontWeight: 500,
              opacity: saving ? 0.6 : 1,
              boxShadow: `0 1px 2px ${colors.shadow}`,
            }}
          >
            {saving ? (
              <RefreshCw className="animate-spin" style={{ width: '14px', height: '14px' }} />
            ) : (
              <Save style={{ width: '14px', height: '14px' }} />
            )}
            {saving ? 'Sauvegarde...' : 'Sauvegarder'}
          </button>
        </div>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div
          className="ovix-panel"
          style={{
            marginBottom: '20px',
            padding: '12px 16px',
            backgroundColor: colors.successSoft,
            border: `1px solid ${colors.successBorder}`,
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            color: colors.success,
            fontSize: '11.5px',
          }}
        >
          <CheckCircle style={{ width: '17px', height: '17px', flexShrink: 0 }} />
          {successMessage}
        </div>
      )}

      {validationErrors.length > 0 && (
        <div
          className="ovix-panel"
          style={{
            marginBottom: '20px',
            padding: '14px 16px',
            backgroundColor: colors.errorSoft,
            border: `1px solid ${colors.errorBorder}`,
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
            color: colors.error,
            fontSize: '11.5px',
          }}
        >
          <AlertTriangle style={{ width: '17px', height: '17px', flexShrink: 0, marginTop: '1px' }} />
          <div>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>Erreurs de validation</div>
            <ul style={{ margin: 0, paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
              {validationErrors.map((error, i) => (
                <li key={i}>{error}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Layout: sidebar nav + content panel */}
      <div className="ovix-layout" style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '20px', alignItems: 'start' }}>
        <nav
          className="ovix-nav"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
            backgroundColor: colors.bgPanel,
            border: `1px solid ${colors.border}`,
            borderRadius: '10px',
            padding: '6px',
            position: 'sticky',
            top: '16px',
          }}
        >
          {TABS.map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            
            // Check if this tab is an analyzer and if it's enabled
            const isAnalyzerTab = ['analysis', 'references', 'reference_enricher', 'https_verification', 'typography_xml'].includes(tab.id)
            const sectionConfig = config[tab.section] || {}
            const isAnalyzerEnabled = isAnalyzerTab && (
              tab.id === 'analysis' ? sectionConfig.enable_dead_link_analyzer !== false :
              tab.id === 'references' ? (sectionConfig.check_bare_refs || sectionConfig.check_duplicate_refs || sectionConfig.check_uppercase_refs || sectionConfig.check_isbn_format || sectionConfig.check_template_type || sectionConfig.check_broken_links) :
              sectionConfig.enabled !== false
            )
            
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`ovix-nav-item${isActive ? ' is-active' : ''}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '9px 10px',
                  backgroundColor: isActive ? colors.bgSubtle : 'transparent',
                  color: isActive ? colors.textPrimary : colors.textMuted,
                  border: 'none',
                  borderRadius: '7px',
                  cursor: 'pointer',
                  fontSize: '11.5px',
                  fontWeight: isActive ? 500 : 400,
                  textAlign: 'left',
                  position: 'relative',
                }}
              >
                {isActive && (
                  <span
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: '20%',
                      bottom: '20%',
                      width: '2px',
                      borderRadius: '2px',
                      backgroundColor: colors.accent,
                    }}
                  />
                )}
                <Icon style={{ width: '14px', height: '14px', flexShrink: 0, color: isActive ? colors.accent : colors.textDisabled }} />
                <span style={{ whiteSpace: 'nowrap' }}>{tab.label}</span>
                {isAnalyzerEnabled && (
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: colors.success,
                      marginLeft: 'auto',
                      flexShrink: 0,
                    }}
                  />
                )}
              </button>
            )
          })}
        </nav>

        <div
          key={currentTab.id}
          className="ovix-panel"
          style={{
            backgroundColor: colors.bgPanel,
            borderRadius: '10px',
            border: `1px solid ${colors.border}`,
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '18px 24px', borderBottom: `1px solid ${colors.border}` }}>
            <h2 style={{ fontSize: '12.5px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
              {currentTab.label}
            </h2>
            <p style={{ fontSize: '10.5px', color: colors.textMuted, margin: '4px 0 0' }}>
              {currentTab.description}
            </p>
          </div>
          <div style={{ padding: '8px 24px 20px' }}>
            {currentTab.id === 'wikipedia' && authStatus && (
              <div style={{
                marginBottom: '16px',
                padding: '10px',
                backgroundColor: authStatus.authenticated ? colors.successSoft : colors.errorSoft,
                border: `1px solid ${authStatus.authenticated ? colors.successBorder : colors.errorBorder}`,
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '10px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {authStatus.authenticated ? (
                    <CheckCircle style={{ width: '14px', height: '14px', color: colors.success }} />
                  ) : (
                    <AlertTriangle style={{ width: '14px', height: '14px', color: colors.error }} />
                  )}
                  <span style={{ fontSize: '10px', color: authStatus.authenticated ? colors.success : colors.error }}>
                    {authStatus.authenticated 
                      ? `Connecté en tant que ${authStatus.username || 'utilisateur'}` 
                      : 'Non connecté'}
                  </span>
                </div>
                <button
                  onClick={() => navigate('/settings/wikipedia')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 8px',
                    backgroundColor: 'transparent',
                    border: `1px solid ${authStatus.authenticated ? colors.success : colors.error}`,
                    borderRadius: '4px',
                    color: authStatus.authenticated ? colors.success : colors.error,
                    fontSize: '9px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    transition: 'background-color 150ms ease',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.backgroundColor = authStatus.authenticated ? colors.successSoft : colors.errorSoft}
                  onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <ExternalLink style={{ width: '10px', height: '10px' }} />
                  Gérer
                </button>
              </div>
            )}
            <ConfigSection
              section={currentTab.section}
              config={config}
              onChange={handleValueChange}
              fields={currentTab.fields}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

interface ConfigSectionProps {
  section: string
  config: Record<string, any>
  onChange: (section: string, key: string, value: any) => void
  fields: FieldDef[]
}

function ConfigSection({ section, config, onChange, fields }: ConfigSectionProps) {
  const sectionConfig = config[section] || {}

  return (
    <div>
      {fields.map((field, i) => {
        const isDisabled = field.dependsOn ? !sectionConfig[field.dependsOn] : false
        const dependencyLabel = field.dependsOn ? fields.find(f => f.key === field.dependsOn)?.label : undefined
        const isLast = i === fields.length - 1

        return (
          <div
            key={field.key}
            className="ovix-field-row"
            style={{
              display: 'flex',
              alignItems: field.type === 'boolean' ? 'center' : 'flex-start',
              justifyContent: 'space-between',
              gap: '24px',
              padding: '16px 0',
              borderBottom: isLast ? 'none' : `1px solid ${colors.border}`,
            }}
          >
            <div style={{ maxWidth: '360px' }}>
              <label
                htmlFor={`${section}-${field.key}`}
                style={{
                  fontSize: '11px',
                  fontWeight: 500,
                  color: isDisabled ? colors.textDisabled : colors.textSecondary,
                  display: 'block',
                }}
              >
                {field.label}
              </label>
              {isDisabled && dependencyLabel && (
                <p style={{ fontSize: '9.5px', color: colors.textDisabled, margin: '3px 0 0' }}>
                  Nécessite « {dependencyLabel} »
                </p>
              )}
            </div>

            <div style={{ flexShrink: 0, width: field.type === 'boolean' ? 'auto' : '220px' }}>
              {field.type === 'boolean' ? (
                <ToggleSwitch
                  id={`${section}-${field.key}`}
                  checked={!!sectionConfig[field.key]}
                  disabled={isDisabled}
                  onChange={(checked) => onChange(section, field.key, checked)}
                />
              ) : field.type === 'select' ? (
                <div style={{ position: 'relative' }}>
                  <select
                    id={`${section}-${field.key}`}
                    value={sectionConfig[field.key] || ''}
                    disabled={isDisabled}
                    onChange={(e) => onChange(section, field.key, e.target.value)}
                    className="ovix-input"
                    style={{
                      width: '100%',
                      padding: '8px 32px 8px 12px',
                      backgroundColor: colors.bgInput,
                      color: colors.textPrimary,
                      border: `1px solid ${colors.border}`,
                      borderRadius: '7px',
                      fontSize: '11px',
                      cursor: isDisabled ? 'not-allowed' : 'pointer',
                      opacity: isDisabled ? 0.5 : 1,
                      appearance: 'none',
                      WebkitAppearance: 'none',
                    }}
                  >
                    {field.options?.map(option => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                  <ChevronDown
                    style={{
                      position: 'absolute',
                      right: '10px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: '14px',
                      height: '14px',
                      color: colors.textDisabled,
                      pointerEvents: 'none',
                    }}
                  />
                </div>
              ) : (
                <input
                  id={`${section}-${field.key}`}
                  type={field.type}
                  value={sectionConfig[field.key] ?? ''}
                  disabled={isDisabled}
                  onChange={(e) => onChange(section, field.key, field.type === 'number' ? Number(e.target.value) : e.target.value)}
                  className="ovix-input"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    backgroundColor: colors.bgInput,
                    color: colors.textPrimary,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '7px',
                    fontSize: '11px',
                    opacity: isDisabled ? 0.5 : 1,
                  }}
                />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

interface ToggleSwitchProps {
  id: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}

function ToggleSwitch({ id, checked, disabled, onChange }: ToggleSwitchProps) {
  return (
    <label
      htmlFor={id}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        style={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', opacity: 0 }}
      />
      <span
        className="ovix-toggle-track"
        style={{
          width: '38px',
          height: '22px',
          borderRadius: '999px',
          backgroundColor: checked ? colors.accent : colors.borderStrong,
          position: 'relative',
          display: 'inline-block',
          flexShrink: 0,
        }}
      >
        <span
          className="ovix-toggle-thumb"
          style={{
            position: 'absolute',
            top: '2px',
            left: '2px',
            width: '18px',
            height: '18px',
            borderRadius: '50%',
            backgroundColor: colors.white,
            transform: checked ? 'translateX(16px)' : 'translateX(0)',
            boxShadow: `0 1px 2px ${colors.shadow}`,
          }}
        />
      </span>
    </label>
  )
}