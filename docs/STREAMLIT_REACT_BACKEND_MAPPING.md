# Streamlit → Backend → React Functional Mapping

**Date:** 2026-08-13  
**Status:** Complete Phase 2 Mapping  
**Objective:** Identify all gaps between Streamlit functionality and React implementation

---

## 1. WIKIPEDIA CONNECTION

### Streamlit Implementation
- **Location:** `app.py:260-350`
- **Function:** `connect_to_wikipedia(lang, family, username, password)`
- **Session State:** 
  - `st.session_state.site` (pywikibot.Site)
  - `st.session_state.publisher` (Publisher)
  - `st.session_state.connected_lang`
  - `st.session_state.connected_family`
  - `st.session_state.wp_username`
  - `st.session_state.wp_password`
- **Features:**
  - Connection reuse if parameters match
  - pywikibot rate limiting integration
  - Publisher authentication with MediaWiki API
  - Dry-run mode support

### Backend Implementation
- **Location:** `backend/api/routes/auth.py`
- **Endpoints:**
  - `POST /api/auth/login` ✅
  - `POST /api/auth/logout` ✅
  - `GET /api/auth/status` ✅
  - `GET /api/auth/account` ✅
- **Session Management:** Module-level dictionary (not persistent)
- **Gap:** Session is lost on API restart, no persistence

### React Implementation
- **Location:** `frontend/src/pages/WikipediaConnection.tsx`
- **Features:**
  - Login form ✅
  - Status display ✅
  - Logout ✅
  - Account info display ❌
- **Gap:** No session persistence across page refreshes

---

## 2. ARTICLE RETRIEVAL

### 2.1 Category Retrieval

#### Streamlit Implementation
- **Location:** `app.py:413-465`
- **Function:** `retrieve_articles("category", ...)`
- **Parameters:**
  - `category_name` (with predefined categories from `categories_config.py`)
  - `max_articles` (default: 100)
  - `recursive` (include subcategories)
  - `exclude_published` (filter articles published in last 6 months)
  - `include_analyzed` (include already analyzed articles)
- **Process:**
  1. Check for analyzed-but-not-published articles (priority)
  2. Fetch articles in batches with pagination
  3. Filter by PublishedTracker (exclude published)
  4. Filter by AnalyzedTracker (exclude analyzed unless include_analyzed)
  5. Filter by character limit if in IA mode
- **Session State:** `st.session_state.articles`

#### Backend Implementation
- **Location:** `backend/api/routes/articles.py:80-154`
- **Endpoint:** `POST /api/articles/category`
- **Parameters:**
  - `category` ✅
  - `limit` ✅
  - `recursive` ✅
  - `exclude_published` ✅
  - `include_analyzed` ✅
- **Gap:** Missing pagination for large categories, missing character limit filtering

#### React Implementation
- **Location:** `frontend/src/pages/AnalysisNew.tsx:26-50`
- **Features:**
  - Category input ✅
  - Max articles ✅
  - Recursive checkbox ✅
  - Exclude published checkbox ✅
  - Include analyzed checkbox ✅
- **Gap:** No predefined categories dropdown, no priority article handling

---

### 2.2 Manual Retrieval

#### Streamlit Implementation
- **Location:** `app.py:466-476`
- **Function:** `retrieve_articles("manual", ...)`
- **Parameters:**
  - `titles` (text area, one per line)
  - `include_analyzed`
- **Process:**
  1. Parse titles from text area
  2. Use ManualRetriever
  3. Filter by AnalyzedTracker

#### Backend Implementation
- **Location:** `backend/api/routes/articles.py:157-212`
- **Endpoint:** `POST /api/articles/manual`
- **Parameters:**
  - `titles` ✅
  - `exclude_published` ✅
- **Gap:** Missing `include_analyzed` parameter

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing manual retrieval UI

---

### 2.3 User Contributions Retrieval

#### Streamlit Implementation
- **Location:** `app.py:478-528`
- **Function:** `retrieve_articles("user_contribs", ...)`
- **Parameters:**
  - `username`
  - `max_articles`
  - `include_analyzed`
