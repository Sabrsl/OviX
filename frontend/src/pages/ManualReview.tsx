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

// ---------- Design tokens (matches revision-liens.html) ----------
const T = {
  bgPrimary: '#0a0a0b',
  bgSecondary: '#111113',
  bgCard: '#161618',
  bgCardHover: '#1c1c1f',
  border: '#262629',
  borderSubtle: 'rgba(255,255,255,0.06)',
  textPrimary: '#f2f2f3',
  textSecondary: '#a3a3a8',
  textMuted: '#68686e',
  cyan: '#22d3ee',
  green: '#10b981',
  yellow: '#eab308',
  red: '#ef4444',
  purple: '#a78bfa',
  fontDisplay: "'Space Grotesk', sans-serif",
  fontBody: "'Inter', sans-serif",
  fontMono: "'IBM Plex Mono', monospace",
}

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
  pending: { label: 'En attente', color: T.yellow, icon: Clock },
  reviewed: { label: 'Révisé', color: T.cyan, icon: AlertTriangle },
  approved: { label: 'Approuvé', color: T.green, icon: CheckCircle },
  rejected: { label: 'Rejeté', color: T.red, icon: XCircle }
}

const filterLabels: Record<FilterKey, string> = {
  all: 'Tous',
  pending: 'En attente',
  approved: 'Approuvés',
  rejected: 'Rejetés'
}

