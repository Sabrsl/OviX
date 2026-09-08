import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  FileText,
  Terminal,
  Settings,
  Globe,
  Shield,
  ShieldAlert,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  X,
  Menu,
  Pin
} from 'lucide-react'
import { authApi } from '../api/auth.api'
import { systemApi } from '../api/system.api'
import Tooltip from './Tooltip'

const navigation = [
  {
    name: 'Dashboard',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    name: 'Analyse',
    icon: Search,
    children: [
      { name: 'Récupération d\'articles', href: '/articles/retrieval' },
      { name: 'File d\'analyse', href: '/articles/to-analyze' },
      { name: 'Historique d\'analyse', href: '/analysis/history' },
      { name: 'Révision manuelle', href: '/manual-review' },
      { name: 'Workflow', href: '/analysis/workflow' },
      { name: 'Liens morts publiés', href: '/published-dead-links' },
      { name: 'Scheduler', href: '/articles/scheduler' },
    ],
  },
  {
    name: 'Publication',
    icon: FileText,
    children: [
      { name: 'Prêt à publier', href: '/articles/ready-to-publish' },
      { name: 'En attente', href: '/publication/pending' },
      { name: 'Historique', href: '/publication/history' },
    ],
  },
  {
    name: 'System',
    icon: Terminal,
    children: [
      { name: 'Logs', href: '/system/logs' },
      { name: 'Scheduler', href: '/system/scheduler' },
      { name: 'Kill Switch', href: '/system/kill-switch' },
    ],
  },
  {
    name: 'Paramètres',
    icon: Settings,
    children: [
      { name: 'Wikipedia', href: '/settings/wikipedia' },
      { name: 'Général', href: '/settings' },
      { name: 'Gestion des domaines', href: '/settings/domains' },
    ],
  },
]

const LS_SIDEBAR_COLLAPSED = 'ovix_sidebar_collapsed'
const LS_SIDEBAR_PINNED = 'ovix_sidebar_pinned'

function readBoolPref(key: string, fallback: boolean): boolean {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : raw === 'true'
  } catch {
    return fallback
  }
}

function writeBoolPref(key: string, value: boolean) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(key, String(value))
  } catch {
    // ignore storage errors (private mode, quota, etc.)
  }
}

