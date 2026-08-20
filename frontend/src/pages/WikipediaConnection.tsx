import { useState, useEffect, useCallback, type CSSProperties, type FormEvent } from 'react'
import { Globe, Lock, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { authApi } from '../api/auth.api'

interface AuthStatus {
  authenticated: boolean
  username?: string
  lang?: string
}

const LANG_OPTIONS = [
  { value: 'fr', label: 'Français (fr)' },
  { value: 'en', label: 'English (en)' },
  { value: 'de', label: 'Deutsch (de)' },
  { value: 'es', label: 'Español (es)' },
  { value: 'it', label: 'Italiano (it)' },
] as const

const STORAGE_KEYS = {
  username: 'wp_username',
  lang: 'wp_lang',
  remember: 'wp_remember',
} as const

// ---- Styles centralisés (évite la répétition et facilite la maintenance) ----
const styles: Record<string, CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
    maxWidth: '360px',
    fontFamily: 'inherit',
  },
  title: {
    fontSize: '15px',
    fontWeight: 600,
    color: '#f5f5f5',
    letterSpacing: '-0.01em',
    margin: 0,
  },
  subtitle: {
    color: '#7a7a7a',
    fontSize: '11.5px',
    margin: '2px 0 0',
  },
  card: {
    backgroundColor: '#161616',
    border: '1px solid #2a2a2a',
    borderRadius: '8px',
    padding: '14px',
  },
  sectionLabel: {
    fontSize: '10px',
    fontWeight: 600,
    color: '#666666',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    margin: '0 0 12px',
  },
  fieldLabel: {
    display: 'block',
    fontSize: '11px',
    fontWeight: 500,
    color: '#7a7a7a',
    marginBottom: '5px',
    letterSpacing: '0.01em',
  },
  errorBox: {
    color: '#f87171',
    fontSize: '11px',
    padding: '8px 10px',
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    border: '1px solid rgba(239, 68, 68, 0.2)',
    borderRadius: '5px',
  },
}

const inputBaseStyle: CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  backgroundColor: '#0a0a0a',
  borderRadius: '5px',
  color: '#f5f5f5',
  fontSize: '12px',
  outline: 'none',
  transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
  boxSizing: 'border-box',
  border: '1px solid #2a2a2a',
}

function getInputStyle(isFocused: boolean): CSSProperties {
  return {
    ...inputBaseStyle,
    border: `1px solid ${isFocused ? '#3b82f6' : '#2a2a2a'}`,
    boxShadow: isFocused ? '0 0 0 3px rgba(59, 130, 246, 0.12)' : 'none',
  }
}

function getButtonStyle(variant: 'primary' | 'secondary', disabled: boolean): CSSProperties {
  const base: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: '8px 14px',
    borderRadius: '5px',
    fontSize: '12px',
    fontWeight: 500,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    transition: 'background-color 0.15s ease, border-color 0.15s ease',
    border: 'none',
  }

  if (variant === 'primary') {
    return { ...base, backgroundColor: '#2563eb', color: '#fff' }
  }
  return { ...base, backgroundColor: 'transparent', color: '#f5f5f5', border: '1px solid #333333' }
}

// ---- Sous-composants ----

function Spinner({ size = 12 }: { size?: number }) {
  return <Loader2 style={{ width: size, height: size, animation: 'spin 1s linear infinite' }} aria-hidden />
}

