import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, RefreshCw, AlertTriangle, CheckCircle, Settings as SettingsIcon } from 'lucide-react'
import { configApi, ConfigResponse, ConfigValidationResponse } from '../api/config.api'

export default function Settings() {
  const navigate = useNavigate()
  const [config, setConfig] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [successMessage, setSuccessMessage] = useState('')
  const [activeTab, setActiveTab] = useState('wikipedia')

  useEffect(() => {
    loadConfig(true)
  }, [])

  const loadConfig = async (isInitial = false) => {
    try {
      if (isInitial) {
        setLoading(true)
      }
      const response = await configApi.getConfig()
      if (response.success) {
        setConfig(response.config)
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
        [key]: value
      }
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

  const tabs = [
    { id: 'wikipedia', label: 'Wikipédia' },
    { id: 'rate_limiting', label: 'Rate Limiting' },
    { id: 'ui', label: 'Interface' },
    { id: 'analysis', label: 'Analyse' },
    { id: 'safety', label: 'Sécurité' },
    { id: 'logging', label: 'Logs' },
    { id: 'references', label: 'Références' },
    { id: 'https_verification', label: 'HTTPS' },
    { id: 'timeouts', label: 'Timeouts' },
  ]

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <RefreshCw className="animate-spin" style={{ width: '40px', height: '40px', color: '#666666' }} />
      </div>
    )
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <SettingsIcon style={{ width: '28px', height: '28px', color: '#f5f5f5' }} />
          <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>
            Paramètres OVIX
          </h1>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button
            onClick={handleReset}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              backgroundColor: '#2a2a2a',
              color: '#f5f5f5',
              border: '1px solid #3a3a3a',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            Réinitialiser
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 16px',
              backgroundColor: '#3b82f6',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              cursor: saving ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: 500,
              opacity: saving ? 0.6 : 1,
            }}
          >
            <Save style={{ width: '16px', height: '16px' }} />
            {saving ? 'Sauvegarde...' : 'Sauvegarder'}
          </button>
        </div>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div style={{
          marginBottom: '24px',
          padding: '12px 16px',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          color: '#10b981',
          fontSize: '14px',
        }}>
          <CheckCircle style={{ width: '20px', height: '20px', flexShrink: 0 }} />
          {successMessage}
        </div>
      )}

      {validationErrors.length > 0 && (
        <div style={{
          marginBottom: '24px',
          padding: '12px 16px',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
          color: '#ef4444',
          fontSize: '14px',
        }}>
          <AlertTriangle style={{ width: '20px', height: '20px', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>Erreurs de validation :</div>
            <ul style={{ margin: 0, paddingLeft: '20px' }}>
              {validationErrors.map((error, i) => (
                <li key={i}>{error}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{
        marginBottom: '24px',
        display: 'flex',
        gap: '4px',
        borderBottom: '1px solid #2a2a2a',
        paddingBottom: '0',
      }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '12px 20px',
              backgroundColor: activeTab === tab.id ? '#1a1a1a' : 'transparent',
              color: activeTab === tab.id ? '#f5f5f5' : '#a0a0a0',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid #3b82f6' : '2px solid transparent',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: activeTab === tab.id ? 500 : 400,
              marginBottom: '-1px',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{
        backgroundColor: '#161616',
        borderRadius: '8px',
        padding: '24px',
        border: '1px solid #2a2a2a',
      }}>
        {activeTab === 'wikipedia' && (
          <ConfigSection
            section="wikipedia"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'lang', label: 'Langue', type: 'text' },
              { key: 'family', label: 'Famille', type: 'select', options: ['wikipedia', 'wiktionary', 'wikibooks'] },
            ]}
          />
        )}

        {activeTab === 'rate_limiting' && (
          <ConfigSection
            section="rate_limiting"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'min_edit_delay', label: 'Délai minimum entre éditions (s)', type: 'number' },
              { key: 'max_edits_per_minute', label: 'Éditions max par minute', type: 'number' },
              { key: 'max_requests_per_second', label: 'Requêtes max par seconde', type: 'number' },
              { key: 'burst', label: 'Burst', type: 'number' },
            ]}
          />
        )}

        {activeTab === 'ui' && (
          <ConfigSection
            section="ui"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'theme', label: 'Thème', type: 'select', options: ['light', 'dark', 'auto'] },
              { key: 'max_issues_display', label: 'Max issues affichées', type: 'number' },
              { key: 'auto_expand_high_severity', label: 'Auto-expand haute sévérité', type: 'boolean' },
              { key: 'show_diff_by_default', label: 'Afficher diff par défaut', type: 'boolean' },
              { key: 'compact_view', label: 'Vue compacte', type: 'boolean' },
            ]}
          />
        )}

        {activeTab === 'analysis' && (
          <ConfigSection
            section="analysis"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'min_severity', label: 'Sévérité minimum', type: 'select', options: ['all', 'low', 'medium', 'high', 'critical'] },
              { key: 'parallel', label: 'Analyse parallèle', type: 'boolean' },
              { key: 'analyzer_timeout', label: 'Timeout analyseur (s)', type: 'number' },
            ]}
          />
        )}

        {activeTab === 'safety' && (
          <ConfigSection
            section="safety"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'dry_run_default', label: 'Dry-run par défaut', type: 'boolean' },
              { key: 'require_confirmation', label: 'Confirmation requise', type: 'boolean' },
              { key: 'max_article_batch_size', label: 'Taille max batch articles', type: 'number' },
              { key: 'max_edits_per_session', label: 'Éditions max par session', type: 'number' },
              { key: 'max_change_bytes', label: 'Taille max changement (octets)', type: 'number' },
            ]}
          />
        )}

        {activeTab === 'logging' && (
          <ConfigSection
            section="logging"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'level', label: 'Niveau de log', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] },
              { key: 'file', label: 'Fichier de log', type: 'text' },
              { key: 'console', label: 'Logs console', type: 'boolean' },
              { key: 'max_size_mb', label: 'Taille max fichier (MB)', type: 'number' },
              { key: 'backup_count', label: 'Nombre de backups', type: 'number' },
            ]}
          />
        )}

        {activeTab === 'references' && (
          <ConfigSection
            section="references"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'check_bare_refs', label: 'Vérifier références nues', type: 'boolean' },
              { key: 'check_duplicate_refs', label: 'Vérifier références dupliquées', type: 'boolean' },
              { key: 'check_uppercase_refs', label: 'Vérifier références majuscules', type: 'boolean' },
              { key: 'check_isbn_format', label: 'Vérifier format ISBN', type: 'boolean' },
              { key: 'check_template_type', label: 'Vérifier type de template', type: 'boolean' },
              { key: 'check_broken_links', label: 'Vérifier liens brisés', type: 'boolean' },
              { key: 'use_wayback_api', label: 'Utiliser API Wayback', type: 'boolean' },
              { key: 'link_check_timeout', label: 'Timeout vérification lien (s)', type: 'number' },
            ]}
          />
        )}

        {activeTab === 'https_verification' && (
          <ConfigSection
            section="https_verification"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'enabled', label: 'Vérification HTTPS activée', type: 'boolean' },
              { key: 'timeout', label: 'Timeout (secondes)', type: 'number' },
              { key: 'ttl_available', label: 'TTL disponible (jours)', type: 'number' },
              { key: 'ttl_unavailable', label: 'TTL indisponible (jours)', type: 'number' },
              { key: 'ttl_failed', label: 'TTL échoué (jours)', type: 'number' },
            ]}
          />
        )}

        {activeTab === 'timeouts' && (
          <ConfigSection
            section="timeouts"
            config={config}
            onChange={handleValueChange}
            fields={[
              { key: 'wikipedia_api', label: 'Wikipedia API (s)', type: 'number' },
              { key: 'analyzer', label: 'Analyseur (s)', type: 'number' },
              { key: 'link_check', label: 'Vérification lien (s)', type: 'number' },
              { key: 'https_verification', label: 'Vérification HTTPS (s)', type: 'number' },
              { key: 'wayback_cdx', label: 'Wayback CDX (s)', type: 'number' },
              { key: 'archive_org', label: 'Archive.org (s)', type: 'number' },
            ]}
          />
        )}
      </div>
    </div>
  )
}

