/**
 * ArticleStatusCard - Displays article status with visible progression
 * Shows analysis status, progress, and available actions
 */

import { useEffect, useState } from 'react'
import { articlesApi } from '../api/articles.api'
import type { ArticleStatus } from '../api/types'

interface ArticleStatusCardProps {
  title: string
  onDetailClick?: (title: string) => void
  onReanalyze?: (title: string) => void
  onIgnore?: (title: string) => void
  onPublish?: (title: string) => void
}

export function ArticleStatusCard({
  title,
  onDetailClick,
  onReanalyze,
  onIgnore,
  onPublish
}: ArticleStatusCardProps) {
  const [status, setStatus] = useState<ArticleStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStatus(true)
    // Poll for status updates every 3 seconds if analyzing
    const interval = setInterval(() => {
      if (status?.status === 'analyzing' || status?.status === 'pending') {
        loadStatus()
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [title, status?.status])

  const loadStatus = async (isInitial = false) => {
    try {
      if (isInitial) {
        setLoading(true)
      }
      const articleStatus = await articlesApi.getArticleStatus(title)
      setStatus(articleStatus)
      setError(null)
    } catch (err) {
      setError('Failed to load article status')
      console.error(err)
    } finally {
      if (isInitial) {
        setLoading(false)
      }
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'analyzing':
        return '⏳'
      case 'analyzed':
        return '✓'
      case 'published':
        return '✓'
      case 'rejected':
        return '✗'
      case 'ignored':
        return '⊘'
      case 'error':
        return '✗'
      case 'pending':
        return '○'
      default:
        return '○'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'analyzing':
        return '#3b82f6'
      case 'analyzed':
        return '#10b981'
      case 'published':
        return '#10b981'
      case 'rejected':
        return '#ef4444'
      case 'ignored':
        return '#6b7280'
      case 'error':
        return '#ef4444'
      case 'pending':
        return '#f59e0b'
      default:
        return '#6b7280'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'analyzing':
        return 'Analysis in progress'
      case 'analyzed':
        return 'Analysis completed'
      case 'published':
        return 'Published'
      case 'rejected':
        return 'Rejected'
      case 'ignored':
        return 'Ignored'
      case 'error':
        return 'Error'
      case 'pending':
        return 'Pending'
      default:
        return 'Unknown'
    }
  }

  if (loading && !status) {
    return (
      <div style={{ 
        border: '1px solid #2a2a2a', 
        borderRadius: '8px', 
        padding: '16px',
        backgroundColor: '#1a1a1a'
      }}>
        <div style={{ color: '#888' }}>Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ 
        border: '1px solid #ef4444', 
        borderRadius: '8px', 
        padding: '16px',
        backgroundColor: '#1a1a1a'
      }}>
        <div style={{ color: '#ef4444' }}>{error}</div>
      </div>
    )
  }

  const statusColor = getStatusColor(status?.status || 'pending')

  return (
    <div style={{
      border: '1px solid #2a2a2a',
      borderRadius: '8px',
      padding: '16px',
      backgroundColor: '#1a1a1a',
      marginBottom: '12px'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '20px' }}>{getStatusIcon(status?.status || 'pending')}</span>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>{title}</h3>
        </div>
        <div style={{ 
          color: statusColor,
          fontSize: '14px',
          fontWeight: 500
        }}>
          {getStatusText(status?.status || 'pending')}
        </div>
      </div>

      {/* Progress for analyzing articles */}
      {status?.status === 'analyzing' && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{
            height: '4px',
            backgroundColor: '#2a2a2a',
            borderRadius: '2px',
            overflow: 'hidden',
            marginBottom: '8px'
          }}>
            <div style={{
              height: '100%',
              backgroundColor: statusColor,
              width: `${status.progress || 0}%`,
              transition: 'width 0.3s ease'
            }} />
          </div>
          <div style={{ fontSize: '12px', color: '#888' }}>
            Progress: {Math.round(status.progress || 0)}% - {status.current_step || 'Analyzing...'}
          </div>
          {status.elapsed_time_seconds && (
            <div style={{ fontSize: '12px', color: '#666' }}>
              Temps écoulé: {Math.floor(status.elapsed_time_seconds / 60)}:{String(Math.floor(status.elapsed_time_seconds % 60)).padStart(2, '0')}
            </div>
          )}
          {status.analyzers_status && Object.keys(status.analyzers_status).length > 0 && (
            <div style={{ marginTop: '8px', fontSize: '11px', color: '#666' }}>
              <div style={{ marginBottom: '4px' }}>Analyzers:</div>
              {Object.entries(status.analyzers_status).map(([analyzer, status]) => (
                <div key={analyzer} style={{ marginLeft: '8px' }}>
                  {status === 'completed' ? '✓' : status === 'running' ? '⏳' : '○'} {analyzer}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Analysis results */}
      {status?.status === 'analyzed' && status.changes_count !== undefined && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '14px', color: '#10b981', marginBottom: '4px' }}>
            {status.changes_count} problems detected
          </div>
          {status.summary && (
            <div style={{ fontSize: '12px', color: '#888' }}>
              {status.summary}
            </div>
          )}
        </div>
      )}

      {/* Published info */}
      {status?.status === 'published' && status.revision_id && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '14px', color: '#10b981', marginBottom: '4px' }}>
            Published successfully
          </div>
          <div style={{ fontSize: '12px', color: '#888' }}>
            Revision: {status.revision_id}
          </div>
        </div>
      )}

      {/* Error message */}
      {status?.status === 'error' && (
        <div style={{ marginBottom: '12px', color: '#ef4444', fontSize: '14px' }}>
          Analysis failed
        </div>
      )}

      {/* Actions */}
      <div style={{ 
        display: 'flex', 
        gap: '8px', 
        flexWrap: 'wrap',
        borderTop: '1px solid #2a2a2a',
        paddingTop: '12px'
      }}>
        {status?.status === 'analyzed' && (
          <>
            <button
              onClick={() => onDetailClick?.(title)}
              style={{
                padding: '6px 12px',
                backgroundColor: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              View Details
            </button>
            <button
              onClick={() => onReanalyze?.(title)}
              style={{
                padding: '6px 12px',
                backgroundColor: '#2a2a2a',
                color: 'white',
                border: '1px solid #444',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              Re-analyze
            </button>
            <button
              onClick={() => onPublish?.(title)}
              style={{
                padding: '6px 12px',
                backgroundColor: '#10b981',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              Publish
            </button>
            <button
              onClick={() => onIgnore?.(title)}
              style={{
                padding: '6px 12px',
                backgroundColor: '#2a2a2a',
                color: '#888',
                border: '1px solid #444',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              Ignore
            </button>
          </>
        )}

        {status?.status === 'published' && (
          <button
            onClick={() => onDetailClick?.(title)}
            style={{
              padding: '6px 12px',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            View Details
          </button>
        )}

        {status?.status === 'error' && (
          <>
            <button
              onClick={() => onReanalyze?.(title)}
              style={{
                padding: '6px 12px',
                backgroundColor: '#3b82f6',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              Retry
            </button>
            <button
              onClick={() => onIgnore?.(title)}
              style={{
                padding: '6px 12px',
                backgroundColor: '#2a2a2a',
                color: '#888',
                border: '1px solid #444',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px'
              }}
            >
              Ignore
            </button>
          </>
        )}

        {status?.status === 'pending' && (
          <button
            onClick={() => onReanalyze?.(title)}
            style={{
              padding: '6px 12px',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '13px'
            }}
          >
            Start Analysis
          </button>
        )}
      </div>
    </div>
  )
}