export default function Layout() {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [authStatus, setAuthStatus] = useState<any>(null)
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(() => localStorage.getItem('wp_auth_error') || null)
  const [authSuccess, setAuthSuccess] = useState<string | null>(null)
  const [killSwitchError, setKillSwitchError] = useState<string | null>(null)
  const [killSwitchStatus, setKillSwitchStatus] = useState<any>(null)
  const [killSwitchLoading, setKillSwitchLoading] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => readBoolPref(LS_SIDEBAR_COLLAPSED, false))
  const [sidebarPinned, setSidebarPinned] = useState(() => readBoolPref(LS_SIDEBAR_PINNED, false))
  const [sidebarHovered, setSidebarHovered] = useState(false)
  const hoverCloseTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const location = useLocation()

  // Sidebar is visually "open" (full width, labels + children visible) when:
  // pinned, or explicitly expanded, or temporarily hovered while collapsed.
  const sidebarOpen = sidebarPinned || !sidebarCollapsed || sidebarHovered

  const fetchAuthStatus = async (showLoading = false) => {
    try {
      if (showLoading) {
        setAuthLoading(true)
      }
      const status = await authApi.getStatus()
      setAuthStatus(status)
      // Only hide error banner if user is now authenticated
      if (status.authenticated) {
        setAuthError(null)
        localStorage.removeItem('wp_auth_error')
      }
    } catch (err) {
      // On error, assume not authenticated but don't block UI
      setAuthStatus({ authenticated: false })
      // Show error banner if fetch fails (likely auth issue)
      setAuthError('Session Wikipédia expirée. Veuillez vous reconnecter.')
      localStorage.setItem('wp_auth_error', 'Session Wikipédia expirée. Veuillez vous reconnecter.')
    } finally {
      setAuthLoading(false)
    }
  }

  const fetchKillSwitchStatus = async () => {
    try {
      setKillSwitchLoading(true)
      const status = await systemApi.getKillSwitchStatus()
      setKillSwitchStatus(status)
    } catch (err) {
      console.error('Failed to fetch kill switch status:', err)
      // Don't block UI on error, just set default state
      setKillSwitchStatus({ enabled: false })
    } finally {
      setKillSwitchLoading(false)
    }
  }

  useEffect(() => {
    // Only show loading on initial load, not on navigation
    const isInitialLoad = authStatus === null
    fetchAuthStatus(isInitialLoad)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location])

  // Fetch kill switch status periodically
  useEffect(() => {
    fetchKillSwitchStatus()
    const interval = setInterval(fetchKillSwitchStatus, 3600000) // Poll every 1 hour
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Watch for auth status changes to show success message only on actual login
  useEffect(() => {
    if (authStatus?.authenticated && !authLoading) {
      // Only show success message if we haven't shown it yet in this session
      const hasShown = localStorage.getItem('wp_success_shown') === 'true'
      if (!hasShown) {
        setAuthSuccess('Connexion Wikipédia réussie !')
        localStorage.setItem('wp_success_shown', 'true')
        // Hide success message after 5 seconds
        setTimeout(() => setAuthSuccess(null), 5000)
      }
    } else if (!authStatus?.authenticated && !authLoading) {
      // User disconnected, reset the tracking so message can show again on next login
      localStorage.removeItem('wp_success_shown')
    }
  }, [authStatus, authLoading])

  // Reset tracking on page load if not authenticated (handles reload scenario)
  useEffect(() => {
    if (!authStatus?.authenticated && !authLoading) {
      localStorage.removeItem('wp_success_shown')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Listen for auth expiration events from 401 responses
  useEffect(() => {
    const onAuthExpired = () => {
      setAuthError('Session Wikipédia expirée. Veuillez vous reconnecter.')
      localStorage.setItem('wp_auth_error', 'Session Wikipédia expirée. Veuillez vous reconnecter.')
      setAuthSuccess(null) // Clear success message if showing
      fetchAuthStatus()
      // Remove auto-hide - banner should stay until user reconnects
    }
    window.addEventListener('auth:expired', onAuthExpired)

    // Listen for auth success events from login page
    const onAuthSuccess = () => {
      fetchAuthStatus()
    }
    window.addEventListener('auth:success', onAuthSuccess)

    // Listen for kill switch errors from backend
    const onKillSwitchError = (event: CustomEvent) => {
      setKillSwitchError(event.detail.message || 'Erreur de sécurité du kill switch')
    }
    window.addEventListener('kill-switch:error', onKillSwitchError as EventListener)

    return () => {
      window.removeEventListener('auth:expired', onAuthExpired)
      window.removeEventListener('auth:success', onAuthSuccess)
      window.removeEventListener('kill-switch:error', onKillSwitchError as EventListener)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persist sidebar preferences
  useEffect(() => {
    writeBoolPref(LS_SIDEBAR_COLLAPSED, sidebarCollapsed)
  }, [sidebarCollapsed])

  useEffect(() => {
    writeBoolPref(LS_SIDEBAR_PINNED, sidebarPinned)
  }, [sidebarPinned])

  // Clear any pending hover-close timeout on unmount
  useEffect(() => {
    return () => {
      if (hoverCloseTimeout.current) clearTimeout(hoverCloseTimeout.current)
    }
  }, [])

  const handleSidebarMouseEnter = useCallback(() => {
    if (hoverCloseTimeout.current) {
      clearTimeout(hoverCloseTimeout.current)
      hoverCloseTimeout.current = null
    }
    if (sidebarCollapsed && !sidebarPinned) {
      setSidebarHovered(true)
    }
  }, [sidebarCollapsed, sidebarPinned])

  const handleSidebarMouseLeave = useCallback(() => {
    // Small delay avoids flicker when the cursor briefly crosses the edge
    hoverCloseTimeout.current = setTimeout(() => {
      setSidebarHovered(false)
    }, 120)
  }, [])

  const togglePinned = useCallback(() => {
    setSidebarPinned((prev) => {
      const next = !prev
      // Toggling should also drive the collapsed flag: pinned = fully open, unpinned = rail mode.
      setSidebarCollapsed(next ? false : true)
      setSidebarHovered(false)
      return next
    })
  }, [])

  const toggleExpanded = useCallback((name: string) => {
    setExpandedItems(prev => {
      const newExpanded = new Set(prev)
      if (newExpanded.has(name)) {
        newExpanded.delete(name)
      } else {
        newExpanded.add(name)
      }
      return newExpanded
    })
  }, [])

  const isActive = (href: string) => {
    return location.pathname === href
  }

  const isParentActive = (children?: { href: string }[]) => {
    if (!children) return false
    return children.some(child => location.pathname === child.href)
  }

  // Auto-expand the section containing the active route, so the current page
  // is never hidden behind a collapsed menu after a refresh or deep link.
  useEffect(() => {
    const parent = navigation.find(item => isParentActive(item.children))
    if (parent) {
      setExpandedItems(prev => (prev.has(parent.name) ? prev : new Set(prev).add(parent.name)))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  const currentPageName = useMemo(() => {
    return navigation.find(item =>
      item.href === location.pathname ||
      item.children?.some(child => child.href === location.pathname)
    )?.name || 'Dashboard'
  }, [location.pathname])

  const wikiConnected = Boolean(authStatus?.authenticated)
  const wikiDotColor = authLoading ? '#666666' : (wikiConnected ? '#10b981' : '#ef4444')

  // Visually collapsed = rail mode (icons only), used for layout decisions below.
  const isRailMode = sidebarCollapsed && !sidebarOpen

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: '#0a0a0a' }}>
      {/* Sidebar */}
      <aside
        style={{
          width: sidebarOpen ? '240px' : '60px',
          flexShrink: 0,
          backgroundColor: '#111111',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.2s ease-in-out',
          position: 'relative',
          zIndex: 10
        }}
        onMouseEnter={handleSidebarMouseEnter}
        onMouseLeave={handleSidebarMouseLeave}
      >
        {/* Toggle Sidebar Button */}
        <Tooltip content={sidebarPinned ? 'Réduire le menu' : 'Fixer le menu ouvert'} position="right">
          <button
            onClick={togglePinned}
            aria-pressed={sidebarPinned}
            aria-label={sidebarPinned ? 'Réduire le menu' : 'Fixer le menu ouvert'}
            style={{
              position: 'absolute',
              top: '60px',
              right: '-10px',
              width: '18px',
              height: '18px',
              backgroundColor: sidebarPinned ? '#3b82f6' : '#161616',
              border: sidebarPinned ? '1px solid #3b82f6' : '1px solid #2a2a2a',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              zIndex: 20,
              transition: 'all 0.2s ease',
              color: sidebarPinned ? '#ffffff' : '#a0a0a0'
            }}
            onMouseEnter={(e) => {
              if (!sidebarPinned) {
                e.currentTarget.style.backgroundColor = '#1a1a1a'
                e.currentTarget.style.color = '#f5f5f5'
              }
            }}
            onMouseLeave={(e) => {
              if (!sidebarPinned) {
                e.currentTarget.style.backgroundColor = '#161616'
                e.currentTarget.style.color = '#a0a0a0'
              }
            }}
          >
            {sidebarPinned ? <Pin style={{ width: '9px', height: '9px', fill: 'currentColor' }} /> : <Menu style={{ width: '10px', height: '10px' }} />}
          </button>
        </Tooltip>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: isRailMode ? '10px 8px' : '10px 10px', overflowY: 'auto', overflowX: 'hidden' }}>
          {navigation.map((item) => {
            const Icon = item.icon
            const hasChildren = item.children && item.children.length > 0
            const isExpanded = expandedItems.has(item.name)
            const active = isActive(item.href || '') || isParentActive(item.children)
            const showChildren = hasChildren && isExpanded && sidebarOpen

            return (
              <div key={item.name} style={{ marginBottom: '2px' }}>
                {item.href && !hasChildren ? (
                  <Tooltip content={isRailMode ? item.name : ''} position="right">
                    <Link
                      to={item.href}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: isRailMode ? 'center' : 'space-between',
                        padding: isRailMode ? '8px' : '7px 10px',
                        fontSize: '13px',
                        fontWeight: 500,
                        borderRadius: '6px',
                        transition: 'background-color 0.15s, color 0.15s',
                        backgroundColor: active ? '#161616' : 'transparent',
                        color: active ? '#3b82f6' : '#a0a0a0',
                        textDecoration: 'none',
                        cursor: 'pointer',
                        position: 'relative',
                        boxSizing: 'border-box'
                      }}
                      onMouseEnter={(e) => {
                        if (!active) {
                          e.currentTarget.style.backgroundColor = 'rgba(22, 22, 22, 0.5)'
                          e.currentTarget.style.color = '#f5f5f5'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!active) {
                          e.currentTarget.style.backgroundColor = 'transparent'
                          e.currentTarget.style.color = '#a0a0a0'
                        }
                      }}
                    >
                      {active && !isRailMode && (
                        <span style={{
                          position: 'absolute',
                          left: '-10px',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          width: '3px',
                          height: '16px',
                          borderRadius: '0 3px 3px 0',
                          backgroundColor: '#3b82f6'
                        }} />
                      )}
                      <div style={{ display: 'flex', alignItems: 'center', gap: isRailMode ? '0' : '10px', minWidth: 0 }}>
                        <Icon style={{ width: '14px', height: '14px', flexShrink: 0 }} />
                        {sidebarOpen && (
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                        )}
                      </div>
                    </Link>
                  </Tooltip>
                ) : (
                  <Tooltip content={isRailMode ? item.name : ''} position="right">
                    <button
                      onClick={() => hasChildren && sidebarOpen && toggleExpanded(item.name)}
                      aria-expanded={isExpanded}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: isRailMode ? 'center' : 'space-between',
                        padding: isRailMode ? '8px' : '7px 10px',
                        fontSize: '13px',
                        fontWeight: 500,
                        borderRadius: '6px',
                        transition: 'background-color 0.15s, color 0.15s',
                        backgroundColor: active ? '#161616' : 'transparent',
                        color: active ? '#3b82f6' : '#a0a0a0',
                        border: 'none',
                        cursor: 'pointer',
                        position: 'relative',
                        boxSizing: 'border-box'
                      }}
                      onMouseEnter={(e) => {
                        if (!active) {
                          e.currentTarget.style.backgroundColor = 'rgba(22, 22, 22, 0.5)'
                          e.currentTarget.style.color = '#f5f5f5'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!active) {
                          e.currentTarget.style.backgroundColor = 'transparent'
                          e.currentTarget.style.color = '#a0a0a0'
                        }
                      }}
                    >
                      {active && !isRailMode && (
                        <span style={{
                          position: 'absolute',
                          left: '-10px',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          width: '3px',
                          height: '16px',
                          borderRadius: '0 3px 3px 0',
                          backgroundColor: '#3b82f6'
                        }} />
                      )}
                      <div style={{ display: 'flex', alignItems: 'center', gap: isRailMode ? '0' : '10px', minWidth: 0 }}>
                        <Icon style={{ width: '14px', height: '14px', flexShrink: 0 }} />
                        {sidebarOpen && (
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                        )}
                      </div>
                      {hasChildren && sidebarOpen && (
                        <ChevronRight
                          style={{
                            width: '14px',
                            height: '14px',
                            flexShrink: 0,
                            transition: 'transform 0.2s',
                            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'
                          }}
                        />
                      )}
                    </button>
                  </Tooltip>
                )}

                {hasChildren && sidebarOpen && (
                  <div style={{
                    display: 'grid',
                    gridTemplateRows: showChildren ? '1fr' : '0fr',
                    transition: 'grid-template-rows 0.2s ease',
                  }}>
                    <div style={{ overflow: 'hidden' }}>
                      <div style={{
                        marginTop: '3px',
                        marginLeft: '19px',
                        paddingLeft: '10px',
                        borderLeft: '1px solid rgba(255, 255, 255, 0.06)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px'
                      }}>
                        {item.children!.map((child) => (
                          <Link
                            key={child.href}
                            to={child.href}
                            style={{
                              padding: '6px 10px',
                              fontSize: '12.5px',
                              borderRadius: '6px',
                              transition: 'background-color 0.15s, color 0.15s',
                              backgroundColor: isActive(child.href) ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                              color: isActive(child.href) ? '#3b82f6' : '#666666',
                              fontWeight: isActive(child.href) ? 500 : 400,
                              textDecoration: 'none',
                              display: 'block',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap'
                            }}
                            onMouseEnter={(e) => {
                              if (!isActive(child.href)) {
                                e.currentTarget.style.backgroundColor = 'rgba(22, 22, 22, 0.5)'
                                e.currentTarget.style.color = '#a0a0a0'
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (!isActive(child.href)) {
                                e.currentTarget.style.backgroundColor = 'transparent'
                                e.currentTarget.style.color = '#666666'
                              }
                            }}
                          >
                            {child.name}
                          </Link>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        {/* Wikipedia Status */}
        <div style={{ padding: isRailMode ? '12px 8px' : '12px', flexShrink: 0, borderTop: '1px solid var(--border-subtle)' }}>
          <Tooltip content={isRailMode ? (wikiConnected ? 'Wikipédia connecté' : 'Wikipédia déconnecté') : ''} position="right">
            <Link
              to="/settings/wikipedia"
              style={{ textDecoration: 'none' }}
            >
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: isRailMode ? '0' : '10px',
                padding: isRailMode ? '8px' : '7px 10px',
                backgroundColor: '#161616',
                borderRadius: '7px',
                cursor: 'pointer',
                transition: 'background-color 0.15s ease',
                justifyContent: isRailMode ? 'center' : 'flex-start'
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#1a1a1a'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#161616'}
            >
              <span style={{ position: 'relative', display: 'flex', width: '6px', height: '6px', flexShrink: 0 }}>
                {wikiConnected && !authLoading && (
                  <span style={{
                    position: 'absolute',
                    inset: 0,
                    borderRadius: '50%',
                    backgroundColor: wikiDotColor,
                    opacity: 0.75,
                    animation: 'ovix-pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite'
                  }} />
                )}
                <span style={{
                  position: 'relative',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: wikiDotColor
                }} />
              </span>
              {sidebarOpen && (
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '11px', fontWeight: 500, color: '#f5f5f5' }}>Wikipédia</div>
                  <div style={{ fontSize: '10.5px', color: wikiConnected && !authLoading ? '#10b981' : '#666666' }}>
                    {authLoading ? 'Chargement...' : (wikiConnected ? 'Connecté' : 'Déconnecté')}
                  </div>
                </div>
              )}
            </div>
            </Link>
          </Tooltip>
        </div>
      </aside>

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {/* Global Auth Error Banner */}
        {authError && (
          <div
            style={{
              padding: '10px 24px',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              borderBottom: '1px solid rgba(239, 68, 68, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexShrink: 0
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444', fontSize: '12.5px' }}>
              <AlertTriangle style={{ width: '15px', height: '15px', flexShrink: 0 }} />
              <span>{authError}</span>
            </div>
            <button
              onClick={() => {
                setAuthError(null)
                localStorage.removeItem('wp_auth_error')
              }}
              aria-label="Fermer"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '20px',
                height: '20px',
                background: 'none',
                border: 'none',
                color: '#ef4444',
                cursor: 'pointer',
                borderRadius: '4px',
                flexShrink: 0,
                transition: 'background-color 0.15s'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.15)' }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              <X style={{ width: '13px', height: '13px' }} />
            </button>
          </div>
        )}

        {/* Global Auth Success Banner */}
        {authSuccess && (
          <div
            style={{
              padding: '10px 24px',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderBottom: '1px solid rgba(16, 185, 129, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexShrink: 0
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', fontSize: '12.5px' }}>
              <CheckCircle style={{ width: '15px', height: '15px', flexShrink: 0 }} />
              <span>{authSuccess}</span>
            </div>
            <button
              onClick={() => setAuthSuccess(null)}
              aria-label="Fermer"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '20px',
                height: '20px',
                background: 'none',
                border: 'none',
                color: '#10b981',
                cursor: 'pointer',
                borderRadius: '4px',
                flexShrink: 0,
                transition: 'background-color 0.15s'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(16, 185, 129, 0.15)' }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              <X style={{ width: '13px', height: '13px' }} />
            </button>
          </div>
        )}

        {/* Global Kill Switch Error Banner */}
        {killSwitchError && (
          <div
            style={{
              padding: '10px 24px',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              borderBottom: '1px solid rgba(239, 68, 68, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexShrink: 0
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444', fontSize: '12.5px' }}>
              <ShieldAlert style={{ width: '15px', height: '15px', flexShrink: 0 }} />
              <span>{killSwitchError}</span>
            </div>
            <button
              onClick={() => setKillSwitchError(null)}
              aria-label="Fermer"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '20px',
                height: '20px',
                background: 'none',
                border: 'none',
                color: '#ef4444',
                cursor: 'pointer',
                borderRadius: '4px',
                flexShrink: 0,
                transition: 'background-color 0.15s'
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.15)' }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              <X style={{ width: '13px', height: '13px' }} />
            </button>
          </div>
        )}

        {/* Top Bar */}
        <header style={{ height: '56px', flexShrink: 0, backgroundColor: '#111111', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px', boxSizing: 'border-box' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', minWidth: 0 }}>
            <h1 style={{ fontSize: '15px', fontWeight: 600, color: '#f5f5f5', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentPageName}
            </h1>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
            {/* OVIX Status */}
            <Tooltip 
              content={killSwitchStatus?.enabled 
                ? "Système arrêté" 
                : "Système opérationnel"}
              position="bottom"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '3px 8px', backgroundColor: '#161616', borderRadius: '5px', cursor: 'help' }}>
                <span style={{ fontSize: '10px', fontWeight: 500, color: killSwitchStatus?.enabled ? '#666666' : '#10b981' }}>
                  {killSwitchLoading ? 'Chargement...' : (killSwitchStatus?.enabled ? 'Arrêté' : 'Opérationnel')}
                </span>
              </div>
            </Tooltip>

            {/* Kill Switch Status */}
            <Tooltip 
              content={killSwitchStatus?.enabled 
                ? "Arrêt d'urgence activé" 
                : "Arrêt d'urgence désactivé"}
              position="bottom"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '3px 8px', backgroundColor: '#161616', borderRadius: '5px', cursor: 'help' }}>
                <Shield style={{ width: '11px', height: '11px', color: killSwitchStatus?.enabled ? '#ef4444' : '#666666', flexShrink: 0 }} />
                <span style={{ fontSize: '10px', fontWeight: 500, color: killSwitchStatus?.enabled ? '#ef4444' : '#666666' }}>
                  {killSwitchLoading ? 'Chargement...' : (killSwitchStatus?.enabled ? 'Actif' : 'Inactif')}
                </span>
              </div>
            </Tooltip>
          </div>
        </header>

        {/* Page Content */}
        <main style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '16px 24px', boxSizing: 'border-box' }}>
          <Outlet />
        </main>
      </div>

      <style>{`
        @keyframes ovix-pulse {
          0%, 100% { opacity: 0.75; transform: scale(1); }
          50% { opacity: 0.2; transform: scale(1.6); }
        }
      `}</style>
    </div>
  )
}