function StatusCard({ status }: { status: AuthStatus | null }) {
  const isAuthenticated = status?.authenticated ?? false

  return (
    <div
      style={{
        ...styles.card,
        padding: '12px 14px',
        border: `1px solid ${isAuthenticated ? 'rgba(16, 185, 129, 0.35)' : '#2a2a2a'}`,
      }}
      role="status"
      aria-live="polite"
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div
          style={{
            padding: '7px',
            backgroundColor: isAuthenticated ? 'rgba(16, 185, 129, 0.1)' : '#1c1c1c',
            borderRadius: '6px',
            display: 'flex',
            flexShrink: 0,
          }}
        >
          {isAuthenticated ? (
            <CheckCircle style={{ width: 14, height: 14, color: '#10b981' }} aria-hidden />
          ) : (
            <AlertCircle style={{ width: 14, height: 14, color: '#666666' }} aria-hidden />
          )}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ fontSize: '11.5px', fontWeight: 600, color: '#f5f5f5', margin: '0 0 3px' }}>
            Statut de la connexion
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <div
              style={{
                width: 5,
                height: 5,
                backgroundColor: isAuthenticated ? '#10b981' : '#666666',
                borderRadius: '50%',
              }}
            />
            <span style={{ fontSize: '11px', color: '#999999' }}>
              {isAuthenticated ? 'Connecté' : 'Déconnecté'}
            </span>
          </div>
          {isAuthenticated && status?.username && (
            <div style={{ fontSize: '11px', color: '#666666', marginTop: '4px' }}>
              <span style={{ color: '#7a7a7a' }}>Compte :</span> {status.username}
            </div>
          )}
          {isAuthenticated && status?.lang && (
            <div style={{ fontSize: '11px', color: '#666666' }}>
              <span style={{ color: '#7a7a7a' }}>Langue :</span> {status.lang}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---- Composant principal ----

export default function WikipediaConnection() {
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [loggingIn, setLoggingIn] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [lang, setLang] = useState('fr')
  const [remember, setRemember] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [focusedField, setFocusedField] = useState<string | null>(null)

  useEffect(() => {
    try {
      const savedUsername = localStorage.getItem(STORAGE_KEYS.username)
      const savedLang = localStorage.getItem(STORAGE_KEYS.lang)
      const savedRemember = localStorage.getItem(STORAGE_KEYS.remember)

      if (savedUsername) setUsername(savedUsername)
      if (savedLang) setLang(savedLang)
      if (savedRemember) setRemember(savedRemember === 'true')
    } catch {
      // localStorage indisponible (mode privé, quota, etc.) — on ignore silencieusement
    }
  }, [])

  // isRetry=true : appel silencieux déclenché après un premier échec 401/403 au montage.
  // On ne touche pas à `loading`/`error` tant qu'on n'est pas sûr que ce n'est pas
  // juste une histoire de cookie/session pas encore propagée côté client.
  const fetchStatus = useCallback(async (isRetry = false) => {
    if (!isRetry) setLoading(true)
    if (!isRetry) setError(null)
    try {
      const status = await authApi.getStatus()
      setAuthStatus(status)
      setError(null)
      if (status.username) setUsername(status.username)
      if (status.lang) setLang(status.lang)
      setLoading(false)
    } catch (err: any) {
      const statusCode = err?.response?.status ?? err?.status

      // Premier essai + 401/403 : ne montre rien, retente une fois après un court délai
      // au lieu d'afficher tout de suite "Déconnecté" / une erreur qui disparaît ensuite.
      if (!isRetry && (statusCode === 401 || statusCode === 403)) {
        setTimeout(() => fetchStatus(true), 800)
        return
      }

      setAuthStatus({ authenticated: false })
      // On n'affiche une erreur explicite que si ce n'est pas un simple 401/403
      // (dans ce cas, "Déconnecté" suffit et est correct, ce n'est pas une erreur).
      if (statusCode !== 401 && statusCode !== 403) {
        setError(err?.message || err?.userMessage || 'Erreur lors de la récupération du statut')
      }
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  // Se resynchronise automatiquement si un autre composant (ex: après connexion
  // ailleurs dans l'app) signale un changement d'état d'authentification.
  useEffect(() => {
    const handleAuthSuccess = () => fetchStatus()
    window.addEventListener('auth:success', handleAuthSuccess)
    return () => window.removeEventListener('auth:success', handleAuthSuccess)
  }, [fetchStatus])

  const persistCredentials = (shouldRemember: boolean) => {
    try {
      if (shouldRemember) {
        localStorage.setItem(STORAGE_KEYS.username, username)
        localStorage.setItem(STORAGE_KEYS.lang, lang)
        localStorage.setItem(STORAGE_KEYS.remember, 'true')
      } else {
        localStorage.removeItem(STORAGE_KEYS.username)
        localStorage.removeItem(STORAGE_KEYS.remember)
        localStorage.setItem(STORAGE_KEYS.lang, lang)
      }
    } catch {
      // silencieux — non bloquant pour le flux d'auth
    }
  }

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('Veuillez remplir tous les champs')
      return
    }

    setLoggingIn(true)
    setError(null)
    setSuccessMessage(null)
    try {
      const result = await authApi.login({ username: username.trim(), password, lang, remember })
      if (result.success && result.authenticated) {
        persistCredentials(remember)
        setPassword('')
        setSuccessMessage('Connexion réussie !')
        setTimeout(() => setSuccessMessage(null), 3000)
        await fetchStatus()
        // Notifie les autres composants (ex: Dashboard) qu'ils doivent se rafraîchir
        window.dispatchEvent(new CustomEvent('auth:success'))
      } else {
        setError(result.error || 'Échec de la connexion')
      }
    } catch (err: any) {
      setError(err?.message || err?.userMessage || 'Erreur lors de la connexion')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleLogout = async () => {
    if (!confirm('Êtes-vous sûr de vouloir vous déconnecter de Wikipédia ?')) return

    setLoggingIn(true)
    setError(null)
    try {
      await authApi.logout()
      try {
        localStorage.removeItem(STORAGE_KEYS.username)
        localStorage.removeItem(STORAGE_KEYS.remember)
      } catch {
        // silencieux
      }
      await fetchStatus()
    } catch (err: any) {
      setError(err?.message || err?.userMessage || 'Erreur lors de la déconnexion')
    } finally {
      setLoggingIn(false)
    }
  }

  if (loading) {
    return (
      <div style={styles.container}>
        <div>
          <h2 style={styles.title}>Connexion Wikipédia</h2>
          <p style={styles.subtitle}>Gérer la connexion à Wikipédia</p>
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '8px',
            padding: '28px',
            backgroundColor: '#161616',
            borderRadius: '8px',
            border: '1px solid #2a2a2a',
          }}
        >
          <Spinner size={13} />
          <span style={{ color: '#666666', fontSize: '11.5px' }}>Chargement...</span>
        </div>
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  const isAuthenticated = authStatus?.authenticated ?? false

  return (
    <div style={styles.container}>
      <div>
        <h2 style={styles.title}>Connexion Wikipédia</h2>
        <p style={styles.subtitle}>Gérer la connexion à Wikipédia</p>
      </div>

      <StatusCard status={authStatus} />

      {successMessage && (
        <div
          style={{
            color: '#10b981',
            fontSize: '11px',
            padding: '8px 10px',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '5px',
            marginBottom: '10px',
          }}
          role="status"
          aria-live="polite"
        >
          {successMessage}
        </div>
      )}

      {!isAuthenticated && (
        <div style={styles.card}>
          <h3 style={styles.sectionLabel}>Connexion</h3>
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }} noValidate>
            <div>
              <label htmlFor="wp-username" style={styles.fieldLabel}>
                Nom d'utilisateur Wikipédia
              </label>
              <input
                id="wp-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onFocus={() => setFocusedField('username')}
                onBlur={() => setFocusedField(null)}
                placeholder="Votre nom d'utilisateur"
                autoComplete="username"
                style={getInputStyle(focusedField === 'username')}
              />
            </div>

            <div>
              <label htmlFor="wp-password" style={styles.fieldLabel}>
                Mot de passe
              </label>
              <input
                id="wp-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setFocusedField('password')}
                onBlur={() => setFocusedField(null)}
                placeholder="Votre mot de passe"
                autoComplete="current-password"
                style={getInputStyle(focusedField === 'password')}
              />
            </div>

            <div>
              <label htmlFor="wp-lang" style={styles.fieldLabel}>
                Langue
              </label>
              <select
                id="wp-lang"
                value={lang}
                onChange={(e) => setLang(e.target.value)}
                onFocus={() => setFocusedField('lang')}
                onBlur={() => setFocusedField(null)}
                style={{ ...getInputStyle(focusedField === 'lang'), cursor: 'pointer' }}
              >
                {LANG_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <label
              htmlFor="remember"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '11px',
                color: '#999999',
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <input
                type="checkbox"
                id="remember"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                style={{ width: 12, height: 12, accentColor: '#3b82f6', cursor: 'pointer' }}
              />
              Se souvenir de mes identifiants
            </label>

            {error && (
              <div style={styles.errorBox} role="alert">
                {error}
              </div>
            )}

            <button type="submit" disabled={loggingIn} style={getButtonStyle('primary', loggingIn)}>
              {loggingIn ? <Spinner /> : <Globe style={{ width: 12, height: 12 }} aria-hidden />}
              {loggingIn ? 'Connexion...' : 'Se connecter'}
            </button>
          </form>
        </div>
      )}

      {isAuthenticated && (
        <div style={styles.card}>
          <h3 style={styles.sectionLabel}>Actions</h3>

          {error && (
            <div style={{ ...styles.errorBox, marginBottom: '10px' }} role="alert">
              {error}
            </div>
          )}

          <button onClick={handleLogout} disabled={loggingIn} style={getButtonStyle('secondary', loggingIn)}>
            {loggingIn ? <Spinner /> : <Lock style={{ width: 12, height: 12 }} aria-hidden />}
            {loggingIn ? 'Déconnexion...' : 'Se déconnecter'}
          </button>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}