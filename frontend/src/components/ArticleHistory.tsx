/**
 * ArticleHistory - Displays history of analyzed articles
 * Shows each article with its status and allows clicking for details
 */

import { useEffect, useState } from 'react'
import { articlesApi } from '../api/articles.api'
import { historyApi } from '../api/history.api'
import type { ArticleHistoryItem } from '../api/types'

interface ArticleHistoryProps {
  onArticleClick?: (title: string) => void
  limit?: number
}

export function ArticleHistory({ onArticleClick, limit = 50 }: ArticleHistoryProps) {
  const [history, setHistory] = useState<ArticleHistoryItem[]>([])
  const [publishedHistory, setPublishedHistory] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadHistory()
  }, [limit])

  const loadHistory = async () => {
    try {
      setLoading(true)
      const [historyData, publishedData] = await Promise.all([
        articlesApi.getArticleHistory(limit),
        historyApi.getPublishedHistory()
      ])
      // Sort by analysis date, most recent first
      const sortedHistory = historyData.sort((a: ArticleHistoryItem, b: ArticleHistoryItem) => {
        const dateA = new Date(a.analysis_date || 0).getTime()
        const dateB = new Date(b.analysis_date || 0).getTime()
        return dateB - dateA // Descending order (most recent first)
      })
      setHistory(sortedHistory)
      setPublishedHistory(publishedData)
      setError(null)
    } catch (err) {
      setError('Failed to load article history')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const getFinalStatus = (item: ArticleHistoryItem) => {
    // Use the status directly from backend (SQLite source of truth)
    const validStatuses = ['published', 'pending', 'rejected', 'ignored', 'error', 'analyzing', 'analyzed']
    if (validStatuses.includes(item.status)) {
      return item.status
    }

    // Default to pending if status is invalid
    return 'pending'
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
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
      case 'analyzing':
        return '◐'
      default:
        return '○'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
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
      case 'analyzing':
        return '#3b82f6'
      default:
        return '#6b7280'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'published':
        return 'Publié'
      case 'analyzed':
        return 'Analysé'
      case 'rejected':
        return 'Refusé'
      case 'ignored':
        return 'Ignoré'
      case 'error':
        return 'Erreur'
      case 'pending':
        return 'En attente'
      case 'analyzing':
        return 'Analyse en cours'
      default:
        return status
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A'
    const date = new Date(dateString)
    return date.toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <div style={{ padding: '16px', color: '#888' }}>
        Loading history...
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: '16px', color: '#ef4444' }}>
        {error}
      </div>
    )
  }

  if (history.length === 0) {
    return (
      <div style={{ padding: '16px', color: '#888' }}>
        No analyzed articles found
      </div>
    )
  }

  return (
    <div>
      <h2 style={{ 
        fontSize: '18px', 
        fontWeight: 600, 
        marginBottom: '16px',
        color: '#fff'
      }}>
        History ({history.length} articles)
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {history.map((item) => {
          const finalStatus = getFinalStatus(item)
          return (
            <div
              key={item.title}
              onClick={() => onArticleClick?.(item.title)}
              style={{
                padding: '12px 16px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #2a2a2a',
                borderRadius: '6px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#2a2a2a'
                e.currentTarget.style.borderColor = '#3b82f6'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#1a1a1a'
                e.currentTarget.style.borderColor = '#2a2a2a'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                <span style={{ fontSize: '18px' }}>
                  {getStatusIcon(finalStatus)}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: '14px',
                    fontWeight: 500,
                    color: '#fff',
                    marginBottom: '4px'
                  }}>
                    {item.title}
                  </div>
                  <div style={{ fontSize: '12px', color: '#888' }}>
                    {formatDate(item.analysis_date)}
                  </div>
                </div>
              </div>

              <div style={{ textAlign: 'right', marginLeft: '16px' }}>
                <div style={{
                  fontSize: '12px',
                  color: getStatusColor(finalStatus),
                  fontWeight: 500,
                  marginBottom: '4px'
                }}>
                  {getStatusLabel(finalStatus)}
                </div>
                {item.changes_count !== undefined && item.changes_count > 0 && (
                  <div style={{ fontSize: '12px', color: '#888' }}>
                    {item.changes_count} changes
                  </div>
                )}
                {item.published_revision_id && (
                  <div style={{ fontSize: '12px', color: '#10b981' }}>
                    Rev: {item.published_revision_id}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
