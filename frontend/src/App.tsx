import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AnalysisNew from './pages/AnalysisNew'
import AnalysisResults from './pages/AnalysisResults'
import AnalyzedHistory from './pages/AnalyzedHistory'
import ArticleDetail from './pages/ArticleDetail'
import ArticleWorkflowPage from './pages/ArticleWorkflowPage'
import PublicationPending from './pages/PublicationPending'
import PublicationHistory from './pages/PublicationHistory'
import PublicationDetail from './pages/PublicationDetail'
import PublicationReview from './pages/PublicationReview'
import SystemLogs from './pages/SystemLogs'
import SystemScheduler from './pages/SystemScheduler'
import SystemKillSwitch from './pages/SystemKillSwitch'
import Settings from './pages/Settings'
import WikipediaConnection from './pages/WikipediaConnection'
import ManualReview from './pages/ManualReview'
import ArticlesToAnalyze from './pages/ArticlesToAnalyze'
import ReadyToPublish from './pages/ReadyToPublish'
import UserContributions from './pages/UserContributions'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="analysis/new" element={<AnalysisNew />} />
          <Route path="analysis/results" element={<AnalysisResults />} />
          <Route path="analysis/history" element={<AnalyzedHistory />} />
          <Route path="analysis/workflow" element={<ArticleWorkflowPage />} />
          <Route path="article/detail" element={<ArticleDetail />} />
          <Route path="manual-review" element={<ManualReview />} />
          <Route path="articles/to-analyze" element={<ArticlesToAnalyze />} />
          <Route path="articles/ready-to-publish" element={<ReadyToPublish />} />
          <Route path="publication/pending" element={<PublicationPending />} />
          <Route path="publication/review" element={<PublicationReview />} />
          <Route path="publication/history" element={<PublicationHistory />} />
          <Route path="publication/detail" element={<PublicationDetail />} />
          <Route path="system/logs" element={<SystemLogs />} />
          <Route path="system/scheduler" element={<SystemScheduler />} />
          <Route path="system/kill-switch" element={<SystemKillSwitch />} />
          <Route path="settings/wikipedia" element={<WikipediaConnection />} />
          <Route path="settings" element={<Settings />} />
          <Route path="user-contributions" element={<UserContributions />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
