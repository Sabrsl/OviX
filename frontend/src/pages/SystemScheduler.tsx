import { useState, useEffect, useRef } from 'react'
import { Clock, Play, Pause, Square } from 'lucide-react'
import { systemApi } from '../api/system.api'

export default function SystemScheduler() {
  const [schedulerStatus, setSchedulerStatus] = useState<any>(null)
  const [schedulerConfig, setSchedulerConfig] = useState<any>(null)
  const [automationStatus, setAutomationStatus] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [configLoading, setConfigLoading] = useState(false)
  const [editingConfig, setEditingConfig] = useState(false)
  const [manualRunLoading, setManualRunLoading] = useState(false)
  const [manualRunMessage, setManualRunMessage] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false) // Auto-poll disabled by default to prevent UI blocking
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [includeAnalyzed, setIncludeAnalyzed] = useState(false)
  const [liaMode, setLiaMode] = useState(false)
  const [configForm, setConfigForm] = useState({
    daily_limit: 100,
    working_hours_start: 0,
    working_hours_end: 23,
    dry_run: true,
    category: '',
    articles_to_process: 100
  })

  const fetchStatus = async (isInitial = false) => {
    setError(null)
    try {
      const status = await systemApi.getSchedulerStatus()
      setSchedulerStatus(status)
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la récupération du statut')
    }
  }

  const fetchAutomationStatus = async () => {
    try {
      const status = await systemApi.getAutomationStatus()
      setAutomationStatus(status)
      return status
    } catch (err: any) {
      console.error('Failed to fetch automation status:', err)
      return null
    }
  }

  const fetchConfig = async () => {
    setConfigLoading(true)
    try {
      const response = await fetch('/api/system/scheduler/config')
      const data = await response.json()
      if (data.success) {
        setSchedulerConfig(data.config)
        setConfigForm({
          daily_limit: data.config.daily_limit || 30,
          working_hours_start: 0,
          working_hours_end: 23,
          dry_run: data.config.dry_run !== undefined ? data.config.dry_run : true,
          category: data.config.category || '',
          articles_to_process: data.config.articles_to_process || 10
        })
      }
    } catch (err) {
      console.error('Failed to fetch scheduler config:', err)
    } finally {
      setConfigLoading(false)
    }
  }

  const updateConfig = async () => {
    setConfigLoading(true)
    try {
      const response = await fetch('/api/system/scheduler/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configForm)
      })
      const data = await response.json()
      if (data.success) {
        await fetchConfig()
        setEditingConfig(false)
      } else {
        setError(data.message || 'Erreur lors de la mise à jour de la configuration')
      }
    } catch (err) {
      setError('Erreur lors de la mise à jour de la configuration')
    } finally {
      setConfigLoading(false)
    }
  }

  const startScheduler = async () => {
    setActionLoading(true)
    try {
      await systemApi.startScheduler()
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors du démarrage')
    } finally {
      setActionLoading(false)
    }
  }

  const pauseScheduler = async () => {
    setActionLoading(true)
    try {
      await systemApi.pauseScheduler()
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la pause')
    } finally {
      setActionLoading(false)
    }
  }

  const resumeScheduler = async () => {
    setActionLoading(true)
    try {
      await systemApi.resumeScheduler()
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la reprise')
    } finally {
      setActionLoading(false)
    }
  }

  const stopScheduler = async () => {
    if (!confirm('Êtes-vous sûr de vouloir arrêter le planificateur ?')) {
      return
    }

    setActionLoading(true)
    try {
      await systemApi.stopScheduler()
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de l\'arrêt')
    } finally {
      setActionLoading(false)
    }
  }

  const runManualScheduler = async () => {
    const includeText = includeAnalyzed ? 'OUI' : 'NON'
    const liaText = liaMode ? 'OUI (IA)' : 'NON (Regex)'
    
    if (!confirm(`Lancer l'automatisation complète ?\n\nCatégorie: ${configForm.category || 'Non configurée'}\nArticles à traiter: ${configForm.articles_to_process}\nInclure articles déjà analysés: ${includeText}\nMode IA: ${liaText}\n\nCela va:\n1. Récupérer les articles depuis Wikipédia\n2. Analyser tous les articles\n3. Corriger les liens morts\n4. Démarrer la publication progressive`)) {
      return
    }

    setManualRunLoading(true)
    setManualRunMessage('Lancement de l\'automatisation en cours...')
    
    try {
      const result = await systemApi.runManualScheduler({
        include_analyzed: includeAnalyzed,
        lia_mode: liaMode
      })
      if (result.success) {
        setManualRunMessage(result.message || 'Automatisation lancée avec succès')
        // Start polling for status updates
        setIsPolling(true)
        // Initial status refresh
        fetchStatus()
        fetchAutomationStatus()
      } else {
        setError(result.message || 'Erreur lors du lancement de l\'automatisation')
        setManualRunMessage(null)
      }
    } catch (err: any) {
      setError(err.message || 'Erreur lors du lancement de l\'automatisation')
      setManualRunMessage(null)
    } finally {
      setManualRunLoading(false)
    }
  }

  const pauseAutomation = async () => {
    setActionLoading(true)
    try {
      await systemApi.pauseAutomation()
      await fetchAutomationStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la pause')
    } finally {
      setActionLoading(false)
    }
  }

  const resumeAutomation = async () => {
    setActionLoading(true)
    try {
      await systemApi.resumeAutomation()
      await fetchAutomationStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de la reprise')
    } finally {
      setActionLoading(false)
    }
  }

  const stopAutomation = async () => {
    if (!confirm('Êtes-vous sûr de vouloir arrêter l\'automatisation ?')) {
      return
    }

    setActionLoading(true)
    try {
      await systemApi.stopAutomation()
      setIsPolling(false)
      // Force immediate status refresh to clear stale running state
      await fetchAutomationStatus()
      await fetchStatus()
    } catch (err: any) {
      setError(err.message || err.userMessage || 'Erreur lors de l\'arrêt')
    } finally {
      setActionLoading(false)
    }
  }

  // P1 CRITICAL FIX: Auto-polling for real-time scheduler and automation status updates
  useEffect(() => {
    if (isPolling) {
      pollingIntervalRef.current = setInterval(() => {
        fetchStatus()
        fetchAutomationStatus()
      }, 5000) // Poll every 5 seconds (same as Kill Switch)
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

  // Stop polling when automation is complete (no active task)
  useEffect(() => {
    if (isPolling && automationStatus) {
      const isCompleted = automationStatus.status === 'completed' || 
                        automationStatus.status === 'failed' || 
                        automationStatus.status === 'interrupted' ||
                        automationStatus.status === 'not_initialized'
      
      if (isCompleted) {
        setIsPolling(false)
        setManualRunMessage('Automatisation terminée')
        // Clear the completion message after 5 seconds
        const messageTimeout = setTimeout(() => setManualRunMessage(null), 5000)
        return () => clearTimeout(messageTimeout)
      }
    }
  }, [automationStatus, isPolling])

  useEffect(() => {
    fetchStatus()
    fetchConfig()
    fetchAutomationStatus()
  }, [])

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
        <div>
          <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>Planificateur</h2>
          <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Gérer le planificateur de publications</p>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px', backgroundColor: '#161616', borderRadius: '8px', border: '1px solid #2a2a2a' }}>
          <div style={{ textAlign: 'center', color: '#ef4444' }}>{error}</div>
        </div>
      </div>
    )
  }

  const isActive = schedulerStatus?.is_active || false
  const isPaused = schedulerStatus?.is_paused || false
  const isAutomationRunning = automationStatus?.status === 'running'

  return (
    <>
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.2); }
        }
      `}</style>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', animation: 'fadeIn 0.2s ease-in-out' }}>
      <div>
        <h2 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>Planificateur</h2>
        <p style={{ color: '#a0a0a0', marginTop: '4px' }}>Gérer le planificateur de publications</p>
      </div>

      {/* Automation Status Card */}
      {isAutomationRunning && automationStatus && (
        <div style={{ backgroundColor: '#161616', border: '1px solid #8b5cf6', borderRadius: '8px', padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            <div style={{ padding: '12px', backgroundColor: '#161616', borderRadius: '8px' }}>
              <Clock style={{ width: '24px', height: '24px', color: '#8b5cf6' }} />
            </div>
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#f5f5f5', marginBottom: '4px' }}>
                Statut de l'Automatisation
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ 
                  width: '8px', 
                  height: '8px', 
                  backgroundColor: '#8b5cf6', 
                  borderRadius: '50%',
                  animation: 'pulse 1.5s ease-in-out infinite'
                }} />
                <span style={{ fontSize: '14px', color: '#a0a0a0' }}>
                  {automationStatus.current_step || 'En cours...'}
                </span>
              </div>
            </div>
          </div>

          {automationStatus.session_id && (
            <div style={{ fontSize: '14px', color: '#666666', marginBottom: '8px' }}>
              <strong>Session:</strong> {automationStatus.session_id}
            </div>
          )}

          {automationStatus.category_name && (
            <div style={{ fontSize: '14px', color: '#666666', marginBottom: '8px' }}>
              <strong>Catégorie:</strong> {automationStatus.category_name}
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginTop: '16px' }}>
            <div>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>Articles traités</div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>
                {automationStatus.articles_processed || 0}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>Articles publiés</div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#10b981' }}>
                {automationStatus.articles_published || 0}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#a0a0a0', marginBottom: '4px' }}>Erreurs</div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#ef4444' }}>
                {automationStatus.articles_error || 0}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Scheduler Status Card */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
          <div style={{ padding: '12px', backgroundColor: '#161616', borderRadius: '8px' }}>
            <Clock style={{ width: '24px', height: '24px', color: isActive ? '#10b981' : '#666666' }} />
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ fontSize: '18px', fontWeight: 500, color: '#f5f5f5', marginBottom: '4px' }}>
              Statut du Planificateur
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ 
                width: '8px', 
                height: '8px', 
                backgroundColor: isPaused ? '#f59e0b' : (isActive ? '#10b981' : '#666666'), 
                borderRadius: '50%'
              }} />
              <span style={{ fontSize: '14px', color: '#a0a0a0' }}>
                {isPaused ? 'En pause' : (isActive ? 'Actif' : 'Inactif')}
              </span>
            </div>
          </div>
        </div>

        {schedulerStatus?.current_task && (
          <div style={{ fontSize: '14px', color: '#666666', marginBottom: '8px' }}>
            <strong>Tâche actuelle:</strong> {schedulerStatus.current_task}
          </div>
        )}

        {schedulerStatus?.queue_size !== undefined && (
          <div style={{ fontSize: '14px', color: '#666666', marginBottom: '8px' }}>
            <strong>File d'attente:</strong> {schedulerStatus.queue_size} publication(s)
          </div>
        )}

        {schedulerStatus?.next_execution && (
          <div style={{ fontSize: '14px', color: '#666666', marginBottom: '8px' }}>
            <strong>Prochaine exécution:</strong> {new Date(schedulerStatus.next_execution).toLocaleString('fr-FR')}
          </div>
        )}

        {schedulerStatus?.last_execution && (
          <div style={{ fontSize: '14px', color: '#666666', marginBottom: '8px' }}>
            <strong>Dernière exécution:</strong> {new Date(schedulerStatus.last_execution).toLocaleString('fr-FR')}
          </div>
        )}

        {schedulerStatus?.daily_published_count !== undefined && (
          <div style={{ fontSize: '14px', color: '#666666', marginBottom: '16px' }}>
            <strong>Traité aujourd'hui:</strong> {schedulerStatus.daily_published_count} / {schedulerStatus.daily_limit || '∞'}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn btn-secondary"
            onClick={() => fetchStatus()}
            disabled={actionLoading}
          >
            {actionLoading ? 'Chargement...' : 'Actualiser'}
          </button>
          <button
            onClick={() => setIsPolling(!isPolling)}
            style={{
              padding: '8px 16px',
              backgroundColor: isPolling ? '#10b981' : '#6b7280',
              border: 'none',
              borderRadius: '4px',
              color: '#ffffff',
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            {isPolling ? 'Suivi actif' : 'Suivi inactif'}
          </button>
        </div>
      </div>

      {/* Configuration */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Configuration
          </h3>
          {!editingConfig && (
            <button
              onClick={() => setEditingConfig(true)}
              style={{
                padding: '6px 12px',
                backgroundColor: '#3b82f6',
                border: 'none',
                borderRadius: '4px',
                color: '#ffffff',
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              Modifier
            </button>
          )}
        </div>

        {editingConfig ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Limite quotidienne
              </label>
              <input
                type="number"
                value={configForm.daily_limit}
                onChange={(e) => setConfigForm({ ...configForm, daily_limit: parseInt(e.target.value) })}
                style={{
                  width: '100%',
                  padding: '8px',
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '4px',
                  color: '#f5f5f5',
                  fontSize: '14px'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Mode Dry-run
              </label>
              <select
                value={configForm.dry_run ? 'true' : 'false'}
                onChange={(e) => setConfigForm({ ...configForm, dry_run: e.target.value === 'true' })}
                style={{
                  width: '100%',
                  padding: '8px',
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '4px',
                  color: '#f5f5f5',
                  fontSize: '14px'
                }}
              >
                <option value="true">Activé (test)</option>
                <option value="false">Désactivé (production)</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Catégorie Wikipédia
              </label>
              <input
                type="text"
                value={configForm.category}
                onChange={(e) => setConfigForm({ ...configForm, category: e.target.value })}
                placeholder="Ex: Article de qualité"
                style={{
                  width: '100%',
                  padding: '8px',
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '4px',
                  color: '#f5f5f5',
                  fontSize: '14px'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Articles à traiter
              </label>
              <input
                type="number"
                value={configForm.articles_to_process}
                onChange={(e) => setConfigForm({ ...configForm, articles_to_process: parseInt(e.target.value) })}
                style={{
                  width: '100%',
                  padding: '8px',
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '4px',
                  color: '#f5f5f5',
                  fontSize: '14px'
                }}
              />
            </div>
            <div style={{ gridColumn: 'span  2', display: 'flex', gap: '8px', marginTop: '8px' }}>
              <button
                onClick={updateConfig}
                disabled={configLoading}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#10b981',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#ffffff',
                  fontSize: '14px',
                  cursor: configLoading ? 'not-allowed' : 'pointer',
                  opacity: configLoading ? 0.5 : 1
                }}
              >
                {configLoading ? 'Sauvegarde...' : 'Sauvegarder'}
              </button>
              <button
                onClick={() => {
                  setEditingConfig(false)
                  if (schedulerConfig) {
                    setConfigForm({
                      daily_limit: schedulerConfig.daily_limit || 30,
                      working_hours_start: 0,
                      working_hours_end: 23,
                      dry_run: schedulerConfig.dry_run !== undefined ? schedulerConfig.dry_run : true,
                      category: schedulerConfig.category || '',
                      articles_to_process: schedulerConfig.articles_to_process || 10
                    })
                  }
                }}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#6b7280',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#ffffff',
                  fontSize: '14px',
                  cursor: 'pointer'
                }}
              >
                Annuler
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Limite quotidienne
              </label>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>
                {schedulerConfig?.daily_limit || 'Non configuré'}
              </div>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Mode Dry-run
              </label>
              <div style={{ fontSize: '24px', fontWeight: 600, color: schedulerConfig?.dry_run ? '#f59e0b' : '#10b981' }}>
                {schedulerConfig?.dry_run ? 'Activé' : 'Désactivé'}
              </div>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Catégorie Wikipédia
              </label>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>
                {schedulerConfig?.category || 'Non configuré'}
              </div>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '14px', color: '#a0a0a0', marginBottom: '8px' }}>
                Articles à traiter
              </label>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5' }}>
                {schedulerConfig?.articles_to_process || 'Non configuré'}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
          Contrôles
        </h3>
        
        {/* Automation Options */}
        <div style={{ marginBottom: '16px', padding: '16px', backgroundColor: '#0a0a0a', borderRadius: '6px', border: '1px solid #2a2a2a' }}>
          <h4 style={{ fontSize: '12px', fontWeight: 500, color: '#a0a0a0', marginBottom: '12px', textTransform: 'uppercase' }}>
            Options d'automatisation
          </h4>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={includeAnalyzed}
                onChange={(e) => setIncludeAnalyzed(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ fontSize: '14px', color: '#f5f5f5' }}>
                Inclure les articles déjà analysés
              </span>
            </label>
            
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={liaMode}
                onChange={(e) => setLiaMode(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ fontSize: '14px', color: '#f5f5f5' }}>
                Utiliser l'analyse IA (Gemini)
              </span>
            </label>
          </div>
        </div>
        
        {manualRunMessage && (
          <div style={{ 
            padding: '12px', 
            backgroundColor: 'rgba(16, 185, 129, 0.1)', 
            border: '1px solid #10b981', 
            borderRadius: '6px', 
            marginBottom: '16px',
            color: '#10b981',
            fontSize: '14px'
          }}>
            {manualRunMessage}
          </div>
        )}
        
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {!isActive ? (
            <button
              className="btn btn-primary"
              onClick={startScheduler}
              disabled={actionLoading}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <Play style={{ width: '16px', height: '16px' }} />
              {actionLoading ? 'Démarrage...' : 'Démarrer'}
            </button>
          ) : isPaused ? (
            <button
              className="btn btn-primary"
              onClick={resumeScheduler}
              disabled={actionLoading}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <Play style={{ width: '16px', height: '16px' }} />
              {actionLoading ? 'Reprise...' : 'Reprendre'}
            </button>
          ) : (
            <button
              className="btn btn-secondary"
              onClick={pauseScheduler}
              disabled={actionLoading}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <Pause style={{ width: '16px', height: '16px' }} />
              {actionLoading ? 'Pause...' : 'Pause'}
            </button>
          )}
          <button
            className="btn btn-danger"
            onClick={stopScheduler}
            disabled={actionLoading || !isActive}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <Square style={{ width: '16px', height: '16px' }} />
            {actionLoading ? 'Arrêt...' : 'Arrêter'}
          </button>
          <button
            onClick={runManualScheduler}
            disabled={manualRunLoading || actionLoading || (automationStatus && automationStatus.status === 'running')}
            style={{
              padding: '8px 16px',
              backgroundColor: '#8b5cf6',
              border: 'none',
              borderRadius: '6px',
              color: '#ffffff',
              fontSize: '14px',
              cursor: (manualRunLoading || actionLoading || (automationStatus && automationStatus.status === 'running')) ? 'not-allowed' : 'pointer',
              opacity: (manualRunLoading || actionLoading || (automationStatus && automationStatus.status === 'running')) ? 0.5 : 1,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            {manualRunLoading ? (
              <>
                <div style={{
                  width: '14px',
                  height: '14px',
                  border: '2px solid #ffffff',
                  borderTop: '2px solid transparent',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite'
                }} />
                Lancement en cours...
              </>
            ) : (
              'Lancer manuellement'
            )}
          </button>
        </div>

        {/* Automation Controls */}
        {automationStatus && automationStatus.status === 'running' && (
          <div style={{ 
            marginTop: '16px', 
            padding: '16px', 
            backgroundColor: 'rgba(139, 92, 246, 0.1)', 
            borderRadius: '6px', 
            border: '1px solid #8b5cf6' 
          }}>
            <div style={{ fontSize: '14px', color: '#a0a0a0', marginBottom: '12px' }}>
              Automatisation en cours
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {automationStatus.status === 'paused' ? (
                <button
                  onClick={resumeAutomation}
                  disabled={actionLoading}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#10b981',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#ffffff',
                    fontSize: '14px',
                    cursor: actionLoading ? 'not-allowed' : 'pointer',
                    opacity: actionLoading ? 0.5 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <Play style={{ width: '14px', height: '14px' }} />
                  Reprendre
                </button>
              ) : (
                <button
                  onClick={pauseAutomation}
                  disabled={actionLoading}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#f59e0b',
                    border: 'none',
                    borderRadius: '4px',
                    color: '#ffffff',
                    fontSize: '14px',
                    cursor: actionLoading ? 'not-allowed' : 'pointer',
                    opacity: actionLoading ? 0.5 : 1,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <Pause style={{ width: '14px', height: '14px' }} />
                  Pause
                </button>
              )}
              <button
                onClick={stopAutomation}
                disabled={actionLoading}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#ef4444',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#ffffff',
                  fontSize: '14px',
                  cursor: actionLoading ? 'not-allowed' : 'pointer',
                  opacity: actionLoading ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <Square style={{ width: '14px', height: '14px' }} />
                Arrêter
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  )
}
