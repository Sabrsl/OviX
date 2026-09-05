import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Clock, FileText, User } from 'lucide-react'

interface Contribution {
  page_id: number
  revision_id: number
  title: string
  namespace: number
  timestamp: string
  comment: string
  retrieved_at: string
}

export default function UserContributions() {
  const navigate = useNavigate()
  const [contributions, setContributions] = useState<Contribution[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [username, setUsername] = useState('')

  useEffect(() => {
    // Get connected user from localStorage or API
    const fetchConnectedUser = async () => {
      try {
        const response = await fetch('/api/auth/user')
        if (response.ok) {
          const data = await response.json()
          setUsername(data.username)
          fetchContributions(data.username)
        }
      } catch (e) {
        setError('Impossible de récupérer l\'utilisateur connecté')
      }
    }
    fetchConnectedUser()
  }, [])

  const fetchContributions = async (user: string) => {
    if (!user) return
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`/api/articles/user-contributions/history?username=${encodeURIComponent(user)}&limit=50`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      if (data.success) {
        setContributions(data.contributions)
      } else {
        setError(data.error || 'Impossible de récupérer les contributions')
      }
    } catch (e) {
      setError(`Erreur de connexion: ${e}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <button
          onClick={() => navigate('/articles/retrieval')}
          style={{
            padding: '8px 12px',
            backgroundColor: '#1a1a1a',
            border: '1px solid #2a2a2a',
            borderRadius: '6px',
            color: '#a0a0a0',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <ArrowLeft style={{ width: '16px', height: '16px' }} />
          Retour
        </button>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#f5f5f5', margin: 0 }}>
          50 dernières contributions
        </h1>
      </div>

      <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '16px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <User style={{ width: '20px', height: '20px', color: '#3b82f6' }} />
          <span style={{ fontSize: '14px', color: '#a0a0a0' }}>
            {username || 'Chargement...'}
          </span>
        </div>
      </div>

      {error && (
        <div style={{
          color: '#ef4444',
          fontSize: '14px',
          padding: '12px',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          borderRadius: '6px',
          marginBottom: '24px'
        }}>
          {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '24px', color: '#a0a0a0' }}>
          Chargement...
        </div>
      )}

      {!loading && contributions.length > 0 && (
        <div style={{ backgroundColor: '#161616', border: '1px solid #2a2a2a', borderRadius: '8px', padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#666666', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
              {contributions.length} contribution(s) affichée(s)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {contributions.map((contrib, index) => (
              <div
                key={index}
                style={{
                  padding: '16px',
                  backgroundColor: '#1a1a1a',
                  border: '1px solid #2a2a2a',
                  borderRadius: '6px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileText style={{ width: '16px', height: '16px', color: '#3b82f6' }} />
                  <span style={{ fontSize: '16px', fontWeight: 500, color: '#f5f5f5' }}>
                    {contrib.title}
                  </span>
                </div>
                
                <div style={{ display: 'flex', gap: '24px', fontSize: '12px', color: '#a0a0a0' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock style={{ width: '14px', height: '14px' }} />
                    {contrib.timestamp}
                  </div>
                  <div>
                    Page ID: {contrib.page_id}
                  </div>
                  <div>
                    Revision ID: {contrib.revision_id}
                  </div>
                  <div>
                    Namespace: {contrib.namespace}
                  </div>
                </div>

                {contrib.comment && (
                  <div style={{ fontSize: '13px', color: '#666666', fontStyle: 'italic' }}>
                    {contrib.comment}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && contributions.length === 0 && username && !error && (
        <div style={{ textAlign: 'center', padding: '48px', color: '#666666' }}>
          Aucune contribution trouvée pour {username}
        </div>
      )}
    </div>
  )
}
