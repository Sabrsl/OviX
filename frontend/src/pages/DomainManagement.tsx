/**
 * Domain Management Page
 * 
 * Provides UI for managing domain_to_site_name mappings
 * in case_normalization_data.yaml.
 * 
 * Reuses design tokens and patterns from Settings.tsx.
 * Buttons now use the shared <Button /> component (see Button.tsx).
 */

import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Search, Plus, Edit, Trash2, CheckCircle, AlertTriangle, X, RefreshCw, Zap } from 'lucide-react'
import {
  listDomains,
  validateDomain,
  addDomain,
  updateDomain,
  deleteDomain,
  DomainEntry,
  DomainListResponse,
  AddDomainRequest,
  UpdateDomainRequest,
} from '../api/domain_management.api'
import Button from '../components/Button'

// Design tokens from Settings.tsx
const colors = {
  bgPanel: '#161616',
  bgInput: '#1a1a1a',
  border: '#2a2a2a',
  textPrimary: '#f5f5f5',
  textSecondary: '#e0e0e0',
  textMuted: '#a0a0a0',
  accent: '#3b82f6',
  accentSoft: 'rgba(59, 130, 246, 0.12)',
  success: '#059669',
  successSoft: 'rgba(5, 150, 105, 0.1)',
  successBorder: 'rgba(5, 150, 105, 0.3)',
  error: '#ef4444',
  errorSoft: 'rgba(239, 68, 68, 0.1)',
  errorBorder: 'rgba(239, 68, 68, 0.3)',
}

interface Notice {
  type: 'success' | 'error'
  message: string
}