- **Process:**
  1. Use UserContribsRetriever
  2. Batch fetching with pagination
  3. Filter by PublishedTracker
  4. Filter by AnalyzedTracker

#### Backend Implementation
- **Status:** ❌ Not implemented
- **Gap:** No endpoint for user contributions

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing user contributions UI

---

### 2.4 PetScan Retrieval

#### Streamlit Implementation
- **Location:** `app.py:530-556`
- **Function:** `retrieve_articles("petscan", ...)`
- **Parameters:**
  - `psid` (PetScan ID)
  - `include_analyzed`
- **Process:**
  1. Use PetScanRetriever
  2. Fetch large batch (needed * 10) to account for filtering
  3. Filter by PublishedTracker
  4. Filter by AnalyzedTracker

#### Backend Implementation
- **Status:** ❌ Not implemented
- **Gap:** No endpoint for PetScan

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing PetScan UI

---

### 2.5 File Retrieval

#### Streamlit Implementation
- **Location:** `app.py:558-582`
- **Function:** `retrieve_articles("file", ...)`
- **Parameters:**
  - `file_path`
  - `include_analyzed`
- **Process:**
  1. Use FileRetriever
  2. Load articles from file
  3. Verify existence on wiki
  4. Filter by AnalyzedTracker

#### Backend Implementation
- **Status:** ❌ Not implemented
- **Gap:** No endpoint for file retrieval

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing file retrieval UI

---

## 3. ARTICLE ANALYSIS

### 3.1 Regex Mode (DeadLinkAnalyzer)

#### Streamlit Implementation
- **Location:** `app.py:839-1001`
- **Function:** `analyze_article(article, silent=False)`
- **Process:**
  1. Get article content via pywikibot
  2. Get enabled analyzers from settings
  3. Execute DeadLinkAnalyzer
  4. Apply corrections via Corrector
  5. Store in session state:
     - `st.session_state.issues[title]`
     - `st.session_state.corrected_content[title]`
     - `st.session_state.article_status[title]`
  6. Record in AnalyzedTracker
- **Settings:** `st.session_state.settings_manager.get_settings().get_enabled_analyzers()`

#### Backend Implementation
- **Location:** `backend/api/routes/analysis.py:134-259`
- **Endpoint:** `POST /api/analysis/start`
- **Parameters:**
  - `article_title` ✅
  - `mode` ("regex" or "ai") ✅
  - `analysis_type` ✅
  - `ai_provider` ✅
- **Gap:** Missing analyzers configuration, missing batch analysis

#### React Implementation
- **Location:** `frontend/src/pages/AnalysisNew.tsx:52-113`
- **Features:**
  - Single article analysis ✅
  - Category mode (first article only) ✅
- **Gap:** Missing batch analysis, missing analyzer selection

---

### 3.2 AI Mode (Gemini/Ollama)

#### Streamlit Implementation
- **Location:** `app.py:732-836`
- **Function:** `analyze_article_with_lia(article, silent=False)`
- **Parameters:**
  - `lia_limite_caracteres` (default: 10800)
  - `ai_provider` ("gemini" or "ollama")
  - `gemini_api_key`
  - `gemini_project_id`
- **Process:**
  1. Get article content
  2. Verify character limit
  3. Send to AI provider
  4. Store corrected content
  5. Record in AnalyzedTracker
- **Session State:**
  - `st.session_state.lia_mode`
  - `st.session_state.lia_client`
  - `st.session_state.lia_corrected_content`
  - `st.session_state.lia_limite_caracteres`

#### Backend Implementation
- **Location:** `backend/api/routes/analysis.py:261-300`
- **Function:** `run_ai_analysis()`
- **Status:** ⚠️ Partial
- **Gap:** Missing character limit validation, missing AI provider configuration

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing AI mode UI, missing AI provider selection, missing character limit configuration

---

## 4. CORRECTION APPLICATION

#### Streamlit Implementation
- **Location:** `ui/issue_groups.py:221-290`
- **Function:** `_apply_selected_corrections()`
- **Process:**
  1. Get selected issue indices
  2. Apply corrections via Corrector
  3. Update session state
  4. Mark article as "approved"
