import { useState, useEffect, useMemo, useCallback } from 'react'
import { useApi } from '../hooks/useApi'
import { historyApi } from '../api/history.api'
import { AlertTriangle, ExternalLink, Clock, CheckCircle, XCircle, RefreshCw, Bug, Link2, Inbox } from 'lucide-react'

interface ManualReviewItem {
  id: string
  article_title: string
  url: string
  status: 'pending' | 'reviewed' | 'approved' | 'rejected'
  detected_at: string
  context?: string
  suggested_replacement?: string
}

type FilterKey = 'all' | 'pending' | 'approved' | 'rejected'

// API function
const fetchManualReviewItems = async (): Promise<ManualReviewItem[]> => {
  try {
    const response = await fetch('/api/manual-review-analyzed')
    if (!response.ok) {
      console.error('API response not ok:', response.status, response.statusText)
      throw new Error('Failed to fetch manual review items')
    }
    const data = await response.json()
    console.log('Manual review items loaded:', data)
    return data
  } catch (error) {
    console.error('Error fetching manual review items:', error)
    throw error
  }
}

const statusConfig: Record<ManualReviewItem['status'], { label: string; color: string; icon: typeof Clock }> = {
  pending: { label: 'En attente', color: '#f59e0b', icon: Clock },
  reviewed: { label: 'Révisé', color: '#3b82f6', icon: AlertTriangle },
  approved: { label: 'Approuvé', color: '#10b981', icon: CheckCircle },
  rejected: { label: 'Rejeté', color: '#ef4444', icon: XCircle }
}

const filterLabels: Record<FilterKey, string> = {
  all: 'Tous',
  pending: 'En attente',
  approved: 'Approuvés',
  rejected: 'Rejetés'
}