export default function DomainManagement() {
  const [domains, setDomains] = useState<DomainEntry[]>([])
  const [statistics, setStatistics] = useState<{ total: number; valid: number; conflicts: number }>({ total: 0, valid: 0, conflicts: 0 })
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [notice, setNotice] = useState<Notice | null>(null)
  
  // Modal states
  const [showAddModal, setShowAddModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [selectedDomain, setSelectedDomain] = useState<DomainEntry | null>(null)
  
  // Form states
  const [addForm, setAddForm] = useState({ domain: '', site_name: '' })
  const [editForm, setEditForm] = useState({ new_domain: '', new_site_name: '' })
  const [formErrors, setFormErrors] = useState<{ domain?: string; site_name?: string }>({})
  const [validating, setValidating] = useState(false)

  const loadDomains = useCallback(async () => {
    try {
      setLoading(true)
      const response: DomainListResponse = await listDomains(searchQuery || undefined)
      setDomains(response.domains)
      setStatistics(response.statistics)
    } catch (error) {
      console.error('Failed to load domains:', error)
      showNoticeFn({ type: 'error', message: 'Erreur lors du chargement des domaines' })
    } finally {
      setLoading(false)
    }
  }, [searchQuery])

  useEffect(() => {
    loadDomains()
  }, [loadDomains])

  const showNoticeFn = useCallback((n: Notice) => {
    setNotice(n)
    setTimeout(() => setNotice(null), 4000)
  }, [])

  const handleAddDomain = async () => {
    setFormErrors({})
    setValidating(true)
    
    try {
      const validation = await validateDomain(addForm.domain, addForm.site_name)
      
      if (!validation.valid) {
        setFormErrors({
          domain: validation.errors.find(e => e.toLowerCase().includes('domain')) || '',
          site_name: validation.errors.find(e => e.toLowerCase().includes('site')) || '',
        })
        if (validation.errors.length > 0 && !formErrors.domain && !formErrors.site_name) {
          setFormErrors({ domain: validation.errors[0] })
        }
        return
      }
      
      if (validation.warnings.length > 0) {
        if (!confirm(`${validation.warnings.join('\n')}\n\nContinuer?`)) {
          return
        }
      }
      
      await addDomain({ domain: addForm.domain, site_name: addForm.site_name, source: 'manual' })
      showNoticeFn({ type: 'success', message: 'Domaine ajouté avec succès' })
      setShowAddModal(false)
      setAddForm({ domain: '', site_name: '' })
      loadDomains()
    } catch (error: any) {
      console.error('Failed to add domain:', error)
      showNoticeFn({ type: 'error', message: error.message || 'Erreur lors de l\'ajout' })
    } finally {
      setValidating(false)
    }
  }

  const handleEditDomain = async () => {
    if (!selectedDomain) return
    
    setFormErrors({})
    setValidating(true)
    
    try {
      const request: UpdateDomainRequest = {
        domain: selectedDomain.domain,
        new_domain: editForm.new_domain || undefined,
        new_site_name: editForm.new_site_name || undefined,
      }
      
      await updateDomain(selectedDomain.domain, request)
      showNoticeFn({ type: 'success', message: 'Domaine modifié avec succès' })
      setShowEditModal(false)
      setEditForm({ new_domain: '', new_site_name: '' })
      setSelectedDomain(null)
      loadDomains()
    } catch (error: any) {
      console.error('Failed to update domain:', error)
      showNoticeFn({ type: 'error', message: error.message || 'Erreur lors de la modification' })
    } finally {
      setValidating(false)
    }
  }

  const handleDeleteDomain = async () => {
    if (!selectedDomain) return
    
    try {
      await deleteDomain(selectedDomain.domain)
      showNoticeFn({ type: 'success', message: 'Domaine supprimé avec succès' })
      setShowDeleteModal(false)
      setSelectedDomain(null)
      loadDomains()
    } catch (error: any) {
      console.error('Failed to delete domain:', error)
      showNoticeFn({ type: 'error', message: error.message || 'Erreur lors de la suppression' })
    }
  }

  const openEditModal = (domain: DomainEntry) => {
    setSelectedDomain(domain)
    setEditForm({ new_domain: domain.domain, new_site_name: domain.site_name })
    setShowEditModal(true)
  }

  const openDeleteModal = (domain: DomainEntry) => {
    setSelectedDomain(domain)
    setShowDeleteModal(true)
  }

  return (
    <div style={{ maxWidth: '860px', margin: '0 auto' }}>
      <style>{`
        @keyframes ovix-fade-in {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .ovix-panel { animation: ovix-fade-in 180ms ease-out; }
        .ovix-input {
          transition: border-color 150ms ease, box-shadow 150ms ease;
        }
        .ovix-input:focus {
          outline: none;
          border-color: ${colors.accent} !important;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
        }
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: '28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '15.5px', fontWeight: 600, color: colors.textPrimary, margin: 0, letterSpacing: '-0.01em' }}>
            Gestion des domaines
          </h1>
          <p style={{ fontSize: '10.5px', color: colors.textMuted, margin: '4px 0 0' }}>
            Référentiel domain_to_site_name
          </p>
        </div>
        <Button variant="neutral" onClick={() => setShowAddModal(true)}>
          <Plus style={{ width: '14px', height: '14px' }} />
          Ajouter un domaine
        </Button>
      </div>

      {/* Notice banner */}
      {notice && (
        <div
          className="ovix-panel"
          role="alert"
          style={{
            marginBottom: '20px',
            padding: '12px 16px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            backgroundColor: notice.type === 'success' ? colors.successSoft : colors.errorSoft,
            border: `1px solid ${notice.type === 'success' ? colors.successBorder : colors.errorBorder}`,
            color: notice.type === 'success' ? colors.success : colors.error,
            fontSize: '11.5px',
          }}
        >
          {notice.type === 'success' ? (
            <CheckCircle style={{ width: '17px', height: '17px', flexShrink: 0 }} />
          ) : (
            <AlertTriangle style={{ width: '17px', height: '17px', flexShrink: 0 }} />
          )}
          <span style={{ flex: 1 }}>{notice.message}</span>
          <button
            onClick={() => setNotice(null)}
            aria-label="Fermer"
            style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, display: 'flex' }}
          >
            <X style={{ width: '13px', height: '13px' }} />
          </button>
        </div>
      )}

      {/* Statistics */}
      <div
        className="ovix-panel"
        style={{
          marginBottom: '20px',
          padding: '16px',
          backgroundColor: colors.bgPanel,
          border: `1px solid ${colors.border}`,
          borderRadius: '10px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ fontSize: '10px', color: colors.textMuted, marginBottom: '4px' }}>Total</div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary }}>{statistics.total}</div>
        </div>
        <div>
          <div style={{ fontSize: '10px', color: colors.textMuted, marginBottom: '4px' }}>Valides</div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: colors.success }}>{statistics.valid}</div>
        </div>
        <div>
          <div style={{ fontSize: '10px', color: colors.textMuted, marginBottom: '4px' }}>Conflits</div>
          <div style={{ fontSize: '18px', fontWeight: 600, color: colors.error }}>{statistics.conflicts}</div>
        </div>
      </div>

      {/* Search bar */}
      <div
        className="ovix-panel"
        style={{
          marginBottom: '20px',
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
        }}
      >
        <div style={{ position: 'relative', flex: 1 }}>
          <Search
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              width: '14px',
              height: '14px',
              color: colors.textMuted,
            }}
          />
          <input
            type="text"
            placeholder="Rechercher un domaine ou un nom Wikipédia..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="ovix-input"
            style={{
              width: '100%',
              padding: '10px 12px 10px 40px',
              backgroundColor: colors.bgInput,
              color: colors.textPrimary,
              border: `1px solid ${colors.border}`,
              borderRadius: '7px',
              fontSize: '11px',
            }}
          />
        </div>
        <Button variant="neutral" onClick={loadDomains} disabled={loading}>
          <RefreshCw style={{ width: '14px', height: '14px', ...(loading ? { animation: 'spin 1s linear infinite' } : {}) }} />
          Actualiser
        </Button>
      </div>

      {/* Domain table */}
      <div
        className="ovix-panel"
        style={{
          backgroundColor: colors.bgPanel,
          border: `1px solid ${colors.border}`,
          borderRadius: '10px',
          overflow: 'hidden',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${colors.border}`, backgroundColor: colors.bgInput }}>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: colors.textSecondary, fontSize: '10px' }}>
                  Domaine
                </th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: colors.textSecondary, fontSize: '10px' }}>
                  Nom Wikipédia
                </th>
                <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: colors.textSecondary, fontSize: '10px' }}>
                  Statut
                </th>
                <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: colors.textSecondary, fontSize: '10px' }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} style={{ padding: '40px', textAlign: 'center', color: colors.textMuted }}>
                    Chargement...
                  </td>
                </tr>
              ) : domains.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ padding: '40px', textAlign: 'center', color: colors.textMuted }}>
                    {searchQuery ? 'Aucun résultat' : 'Aucun domaine enregistré'}
                  </td>
                </tr>
              ) : (
                domains.map((domain) => (
                  <tr key={domain.domain} style={{ borderBottom: `1px solid ${colors.border}` }}>
                    <td style={{ padding: '12px 16px', color: colors.textPrimary }}>
                      {domain.domain}
                    </td>
                    <td style={{ padding: '12px 16px', color: colors.textSecondary }}>
                      {domain.site_name}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 8px',
                          backgroundColor: colors.successSoft,
                          color: colors.success,
                          borderRadius: '4px',
                          fontSize: '10px',
                          fontWeight: 500,
                        }}
                      >
                        <CheckCircle style={{ width: '12px', height: '12px' }} />
                        Valide
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                        <Button
                          variant="primary"
                          onClick={() => openEditModal(domain)}
                          style={{ padding: '6px 10px', fontSize: '10px' }}
                        >
                          <Edit style={{ width: '12px', height: '12px' }} />
                          Modifier
                        </Button>
                        <Button
                          variant="danger"
                          onClick={() => openDeleteModal(domain)}
                          style={{ padding: '6px 10px', fontSize: '10px' }}
                        >
                          <Trash2 style={{ width: '12px', height: '12px' }} />
                          Supprimer
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={(e) => e.target === e.currentTarget && setShowAddModal(false)}
        >
          <div
            className="ovix-panel"
            style={{
              backgroundColor: colors.bgPanel,
              border: `1px solid ${colors.border}`,
              borderRadius: '10px',
              padding: '24px',
              width: '100%',
              maxWidth: '450px',
            }}
          >
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 16px' }}>
              Ajouter un domaine
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: colors.textSecondary, marginBottom: '6px' }}>
                  Domaine
                </label>
                <input
                  type="text"
                  value={addForm.domain}
                  onChange={(e) => setAddForm({ ...addForm, domain: e.target.value })}
                  placeholder="example.org"
                  className="ovix-input"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    backgroundColor: colors.bgInput,
                    color: colors.textPrimary,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '7px',
                    fontSize: '11px',
                  }}
                />
                {formErrors.domain && (
                  <div style={{ fontSize: '10px', color: colors.error, marginTop: '4px' }}>{formErrors.domain}</div>
                )}
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: colors.textSecondary, marginBottom: '6px' }}>
                  Nom Wikipédia
                </label>
                <input
                  type="text"
                  value={addForm.site_name}
                  onChange={(e) => setAddForm({ ...addForm, site_name: e.target.value })}
                  placeholder="Organisation X"
                  className="ovix-input"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    backgroundColor: colors.bgInput,
                    color: colors.textPrimary,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '7px',
                    fontSize: '11px',
                  }}
                />
                {formErrors.site_name && (
                  <div style={{ fontSize: '10px', color: colors.error, marginTop: '4px' }}>{formErrors.site_name}</div>
                )}
              </div>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
                <Button
                  variant="neutral"
                  onClick={() => {
                    setShowAddModal(false)
                    setAddForm({ domain: '', site_name: '' })
                    setFormErrors({})
                  }}
                >
                  Annuler
                </Button>
                <Button
                  variant="neutral"
                  onClick={handleAddDomain}
                  disabled={validating || !addForm.domain || !addForm.site_name}
                >
                  {validating ? 'Validation...' : 'Ajouter'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && selectedDomain && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={(e) => e.target === e.currentTarget && setShowEditModal(false)}
        >
          <div
            className="ovix-panel"
            style={{
              backgroundColor: colors.bgPanel,
              border: `1px solid ${colors.border}`,
              borderRadius: '10px',
              padding: '24px',
              width: '100%',
              maxWidth: '450px',
            }}
          >
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 16px' }}>
              Modifier le domaine
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: colors.textSecondary, marginBottom: '6px' }}>
                  Domaine
                </label>
                <input
                  type="text"
                  value={editForm.new_domain}
                  onChange={(e) => setEditForm({ ...editForm, new_domain: e.target.value })}
                  className="ovix-input"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    backgroundColor: colors.bgInput,
                    color: colors.textPrimary,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '7px',
                    fontSize: '11px',
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: colors.textSecondary, marginBottom: '6px' }}>
                  Nom Wikipédia
                </label>
                <input
                  type="text"
                  value={editForm.new_site_name}
                  onChange={(e) => setEditForm({ ...editForm, new_site_name: e.target.value })}
                  className="ovix-input"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    backgroundColor: colors.bgInput,
                    color: colors.textPrimary,
                    border: `1px solid ${colors.border}`,
                    borderRadius: '7px',
                    fontSize: '11px',
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
                <Button
                  variant="neutral"
                  onClick={() => {
                    setShowEditModal(false)
                    setEditForm({ new_domain: '', new_site_name: '' })
                    setSelectedDomain(null)
                  }}
                >
                  Annuler
                </Button>
                <Button variant="neutral" onClick={handleEditDomain} disabled={validating}>
                  {validating ? 'Modification...' : 'Modifier'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {showDeleteModal && selectedDomain && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={(e) => e.target === e.currentTarget && setShowDeleteModal(false)}
        >
          <div
            className="ovix-panel"
            style={{
              backgroundColor: colors.bgPanel,
              border: `1px solid ${colors.border}`,
              borderRadius: '10px',
              padding: '24px',
              width: '100%',
              maxWidth: '400px',
            }}
          >
            <h2 style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 12px' }}>
              Supprimer ce domaine ?
            </h2>
            <p style={{ fontSize: '11px', color: colors.textSecondary, margin: '0 0 20px' }}>
              {selectedDomain.domain} → {selectedDomain.site_name}
            </p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <Button
                variant="neutral"
                onClick={() => {
                  setShowDeleteModal(false)
                  setSelectedDomain(null)
                }}
              >
                Annuler
              </Button>
              <Button variant="danger" onClick={handleDeleteDomain}>
                Supprimer
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}