- **Session State:**
  - `st.session_state.corrected_content[title]`
  - `st.session_state.article_status[title]`

#### Backend Implementation
- **Status:** ❌ Not implemented
- **Gap:** No endpoint for applying corrections

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing correction selection UI, missing apply functionality

---

## 5. PUBLICATION

#### Streamlit Implementation
- **Location:** `ui/issue_groups.py:292-350`
- **Function:** `_publish_corrections()`
- **Process:**
  1. Validate Kill Switch
  2. Get edit summary
  3. Publish via Publisher
  4. Track via PublishedTracker
  5. Update session state
- **Parameters:**
  - `dry_run` (default: True)
  - `minor` (default: False)
  - `original_content`
  - `expected_revision_id`

#### Backend Implementation
- **Location:** `backend/api/routes/publication.py:304-360`
- **Endpoints:**
  - `POST /api/publication/validate` ✅
  - `POST /api/publication/publish` ✅
  - `GET /api/publication/{publication_id}` ✅
  - `GET /api/publication/pending` ✅
- **Gap:** Missing edit summary generation, missing minor edit option

#### React Implementation
- **Status:** ⚠️ Partial
- **Gap:** Missing publication UI, missing validation display

---

## 6. AUTOMATION

#### Streamlit Implementation
- **Location:** `ui/sidebar.py:460-720`
- **Components:**
  - Scheduler configuration
  - Automation orchestrator
  - Telegram bot integration
  - Working hours enforcement
- **Parameters:**
  - `daily_limit`
  - `working_hours_start`
  - `working_hours_end`
  - `automation_lia_mode`
  - `automation_max_articles`

#### Backend Implementation
- **Status:** ⚠️ Partial
- **Gap:** Missing automation endpoints

#### React Implementation
- **Location:** `frontend/src/pages/SystemScheduler.tsx`
- **Status:** ⚠️ Partial
- **Gap:** Missing scheduler configuration UI, missing automation controls

---

## 7. AI ANALYSIS HISTORY

#### Streamlit Implementation
- **Location:** `app.py:1175-1336`
- **Function:** `_render_ai_analysis_history()`
- **Features:**
  - Status filter (published, rejected, ignored, pending, error)
  - Mode filter (IA, Regex)
  - Search by title
  - Date filter (24h, 7d, 30d)
  - Detailed view with metadata
- **Data Source:** `AnalyzedTracker.get_all_records()`

#### Backend Implementation
- **Status:** ❌ Not implemented
- **Gap:** No history endpoint

#### React Implementation
- **Location:** `frontend/src/pages/AnalyzedHistory.tsx`
- **Status:** ⚠️ Partial
- **Gap:** Missing filters, missing detailed view

---

## 8. DASHBOARD STATISTICS

#### Streamlit Implementation
- **Location:** `app.py:1339-1483`
- **Function:** `_render_dashboard_statistics()`
- **Metrics:**
  - Total articles analyzed
  - Articles published
  - Publication rate
  - Articles rejected
  - Queue size
  - Published today
  - Total published
  - Gemini cost
  - Savings metrics
- **Data Sources:**
  - `AnalyzedTracker.get_statistics()`
  - `AutomationReportGenerator.get_reports_summary()`
  - `Scheduler.state_manager.get_state()`

#### Backend Implementation
- **Status:** ⚠️ Partial
- **Gap:** Missing comprehensive statistics endpoint

#### React Implementation
- **Location:** `frontend/src/pages/Dashboard.tsx`
- **Status:** ⚠️ Partial
- **Gap:** Mock data, missing real statistics

---

## 9. CONFIGURATION

### 9.1 API Throttling

#### Streamlit Implementation
- **Location:** `app.py:129-146`
- **Parameters:**
  - `api_max_requests_per_minute` (default: 10.0)
  - `api_max_requests_per_minute_min` (default: 10.0)
  - `api_max_requests_per_minute_max` (default: 15.0)
  - `api_min_delay_min` (default: 8.0)
  - `api_min_delay_max` (default: 15.0)
  - `api_random_delay` (default: True)

