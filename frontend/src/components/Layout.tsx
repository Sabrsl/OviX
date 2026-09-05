import { useState, useEffect, useMemo, useCallback } from 'react'
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
  X
} from 'lucide-react'
import { authApi } from '../api/auth.api'

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
    ],
  },
]

export default function Layout() {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [authStatus, setAuthStatus] = useState<any>(null)
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(() => localStorage.getItem('wp_auth_error') || null)
  const [authSuccess, setAuthSuccess] = useState<string | null>(null)
  const [killSwitchError, setKillSwitchError] = useState<string | null>(null)
  const location = useLocation()

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

  useEffect(() => {
    // Only show loading on initial load, not on navigation
    const isInitialLoad = authStatus === null
    fetchAuthStatus(isInitialLoad)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location])

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

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: '#0a0a0a' }}>
      {/* Sidebar */}
      <aside style={{ width: '240px', flexShrink: 0, backgroundColor: '#111111', borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column' }}>
        {/* Logo */}
        <div style={{ height: '56px', flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 20px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
            <div style={{
              width: '28px',
              height: '28px',
              backgroundColor: '#3b82f6',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 0 1px rgba(59, 130, 246, 0.3), 0 2px 8px rgba(59, 130, 246, 0.25)',
              flexShrink: 0
            }}>
              <Globe style={{ width: '17px', height: '17px', color: 'white' }} />
            </div>
            <span style={{ fontSize: '15px', fontWeight: 700, color: '#f5f5f5', letterSpacing: '0.02em' }}>OVIX</span>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '10px 10px', overflowY: 'auto' }}>
          {navigation.map((item) => {
            const Icon = item.icon
            const hasChildren = item.children && item.children.length > 0
            const isExpanded = expandedItems.has(item.name)
            const active = isActive(item.href || '') || isParentActive(item.children)

            return (
              <div key={item.name} style={{ marginBottom: '2px' }}>
                {item.href && !hasChildren ? (
                  <Link
                    to={item.href}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '7px 10px',
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
                    {active && (
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                      <Icon style={{ width: '14px', height: '14px', flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                    </div>
                  </Link>
                ) : (
                  <button
                    onClick={() => hasChildren && toggleExpanded(item.name)}
                    aria-expanded={isExpanded}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '7px 10px',
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
                    {active && (
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                      <Icon style={{ width: '14px', height: '14px', flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                    </div>
                    {hasChildren && (
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
                )}

                {hasChildren && (
                  <div style={{
                    display: 'grid',
                    gridTemplateRows: isExpanded ? '1fr' : '0fr',
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
        <div style={{ padding: '12px', flexShrink: 0, borderTop: '1px solid var(--border-subtle)' }}>
          <Link
            to="/settings/wikipedia"
            style={{ textDecoration: 'none' }}
          >
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '10px', 
              padding: '7px 10px', 
              backgroundColor: '#161616', 
              borderRadius: '7px',
              cursor: 'pointer',
              transition: 'background-color 0.15s ease'
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
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '11px', fontWeight: 500, color: '#f5f5f5' }}>Wikipédia</div>
                <div style={{ fontSize: '10.5px', color: wikiConnected && !authLoading ? '#10b981' : '#666666' }}>
                  {authLoading ? 'Chargement...' : (wikiConnected ? 'Opérationnel' : 'Inactif')}
                </div>
              </div>
            </div>
          </Link>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '3px 8px', backgroundColor: '#161616', borderRadius: '5px' }}>
              <span style={{ position: 'relative', display: 'flex', width: '5px', height: '5px', flexShrink: 0 }}>
                <span style={{
                  position: 'absolute',
                  inset: 0,
                  borderRadius: '50%',
                  backgroundColor: '#10b981',
                  opacity: 0.75,
                  animation: 'ovix-pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite'
                }} />
                <span style={{ position: 'relative', width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#10b981' }} />
              </span>
              <span style={{ fontSize: '10px', fontWeight: 500, color: '#f5f5f5' }}>Opérationnel</span>
            </div>

            {/* Kill Switch Status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '3px 8px', backgroundColor: '#161616', borderRadius: '5px' }}>
              <Shield style={{ width: '11px', height: '11px', color: '#666666', flexShrink: 0 }} />
              <span style={{ fontSize: '10px', fontWeight: 500, color: '#666666' }}>Inactif</span>
            </div>
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