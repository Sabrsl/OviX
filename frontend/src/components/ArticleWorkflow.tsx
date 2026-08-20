/**
 * ArticleWorkflow - Main workflow component for article-by-article processing
 * Integrates status cards, history, and detail views with real-time updates
 */

import { useNavigate } from 'react-router-dom'
import { ArticleStatusCard } from './ArticleStatusCard'
import { ArticleHistory } from './ArticleHistory'

interface ArticleWorkflowProps {
  articles?: string[]
}

export function ArticleWorkflow({ articles = [] }: ArticleWorkflowProps) {
  const navigate = useNavigate()

  const handleDetailClick = (title: string) => {
    // Navigate to existing ArticleDetail page
    navigate(`/article/detail?title=${encodeURIComponent(title)}`)
  }

  const handleReanalyze = async (title: string) => {
    // Trigger re-analysis via API
    const { articlesApi } = await import('../api/articles.api')
    try {
      await articlesApi.analyzeArticle(title, 'regex')
      // Status will be updated via polling in ArticleStatusCard
    } catch (err) {
      console.error('Failed to reanalyze:', err)
    }
  }

  const handleIgnore = async (title: string) => {
    const { articlesApi } = await import('../api/articles.api')
    try {
      await articlesApi.ignoreArticle(title)
    } catch (err) {
      console.error('Failed to ignore:', err)
    }
  }

  const handlePublish = async (title: string) => {
    // Navigate to detail page for publication
    navigate(`/article/detail?title=${encodeURIComponent(title)}`)
  }

  return (
    <div style={{ padding: '24px', backgroundColor: '#0d0d0d', minHeight: '100vh' }}>
      <h1 style={{ 
        fontSize: '28px', 
        fontWeight: 600, 
        color: '#fff',
        marginBottom: '24px'
      }}>
        Article Workflow
      </h1>

      {/* Active Articles */}
      {articles.length > 0 && (
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{ 
            fontSize: '18px', 
            fontWeight: 600, 
            marginBottom: '16px',
            color: '#fff'
          }}>
            Active Articles ({articles.length})
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {articles.map((title) => (
              <ArticleStatusCard
                key={title}
                title={title}
                onDetailClick={handleDetailClick}
                onReanalyze={handleReanalyze}
                onIgnore={handleIgnore}
                onPublish={handlePublish}
              />
            ))}
          </div>
        </div>
      )}

      {/* History */}
      <div>
        <ArticleHistory onArticleClick={handleDetailClick} />
      </div>
    </div>
  )
}