const filterAccent: Record<FilterKey, string> = {
  all: T.cyan,
  pending: T.yellow,
  approved: T.green,
  rejected: T.red
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
    <div style={{
      padding: '28px 32px 64px',
      maxWidth: '920px',
      margin: '0 auto',
      fontFamily: T.fontBody,
      color: T.textPrimary,
      boxSizing: 'border-box',
      overflowX: 'hidden',
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      gap: '18px'
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '20px',
        padding: '20px 24px',
        borderRadius: '12px',
        border: `1px solid ${T.borderSubtle}`,
        background: `linear-gradient(to right, ${T.bgSecondary}, rgba(17,17,19,0.4))`,
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: '1 1 260px' }}>
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '8px',
            backgroundColor: `${T.cyan}20`,
            border: `1px solid ${T.cyan}40`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            <Link2 style={{ width: '17px', height: '17px', color: T.cyan }} />
          </div>
          <div>
            <h1 style={{
              fontFamily: T.fontDisplay,
              fontSize: '19px',
              fontWeight: 600,
              letterSpacing: '-0.01em',
              color: T.textPrimary,
              margin: '0 0 4px',
              lineHeight: 1.3
            }}>
              Liens nécessitant révision manuelle
            </h1>
            <p style={{ margin: 0, fontSize: '12.5px', color: T.textMuted }}>
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
              padding: '8px 14px',
              backgroundColor: 'transparent',
              color: T.textSecondary,
              border: `1px solid ${T.border}`,
              borderRadius: '7px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 500,
              fontFamily: T.fontBody,
              transition: 'background-color 0.15s, color 0.15s, border-color 0.15s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.04)'
              e.currentTarget.style.color = T.textPrimary
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
              e.currentTarget.style.color = T.textSecondary
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
              padding: '8px 14px',
              backgroundColor: 'rgba(255,255,255,0.05)',
              color: T.textPrimary,
              border: `1px solid ${T.border}`,
              borderRadius: '7px',
              cursor: loading ? 'default' : 'pointer',
              fontSize: '12px',
              fontWeight: 500,
              fontFamily: T.fontBody,
              opacity: loading ? 0.55 : 1,
              transition: 'background-color 0.15s'
            }}
            onMouseEnter={(e) => { if (!loading) e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.08)' }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)' }}
          >
            <RefreshCw style={{ width: '13px', height: '13px', animation: loading ? 'mr-spin 0.9s linear infinite' : 'none' }} />
            Actualiser
          </button>
        </div>
      </div>

      {/* Filter pills */}
      <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '2px' }}>
        {(Object.keys(filterLabels) as FilterKey[]).map((key) => {
          const isActive = filter === key
          const accent = filterAccent[key]
          return (
            <button
              key={key}
              onClick={() => setFilter(key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '7px',
                padding: '8px 14px',
                borderRadius: '999px',
                border: isActive ? `1px solid ${accent}59` : `1px solid ${T.border}`,
                backgroundColor: isActive ? `${accent}1a` : T.bgCard,
                color: isActive ? accent : T.textSecondary,
                fontSize: '12px',
                fontWeight: 500,
                fontFamily: T.fontBody,
                whiteSpace: 'nowrap',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => { if (!isActive) { e.currentTarget.style.borderColor = '#3a3a3e'; e.currentTarget.style.color = T.textPrimary } }}
              onMouseLeave={(e) => { if (!isActive) { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.textSecondary } }}
            >
              {filterLabels[key]}
              <span style={{
                fontFamily: T.fontMono,
                fontSize: '10.5px',
                padding: '1px 6px',
                borderRadius: '999px',
                backgroundColor: isActive ? accent : 'rgba(255,255,255,0.06)',
                color: isActive ? T.bgPrimary : T.textMuted,
                fontWeight: isActive ? 700 : 400,
                opacity: isActive ? 0.9 : 1
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
          backgroundColor: `${T.red}14`,
          border: `1px solid ${T.red}40`,
          borderRadius: '8px',
          color: T.red,
          fontSize: '12.5px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <XCircle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          {actionError}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {[0, 1, 2].map((i) => (
            <div key={i} style={{
              padding: '18px',
              backgroundColor: T.bgCard,
              border: `1px solid ${T.border}`,
              borderRadius: '10px',
              overflow: 'hidden',
              position: 'relative'
            }}>
              <div style={{ height: '13px', width: '45%', backgroundColor: T.border, borderRadius: '4px', marginBottom: '10px' }} />
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
          backgroundColor: `${T.red}14`,
          border: `1px solid ${T.red}40`,
          borderRadius: '10px',
          color: T.red
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
                backgroundColor: T.yellow,
                color: T.bgPrimary,
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 600,
                fontFamily: T.fontBody
              }}
            >
              Debug
            </button>
            <button
              onClick={handleRefresh}
              style={{
                padding: '7px 13px',
                backgroundColor: 'transparent',
                color: T.red,
                border: `1px solid ${T.red}59`,
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 600,
                fontFamily: T.fontBody
              }}
            >
              Réessayer
            </button>
          </div>
        </div>
      ) : filteredItems.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '48px 20px',
          color: T.textMuted,
          fontSize: '12.5px',
          border: `1px dashed ${T.border}`,
          borderRadius: '10px'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            margin: '0 auto 14px',
            borderRadius: '10px',
            backgroundColor: T.bgCard,
            border: `1px solid ${T.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Inbox style={{ width: '19px', height: '19px', color: T.textMuted }} />
          </div>
          <div style={{ marginBottom: '6px', fontSize: '13.5px', color: T.textSecondary, fontWeight: 500 }}>
            Aucun lien nécessitant révision manuelle
          </div>
          <div style={{ fontSize: '11.5px', color: T.textMuted }}>
            Filtre actuel: {filterLabels[filter]} · Total: {items.length}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {filteredItems.map(item => {
            const config = statusConfig[item.status] || statusConfig.pending
            const StatusIcon = config.icon
            const isActing = actionLoadingId === item.id
            return (
              <div
                key={item.id}
                style={{
                  position: 'relative',
                  display: 'flex',
                  gap: '14px',
                  padding: '16px 18px 16px 20px',
                  backgroundColor: T.bgCard,
                  border: `1px solid ${T.border}`,
                  borderLeft: `3px solid ${config.color}`,
                  borderRadius: '10px',
                  cursor: 'pointer',
                  width: '100%',
                  maxWidth: '100%',
                  boxSizing: 'border-box',
                  overflow: 'hidden',
                  transition: 'background-color 0.15s ease'
                }}
                onClick={() => setSelectedItem(item)}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = T.bgCardHover }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = T.bgCard }}
              >
                <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flexWrap: 'wrap' }}>
                      <h3 style={{
                        fontSize: '13.5px',
                        fontWeight: 600,
                        color: T.textPrimary,
                        letterSpacing: '-0.005em',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '100%',
                        margin: 0
                      }}>
                        {item.article_title}
                      </h3>
                      {(item as any).isArticlePublished && (
                        <span style={{
                          padding: '2px 7px',
                          backgroundColor: `${T.green}18`,
                          color: T.green,
                          fontSize: '10px',
                          fontWeight: 600,
                          borderRadius: '4px',
                          border: `1px solid ${T.green}35`,
                          whiteSpace: 'nowrap'
                        }}>
                          Article publié
                        </span>
                      )}
                    </div>
                    <span style={{
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '10px',
                      fontWeight: 600,
                      padding: '3px 9px',
                      borderRadius: '999px',
                      letterSpacing: '0.02em',
                      backgroundColor: `${config.color}1f`,
                      color: config.color
                    }}>
                      <StatusIcon style={{ width: '12px', height: '12px' }} />
                      {config.label}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: T.fontMono, fontSize: '11.5px', minWidth: 0 }}>
                    <ExternalLink style={{ width: '12px', height: '12px', flexShrink: 0, color: T.textMuted }} />
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: T.cyan,
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

                  {item.context && (
                    <div style={{
                      padding: '10px 12px',
                      backgroundColor: T.bgPrimary,
                      border: '1px solid #232323',
                      borderRadius: '7px',
                      fontSize: '11.5px',
                      lineHeight: 1.5,
                      color: T.textSecondary,
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
                      color: T.green,
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

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: T.fontMono, fontSize: '10.5px', color: T.textMuted }}>
                    <Clock style={{ width: '11px', height: '11px' }} />
                    <span>Détecté: {new Date(item.detected_at).toLocaleString('fr-FR')}</span>
                  </div>
                </div>

                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  gap: '6px',
                  flexShrink: 0
                }}>
                  {item.status === 'pending' ? (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleApprove(item.id, item.article_title, item.url)
                        }}
                        disabled={isActing}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '5px',
                          padding: '6px 12px',
                          minWidth: '92px',
                          backgroundColor: 'transparent',
                          color: T.green,
                          border: `1px solid ${T.green}4d`,
                          borderRadius: '6px',
                          cursor: isActing ? 'default' : 'pointer',
                          fontSize: '11px',
                          fontWeight: 500,
                          fontFamily: T.fontBody,
                          opacity: isActing ? 0.65 : 1,
                          transition: 'background-color 0.15s ease, border-color 0.15s ease'
                        }}
                        onMouseEnter={(e) => { if (!isActing) e.currentTarget.style.backgroundColor = `${T.green}1a` }}
                        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
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
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '5px',
                          padding: '6px 12px',
                          minWidth: '92px',
                          backgroundColor: 'transparent',
                          color: T.red,
                          border: `1px solid ${T.red}4d`,
                          borderRadius: '6px',
                          cursor: isActing ? 'default' : 'pointer',
                          fontSize: '11px',
                          fontWeight: 500,
                          fontFamily: T.fontBody,
                          opacity: isActing ? 0.65 : 1,
                          transition: 'background-color 0.15s ease, border-color 0.15s ease'
                        }}
                        onMouseEnter={(e) => { if (!isActing) e.currentTarget.style.backgroundColor = `${T.red}1a` }}
                        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
                      >
                        {isActing ? (
                          <RefreshCw style={{ width: '12px', height: '12px', animation: 'mr-spin 0.9s linear infinite' }} />
                        ) : (
                          <XCircle style={{ width: '12px', height: '12px' }} />
                        )}
                        Rejeter
                      </button>
                    </>
                  ) : (
                    <span style={{ fontSize: '10.5px', color: T.textMuted, fontStyle: 'italic' }}>
                      Traité manuellement
                    </span>
                  )}
                </div>
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
              backgroundColor: T.bgCard,
              border: `1px solid ${T.border}`,
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
              <h2 style={{ fontFamily: T.fontDisplay, fontSize: '15px', fontWeight: 600, color: T.textPrimary, lineHeight: 1.4, margin: 0 }}>
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
                    backgroundColor: `${config.color}1f`,
                    border: `1px solid ${config.color}59`,
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
              <label style={{ fontSize: '11px', color: T.textMuted, display: 'block', marginBottom: '4px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                URL
              </label>
              <a
                href={selectedItem.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: T.cyan, textDecoration: 'none', fontFamily: T.fontMono, fontSize: '12.5px', wordBreak: 'break-all' }}
              >
                {selectedItem.url}
              </a>
            </div>
            {selectedItem.context && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '11px', color: T.textMuted, display: 'block', marginBottom: '4px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  Contexte
                </label>
                <div style={{ padding: '11px', backgroundColor: T.bgPrimary, border: '1px solid #232323', borderRadius: '7px', fontSize: '12.5px', lineHeight: 1.55, color: T.textSecondary }}>
                  {selectedItem.context}
                </div>
              </div>
            )}
            {selectedItem.suggested_replacement && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '11px', color: T.textMuted, display: 'block', marginBottom: '4px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                  Remplacement suggéré
                </label>
                <div style={{ padding: '11px', backgroundColor: T.bgPrimary, border: `1px solid ${T.green}25`, borderRadius: '7px', fontSize: '12.5px', lineHeight: 1.55, color: T.green }}>
                  {selectedItem.suggested_replacement}
                </div>
              </div>
            )}
            <div style={{ marginBottom: '14px', fontFamily: T.fontMono, fontSize: '11px', color: T.textMuted, display: 'flex', alignItems: 'center', gap: '6px' }}>
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
                      backgroundColor: 'transparent',
                      color: T.green,
                      border: `1px solid ${T.green}4d`,
                      borderRadius: '7px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: 600,
                      fontFamily: T.fontBody,
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
                      backgroundColor: 'transparent',
                      color: T.red,
                      border: `1px solid ${T.red}4d`,
                      borderRadius: '7px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontWeight: 600,
                      fontFamily: T.fontBody,
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
                  backgroundColor: 'rgba(255,255,255,0.05)',
                  color: T.textPrimary,
                  border: `1px solid ${T.border}`,
                  borderRadius: '7px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 500,
                  fontFamily: T.fontBody
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