#### Backend Implementation
- **Location:** `backend/api/routes/settings.py:99-108`
- **Status:** ✅ Exposed
- **Gap:** Missing UI for modification

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing throttling configuration UI

---

### 9.2 Publication Delays

#### Streamlit Implementation
- **Location:** `app.py:148-155`
- **Parameters:**
  - `pub_delay_min` (default: 4.0)
  - `pub_delay_max` (default: 7.0)

#### Backend Implementation
- **Location:** `backend/api/routes/settings.py:114-118`
- **Status:** ✅ Exposed
- **Gap:** Missing UI for modification

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing publication delay configuration UI

---

### 9.3 Analyzer Settings

#### Streamlit Implementation
- **Location:** `ui/sidebar.py:130-170`
- **Parameters:**
  - `enabled_analyzers` (list)
  - `min_severity`
  - `timeout`

#### Backend Implementation
- **Location:** `backend/api/routes/settings.py:109-113`
- **Status:** ✅ Exposed
- **Gap:** Missing UI for modification

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing analyzer configuration UI

---

## 10. PREDEFINED CATEGORIES

#### Streamlit Implementation
- **Location:** `categories_config.py:5-20`
- **Function:** `get_predefined_categories(lang)`
- **Categories for French:**
  - Article à wikifier
  - Article à wikifier/Liste complète
  - Article avec section à wikifier
  - Article à sourcer
  - Article à vérifier
  - Article à recycler
  - Article en cours de rédaction
  - Article de qualité à vérifier
  - Bon article en liste de suivi
  - Wikipédia:Ébauche
  - Portail:Biographie/Articles liés
  - Portail:Histoire/Articles liés

#### Backend Implementation
- **Status:** ❌ Not exposed
- **Gap:** No endpoint for predefined categories

#### React Implementation
- **Status:** ❌ Not implemented
- **Gap:** Missing predefined categories dropdown

---

## SUMMARY OF GAPS

### Critical Gaps (P0)
1. **Session Persistence:** React loses Wikipedia session on refresh
2. **Batch Analysis:** React can only analyze one article at a time
3. **Category Pagination:** Backend doesn't handle large categories properly
4. **AI Mode:** React has no AI analysis interface

### Important Gaps (P1)
1. **Missing Retrieval Methods:** PetScan, File, UserContribs
2. **Missing History:** No AI analysis history in React
3. **Missing Configuration:** No UI for throttling, delays, analyzers
4. **Missing Predefined Categories:** No dropdown in React
5. **Missing Correction Application:** No way to apply corrections in React
6. **Missing Publication UI:** No publication interface in React

### Enhancement Gaps (P2)
1. **Missing Automation:** Scheduler and orchestrator not fully integrated
2. **Missing Statistics:** Dashboard uses mock data
3. **Missing Kill Switch UI:** No kill switch management in React
4. **Missing Logs:** No system logs viewer in React

---

## NEXT STEPS

### Phase 3: Fix API and Integrations
1. Add missing endpoints (PetScan, File, UserContribs, History)
2. Improve category retrieval with pagination
3. Add predefined categories endpoint
4. Add batch analysis endpoint
5. Add correction application endpoint

### Phase 4: Fix React Workflows
1. Implement session persistence
2. Add all retrieval method UIs
3. Add AI mode interface
4. Add correction selection and application
5. Add publication interface
6. Add history viewer

### Phase 5: Fix Configuration Management
1. Add throttling configuration UI
2. Add publication delay configuration UI
3. Add analyzer configuration UI
4. Add predefined categories dropdown
5. Persist configuration changes

### Phase 6: Fix Jobs and Real-time Handling
1. Implement proper job tracking
2. Add real-time progress updates
3. Handle job cancellation
4. Display job history

### Phase 7: Fix Errors and UI States
1. Add comprehensive error handling
2. Implement loading states per operation
3. Add user-friendly error messages
4. Handle connection failures gracefully

### Phase 8: Complete Testing
1. Test all workflows end-to-end
2. Verify Streamlit parity
3. Test error scenarios
4. Verify non-regression

### Phase 9: UI/UX Improvements
1. Improve visual consistency
2. Add animations and transitions
3. Improve accessibility
4. Add tooltips and help text