interface ConfigSectionProps {
  section: string
  config: Record<string, any>
  onChange: (section: string, key: string, value: any) => void
  fields: Array<{
    key: string
    label: string
    type: 'text' | 'number' | 'boolean' | 'select'
    options?: string[]
  }>
}

function ConfigSection({ section, config, onChange, fields }: ConfigSectionProps) {
  const sectionConfig = config[section] || {}

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {fields.map(field => (
        <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '14px', fontWeight: 500, color: '#e0e0e0' }}>
            {field.label}
          </label>
          {field.type === 'boolean' ? (
            <input
              type="checkbox"
              checked={sectionConfig[field.key] || false}
              onChange={(e) => onChange(section, field.key, e.target.checked)}
              style={{ width: '20px', height: '20px', cursor: 'pointer' }}
            />
          ) : field.type === 'select' ? (
            <select
              value={sectionConfig[field.key] || ''}
              onChange={(e) => onChange(section, field.key, e.target.value)}
              style={{
                padding: '10px 12px',
                backgroundColor: '#1a1a1a',
                color: '#f5f5f5',
                border: '1px solid #2a2a2a',
                borderRadius: '6px',
                fontSize: '14px',
                cursor: 'pointer',
              }}
            >
              {field.options?.map(option => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          ) : (
            <input
              type={field.type}
              value={sectionConfig[field.key] || ''}
              onChange={(e) => onChange(section, field.key, field.type === 'number' ? Number(e.target.value) : e.target.value)}
              style={{
                padding: '10px 12px',
                backgroundColor: '#1a1a1a',
                color: '#f5f5f5',
                border: '1px solid #2a2a2a',
                borderRadius: '6px',
                fontSize: '14px',
              }}
            />
          )}
        </div>
      ))}
    </div>
  )
}