export default function ManualReview() {
  const [items, setItems] = useState<ManualReviewItem[]>([])
  const [publishedHistory, setPublishedHistory] = useState<any>(null)
  const [filter, setFilter] = useState<FilterKey>('all')
  const [selectedItem, setSelectedItem] = useState<ManualReviewItem | null>(null)
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, loading, error, refetch } = useApi<ManualReviewItem[]>(fetchManualReviewItems)

  useEffect(() => {
    const loadData = async () => {
      if (data) {
        // Sort by detected date, most recent first
        const sortedData = [...data].sort((a: ManualReviewItem, b: ManualReviewItem) => {
          const dateA = new Date(a.detected_at || 0).getTime()
          const dateB = new Date(b.detected_at || 0).getTime()
          return dateB - dateA // Descending order (most recent first)
        })
        setItems(sortedData)
      }

      // Load published history for status checking
      try {
        const publishedData = await historyApi.getPublishedHistory()
        setPublishedHistory(publishedData)
      } catch (err) {
        console.error('Failed to load published history:', err)
      }
    }

    loadData()
  }, [data])

  // Close modal on Escape for better keyboard UX
  useEffect(() => {
    if (!selectedItem) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedItem(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedItem])

  const handleRefresh = useCallback(() => {
    setActionError(null)
    refetch()
  }, [refetch])

  const handleDebug = async () => {
    try {
      const response = await fetch('/api/manual-review-analyzed-debug')
      const debugInfo = await response.json()
      console.log('Debug info:', debugInfo)
      alert(JSON.stringify(debugInfo, null, 2))
    } catch (error) {
      console.error('Debug error:', error)
      alert('Erreur de debug: ' + error)
    }
  }

  const performAction = async (action: 'approve' | 'reject', itemId: string, articleTitle: string, url: string) => {
    setActionError(null)
    setActionLoadingId(itemId)
    try {
      const response = await fetch(`/api/manual-review/${itemId}/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action,
          article_title: articleTitle,
          url: url
        })
      })

      const responseData = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(responseData?.detail || `Échec de l'action "${action}"`)
      }

      handleRefresh()
    } catch (err) {
      console.error(`Error performing action "${action}":`, err)
      setActionError((err as Error).message || 'Une erreur est survenue')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleApprove = (itemId: string, articleTitle: string, url: string) =>
    performAction('approve', itemId, articleTitle, url)

  const handleReject = (itemId: string, articleTitle: string, url: string) =>
    performAction('reject', itemId, articleTitle, url)

  const filteredItems = useMemo(() => {
    return items
      .filter(item => {
        if (filter === 'all') return true
        const itemStatus = item.status?.toLowerCase() || 'pending'
        return itemStatus === filter.toLowerCase()
      })
      .map(item => {
        const isArticlePublished = publishedHistory?.items?.some((pubItem: any) =>
          pubItem.title === item.article_title || pubItem.article_title === item.article_title
        )
        return { ...item, isArticlePublished }
      })
  }, [items, filter, publishedHistory])

  const counts = useMemo(() => {
    const base: Record<FilterKey, number> = { all: items.length, pending: 0, approved: 0, rejected: 0 }
    for (const item of items) {
      const s = (item.status?.toLowerCase() || 'pending') as FilterKey
      if (s === 'pending' || s === 'approved' || s === 'rejected') base[s] += 1
    }
    return base
  }, [items])

  return (
    <div style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto', fontFamily: 'inherit', boxSizing: 'border-box', overflowX: 'hidden', width: '100%' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '16px',
        marginBottom: '20px',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: '1 1 260px' }}>
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '8px',
            backgroundColor: '#3b82f620',
            border: '1px solid #3b82f640',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            <Link2 style={{ width: '17px', height: '17px', color: '#3b82f6' }} />
          </div>
          <div>
            <h1 style={{ fontSize: '17px', fontWeight: 600, color: '#e0e0e0', letterSpacing: '-0.01em', lineHeight: 1.3 }}>
              Liens nécessitant révision manuelle
            </h1>
            <p style={{ fontSize: '12px', color: '#8a8a8a', marginTop: '2px' }}>
              Vérifiez et corrigez les liens détectés avant publication
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button
            onClick={handleDebug}
            title="Afficher les informations de débogage"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 12px',
              backgroundColor: 'transparent',
              color: '#a0a0a0',
              border: '1px solid #333',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 500,
              transition: 'background-color 0.15s, color 0.15s, border-color 0.15s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#2a2a2a'
              e.currentTarget.style.color = '#e0e0e0'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
              e.currentTarget.style.color = '#a0a0a0'
            }}
          >
            <Bug style={{ width: '13px', height: '13px' }} />
            Debug
          </button>
          <button
            onClick={handleRefresh}
            disabled={loading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 12px',
              backgroundColor: '#2a2a2a',
              color: '#e0e0e0',
              border: '1px solid #3a3a3a',
              borderRadius: '6px',
              cursor: loading ? 'default' : 'pointer',
              fontSize: '12px',
              fontWeight: 500,
              opacity: loading ? 0.6 : 1,
              transition: 'background-color 0.15s'
            }}
            onMouseEnter={(e) => { if (!loading) e.currentTarget.style.backgroundColor = '#333' }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#2a2a2a' }}
          >
            <RefreshCw style={{ width: '13px', height: '13px', animation: loading ? 'mr-spin 0.9s linear infinite' : 'none' }} />
            Actualiser
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex',
        gap: '6px',
        marginBottom: '20px',
        padding: '6px',
        backgroundColor: '#1a1a1a',
        borderRadius: '9px',
        border: '1px solid #2a2a2a',
        flexWrap: 'wrap'
      }}>
        {(Object.keys(filterLabels) as FilterKey[]).map((key) => {
          const isActive = filter === key
          return (
            <button
              key={key}
              onClick={() => setFilter(key)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 13px',
                backgroundColor: isActive ? '#3b82f6' : 'transparent',
                color: isActive ? '#ffffff' : '#a0a0a0',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12.5px',
                fontWeight: 500,
                transition: 'background-color 0.15s, color 0.15s'
              }}
              onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.backgroundColor = '#2a2a2a' }}
              onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              {filterLabels[key]}
              <span style={{
                fontSize: '10.5px',
                fontWeight: 600,
                padding: '1px 6px',
                borderRadius: '999px',
                backgroundColor: isActive ? 'rgba(255,255,255,0.2)' : '#2a2a2a',
                color: isActive ? '#ffffff' : '#8a8a8a',
                minWidth: '18px',
                textAlign: 'center'
              }}>
                {counts[key]}
              </span>
            </button>
          )
        })}
      </div>

      {actionError && (
        <div style={{
          padding: '10px 14px',
          backgroundColor: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          borderRadius: '8px',
          color: '#ef4444',
          fontSize: '12.5px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <XCircle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          {actionError}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'grid', gap: '12px' }}>
          {[0, 1, 2].map((i) => (
            <div key={i} style={{
              padding: '18px',
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '10px',
              overflow: 'hidden',
              position: 'relative'
            }}>
              <div style={{ height: '13px', width: '45%', backgroundColor: '#2a2a2a', borderRadius: '4px', marginBottom: '10px' }} />
              <div style={{ height: '11px', width: '65%', backgroundColor: '#242424', borderRadius: '4px' }} />
              <div style={{
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)',
                animation: 'mr-shimmer 1.4s infinite'
              }} />
            </div>
          ))}
        </div>
      ) : error ? (
        <div style={{
          padding: '16px',
          backgroundColor: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.25)',
          borderRadius: '10px',
          color: '#ef4444'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', fontSize: '13px', fontWeight: 500 }}>
            <AlertTriangle style={{ width: '15px', height: '15px', flexShrink: 0 }} />
            Erreur: {error}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleDebug}
              style={{
                padding: '7px 13px',
                backgroundColor: '#f59e0b',
                color: '#1a1a1a',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 600
              }}
            >
              Debug
            </button>
            <button
              onClick={handleRefresh}
              style={{
                padding: '7px 13px',
                backgroundColor: 'transparent',
                color: '#ef4444',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 600
              }}
            >
              Réessayer
            </button>
          </div>
        </div>
      ) : filteredItems.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '56px 20px',
          color: '#a0a0a0',
          backgroundColor: '#1a1a1a',
          border: '1px dashed #2a2a2a',
          borderRadius: '10px'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            margin: '0 auto 14px',
            borderRadius: '10px',
            backgroundColor: '#2a2a2a',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Inbox style={{ width: '19px', height: '19px', color: '#666' }} />
          </div>
          <div style={{ marginBottom: '6px', fontSize: '13.5px', color: '#c0c0c0', fontWeight: 500 }}>
            Aucun lien nécessitant révision manuelle
          </div>
          <div style={{ fontSize: '11.5px', color: '#666' }}>
            Filtre actuel: {filterLabels[filter]} · Total: {items.length}
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {filteredItems.map(item => {
            const config = statusConfig[item.status] || statusConfig.pending
            const StatusIcon = config.icon
            const isActing = actionLoadingId === item.id
            return (
              <div
                key={item.id}
                style={{
                  padding: '16px 18px',
                  backgroundColor: '#1a1a1a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  transition: 'border-color 0.15s, background-color 0.15s',
                  width: '100%',
                  maxWidth: '100%',
                  boxSizing: 'border-box',
                  overflow: 'hidden'
                }}
                onClick={() => setSelectedItem(item)}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#3a3a3a' }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#2a2a2a' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '10px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                      <h3 style={{
                        fontSize: '13.5px',
                        fontWeight: 600,
                        color: '#e0e0e0',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '100%'
                      }}>
                        {item.article_title}
                      </h3>
                      {(item as any).isArticlePublished && (
                        <span style={{
                          padding: '2px 7px',
                          backgroundColor: '#10b98118',
                          color: '#10b981',
                          fontSize: '10px',
                          fontWeight: 600,
                          borderRadius: '4px',
                          border: '1px solid #10b98135',
                          whiteSpace: 'nowrap'
                        }}>
                          Article publié
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11.5px', color: '#8a8a8a' }}>
                      <ExternalLink style={{ width: '12px', height: '12px', flexShrink: 0 }} />
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          color: '#3b82f6',
                          textDecoration: 'none',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {item.url}
                      </a>
                    </div>
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    backgroundColor: `${config.color}18`,
                    border: `1px solid ${config.color}35`,
                    borderRadius: '999px',
                    flexShrink: 0
                  }}>
                    <StatusIcon style={{ width: '12px', height: '12px', color: config.color }} />
                    <span style={{ fontSize: '11px', color: config.color, fontWeight: 600 }}>
                      {config.label}
                    </span>
                  </div>
                </div>

                {item.context && (
                  <div style={{
                    padding: '10px 12px',
                    backgroundColor: '#0f0f0f',
                    border: '1px solid #232323',
                    borderRadius: '7px',
                    fontSize: '11.5px',
                    lineHeight: 1.5,
                    color: '#909090',
                    marginBottom: '10px',
                    overflow: 'hidden',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical'
                  }}>
                    {item.context}
                  </div>
                )}

                {item.suggested_replacement && (
                  <div style={{
                    fontSize: '11.5px',
                    color: '#10b981',
                    marginBottom: '10px',
                    display: 'flex',
                    gap: '4px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                    <strong style={{ fontWeight: 600, flexShrink: 0 }}>Remplacement suggéré:</strong>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.suggested_replacement}</span>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '8px', fontSize: '10.5px', color: '#666' }}>
                  <Clock style={{ width: '11px', height: '11px' }} />
                  <span>Détecté: {new Date(item.detected_at).toLocaleString('fr-FR')}</span>
                </div>

                {item.status === 'pending' && (
                  <div style={{ display: 'flex', gap: '8px', marginTop: '12px', width: '100%', minWidth: 0 }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleApprove(item.id, item.article_title, item.url)
                      }}
                      disabled={isActing}
                      style={{
                        flex: '1 1 0%',
                        minWidth: 0,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        padding: '8px 14px',
                        backgroundColor: '#10b981',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '7px',
                        cursor: isActing ? 'default' : 'pointer',
                        fontSize: '12.5px',
                        fontWeight: 600,
                        opacity: isActing ? 0.65 : 1,
                        transition: 'opacity 0.15s, filter 0.15s'
                      }}
                      onMouseEnter={(e) => { if (!isActing) e.currentTarget.style.filter = 'brightness(1.08)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.filter = 'none' }}
                    >
                      {isActing ? (
                        <RefreshCw style={{ width: '12px', height: '12px', animation: 'mr-spin 0.9s linear infinite' }} />
                      ) : (
                        <CheckCircle style={{ width: '12px', height: '12px' }} />
                      )}
                      Approuver
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleReject(item.id, item.article_title, item.url)
                      }}
                      disabled={isActing}
                      style={{
                        flex: '1 1 0%',
                        minWidth: 0,
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        padding: '8px 14px',
                        backgroundColor: '#ef4444',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '7px',
                        cursor: isActing ? 'default' : 'pointer',
                        fontSize: '12.5px',
                        fontWeight: 600,
                        opacity: isActing ? 0.65 : 1,
                        transition: 'opacity 0.15s, filter 0.15s'
                      }}
                      onMouseEnter={(e) => { if (!isActing) e.currentTarget.style.filter = 'brightness(1.08)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.filter = 'none' }}
                    >
                      {isActing ? (
                        <RefreshCw style={{ width: '12px', height: '12px', animation: 'mr-spin 0.9s linear infinite' }} />
                      ) : (
                        <XCircle style={{ width: '12px', height: '12px' }} />
                      )}
                      Rejeter
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Detail Modal */}
      {selectedItem && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px'
          }}
          onClick={() => setSelectedItem(null)}
        >
          <div
            style={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #2a2a2a',
              borderRadius: '12px',
              padding: '22px',
              maxWidth: '600px',
              width: '100%',
              maxHeight: '80vh',
              overflowY: 'auto',
              boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '14px' }}>
              <h2 style={{ fontSize: '15px', fontWeight: 600, color: '#e0e0e0', lineHeight: 1.4 }}>
                {selectedItem.article_title}
              </h2>
              {(() => {
                const config = statusConfig[selectedItem.status] || statusConfig.pending
                const StatusIcon = config.icon
                return (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '3px 9px',
                    backgroundColor: `${config.color}18`,
                    border: `1px solid ${config.color}35`,
                    borderRadius: '999px',
                    flexShrink: 0
                  }}>
                    <StatusIcon style={{ width: '11px', height: '11px', color: config.color }} />
                    <span style={{ fontSize: '10.5px', color: config.color, fontWeight: 600 }}>{config.label}</span>
                  </div>
                )
              })()}
            </div>

            <div style={{ marginBottom: '14px' }}>
              <label style={{ fontSize: '11px', color: '#8a8a8a', display: 'block', marginBottom: '4px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                URL
              </label>
              <a
                href={selectedItem.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#3b82f6', textDecoration: 'none', fontSize: '12.5px', wordBreak: 'break-all' }}
              >
                {selectedItem.url}
              </a>
            </div>
            {selectedItem.context && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '11px', color: '#8a8a8a', display: 'block', marginBottom: '4px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  Contexte
                </label>
                <div style={{ padding: '11px', backgroundColor: '#0f0f0f', border: '1px solid #232323', borderRadius: '7px', fontSize: '12.5px', lineHeight: 1.55, color: '#c0c0c0' }}>
                  {selectedItem.context}
                </div>
              </div>
            )}
            {selectedItem.suggested_replacement && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '11px', color: '#8a8a8a', display: 'block', marginBottom: '4px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  Remplacement suggéré
                </label>
                <div style={{ padding: '11px', backgroundColor: '#0f0f0f', border: '1px solid #10b98125', borderRadius: '7px', fontSize: '12.5px', lineHeight: 1.55, color: '#10b981' }}>
                  {selectedItem.suggested_replacement}
                </div>
              </div>
            )}
            <div style={{ marginBottom: '14px', fontSize: '11px', color: '#666', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock style={{ width: '11px', height: '11px' }} />
              Détecté: {new Date(selectedItem.detected_at).toLocaleString('fr-FR')}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '20px', gap: '10px', flexWrap: 'wrap' }}>
              {selectedItem.status === 'pending' ? (
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => {
                      handleApprove(selectedItem.id, selectedItem.article_title, selectedItem.url)
                      setSelectedItem(null)
                    }}
                    style={{
                      padding: '8px 14px',
                      backgroundColor: '#10b981',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '7px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <CheckCircle style={{ width: '12px', height: '12px' }} />
                    Approuver
                  </button>
                  <button
                    onClick={() => {
                      handleReject(selectedItem.id, selectedItem.article_title, selectedItem.url)
                      setSelectedItem(null)
                    }}
                    style={{
                      padding: '8px 14px',
                      backgroundColor: '#ef4444',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '7px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: 600,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <XCircle style={{ width: '12px', height: '12px' }} />
                    Rejeter
                  </button>
                </div>
              ) : <div />}
              <button
                onClick={() => setSelectedItem(null)}
                style={{
                  padding: '8px 14px',
                  backgroundColor: '#2a2a2a',
                  color: '#e0e0e0',
                  border: '1px solid #3a3a3a',
                  borderRadius: '7px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 500
                }}
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes mr-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes mr-shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
      `}</style>
    </div>
  )
}