"""
OVIX Backend API - Analysis Routes

Handles article analysis using the existing DeadLinkAnalyzer.
"""

import logging
import asyncio
import uuid
import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import pywikibot

# Phase 2: Database and tracking imports
from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.utils.tracking_service import TrackingService

logger = logging.getLogger(__name__)

router = APIRouter()

# Dedicated thread pool for analysis operations to avoid GIL contention
_analysis_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="analysis-worker")

# ============================================================================
# Models
# ============================================================================

class AnalysisRequest(BaseModel):
    """Analysis request."""
    article_title: str
    mode: str = "regex"  # "regex" or "ai"
    analysis_type: str = "article"  # "article" or "category"
    ai_provider: Optional[str] = None  # "gemini" or "ollama"
    ai_character_limit: Optional[int] = 10800  # Character limit for AI mode
    gemini_api_key: Optional[str] = None
    gemini_project_id: Optional[str] = None


class BatchAnalysisRequest(BaseModel):
    """Batch analysis request."""
    article_titles: List[str]
    mode: str = "regex"  # "regex" or "ai"
    ai_provider: Optional[str] = None  # "gemini" or "ollama"
    ai_character_limit: Optional[int] = 10800
    gemini_api_key: Optional[str] = None
    gemini_project_id: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Analysis response."""
    success: bool
    job_id: str
    status: str
    message: str


class AnalysisStatusResponse(BaseModel):
    """Analysis status response."""
    job_id: str
    article_title: str
    status: str
    progress: float
    message: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    results: Optional[Dict[str, Any]] = None


class IssueInfo(BaseModel):
    """Issue information."""
    issue_type: str
    description: str
    severity: str
    position: Optional[int] = None
    original_text: Optional[str] = None
    suggested_text: Optional[str] = None
    context: Optional[str] = None
    # DeadLink compatibility fields
    url: Optional[str] = None
    status: Optional[str] = None
    anchor: Optional[str] = None
    candidates: Optional[List[Dict[str, Any]]] = None


class AnalysisResultsResponse(BaseModel):
    """Analysis results response."""
    success: bool
    job_id: str
    article_title: Optional[str] = None  # Allow None for compatibility with migrated data
    original_content: Optional[str] = None
    corrected_content: Optional[str] = None
    issues: List[IssueInfo]
    stats: Dict[str, Any]
    completed_at: Optional[str] = None


# ============================================================================
# Job Management
# ============================================================================

# Database-backed job storage (persistent across restarts)
def get_database():
    """Get database manager for job storage."""
    from backend.api.main import get_database
    return get_database()


def create_analysis_job(article_title: str, mode: str, ai_provider: Optional[str] = None,
                      ai_character_limit: Optional[int] = None, gemini_api_key: Optional[str] = None,
                      gemini_project_id: Optional[str] = None) -> str:
    """Create a new analysis job (persistent, stored in database)."""
    job_id = str(uuid.uuid4())
    
    db = get_database()
    success = db.create_analysis_job(
        job_id=job_id,
        article_title=article_title,
        mode=mode,
        ai_provider=ai_provider,
        ai_character_limit=ai_character_limit,
        gemini_api_key=gemini_api_key,
        gemini_project_id=gemini_project_id
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create analysis job in database")
    
    return job_id


def update_analysis_job(job_id: str, **kwargs):
    """Update analysis job status (persistent, stored in database)."""
    db = get_database()
    success = db.update_analysis_job(job_id, **kwargs)

    if not success:
        logger.error(f"Failed to update job {job_id} with kwargs: {kwargs}")
        return False

    logger.info(f"Updated job {job_id} successfully with status: {kwargs.get('status')}")
    return True


def get_analysis_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get analysis job from database."""
    db = get_database()
    return db.get_analysis_job(job_id)


def create_batch_job(article_titles: List[str], mode: str, ai_provider: Optional[str] = None,
                     ai_character_limit: Optional[int] = None, gemini_api_key: Optional[str] = None,
                     gemini_project_id: Optional[str] = None) -> str:
    """Create a new batch analysis job (persistent, stored in database)."""
    batch_id = str(uuid.uuid4())
    
    db = get_database()
    success = db.create_analysis_job(
        job_id=batch_id,
        article_title=f"Batch of {len(article_titles)} articles",
        mode=mode,
        ai_provider=ai_provider,
        ai_character_limit=ai_character_limit,
        gemini_api_key=gemini_api_key,
        gemini_project_id=gemini_project_id
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create batch job in database")
    
    # Store batch metadata separately for individual job tracking
    # For now, we'll use a simple approach: batch job contains a reference to individual article jobs
    # In a more sophisticated implementation, we'd have a separate batch_jobs table
    
    return batch_id


# ============================================================================
# Dependencies
# ============================================================================

def get_wikipedia_session():
    """Get current Wikipedia session."""
    from backend.api.routes.auth import get_wikipedia_session as get_session
    return get_session()


def get_analyzed_tracker():
    """Get analyzed tracker."""
    from backend.api.main import get_analyzed_tracker
    return get_analyzed_tracker()


# ============================================================================
# Analysis Worker
# ============================================================================

def _run_blocking_analysis(
    analysis_id: str,
    article_title: str,
    mode: str,
    site: pywikibot.Site,
    ai_provider: Optional[str] = None,
    ai_character_limit: Optional[int] = 10800,
    gemini_api_key: Optional[str] = None,
    gemini_project_id: Optional[str] = None
):
    """
    Synchronous wrapper for blocking analysis operations.
    This runs in a separate thread to avoid blocking the event loop.
    """
    # Check if job was cancelled or paused before starting
    job = get_analysis_job(analysis_id)
    if job and job.get("status") in ["cancelled", "paused"]:
        logger.info(f"Analysis {analysis_id} was cancelled or paused before starting")
        return None, (None, None, None, None, None)
    
    # Update job status
    update_analysis_job(
        analysis_id,
        status="running",
        progress=0.1,
        message="Starting analysis",
        started_at=datetime.now().isoformat()
    )
    
    # Get article content (blocking pywikibot call)
    job = get_analysis_job(analysis_id)
    if job and job.get("status") in ["cancelled", "paused"]:
        logger.info(f"Analysis {analysis_id} was cancelled or paused during content retrieval")
        return None, (None, None, None, None, None)
    
    update_analysis_job(
        analysis_id,
        progress=0.2,
        message="Retrieving article content"
    )

    page = pywikibot.Page(site, article_title)
    if not page.exists():
        raise Exception(f"Article '{article_title}' not found. Note: Categories are not supported yet. Please use individual article names.")
    
    original_content = page.get()  # Blocking network I/O
    
    # Track analysis with ANALYZING status after page is retrieved
    analyzed_tracker = get_analyzed_tracker()
    if analyzed_tracker:
        from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus
        analyzed_tracker.record_analysis(
            title=article_title,
            page_id=page.pageid,
            revision_id=page.latest_revision_id,
            status=AnalysisStatus.ANALYZING,
            mode=mode
        )
    
    # Run analysis based on mode
    job = get_analysis_job(analysis_id)
    if job and job.get("status") in ["cancelled", "paused"]:
        logger.info(f"Analysis {analysis_id} was cancelled or paused before running analysis")
        return None, (None, None, None, None, None)
    
    update_analysis_job(
        analysis_id,
        progress=0.3,
        message=f"Running {mode} analysis"
    )
    
    if mode == "ai":
        # AI mode using LIA for typographic correction and dead link analysis
        from wikipedia_maintenance.utils.config import load_config
        from wikipedia_maintenance.utils.publisher import Corrector
        
        config = load_config()
        
        # Apply case normalization if enabled (BEFORE AI analysis)
        # Note: In AI mode, case normalization is handled by LIA's main prompt, not by CaseNormalizer's specific AI prompt
        # In regex mode, we also disable CaseNormalizer's specific AI to use only classical normalization
        content = original_content
        if hasattr(config, 'analysis') and hasattr(config.analysis, 'enable_case_normalization'):
            if config.analysis.enable_case_normalization:
                from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer
                enable_ner = getattr(config.analysis, 'enable_ner_title_normalization', False)
                # Disable CaseNormalizer's specific AI normalization - LIA's main prompt handles case normalization in AI mode
                # In regex mode, we use only classical normalization (no AI)
                normalize_with_ai = False  # Always false - LIA main prompt handles case normalization in AI mode
                normalizer = CaseNormalizer(
                    enabled=config.analysis.enable_case_normalization,
                    enable_ner_title_normalization=enable_ner,
                    normalize_with_ai=normalize_with_ai
                )
                normalization_result = normalizer.normalize_text(content)
                if normalization_result.total_changes > 0:
                    logger.info(f"Case normalization applied: {normalization_result.total_changes} changes")
                    content = normalization_result.normalized_text
                else:
                    logger.info("Case normalization: no changes needed")
            else:
                normalization_result = None
        else:
            normalization_result = None
        
        # Apply AI typographic correction using LIA
        try:
            from wikipedia_maintenance.utils.gemini_client import GeminiClient
            
            # Get AI parameters from config or use defaults
            ai_provider = ai_provider or "gemini"
            ai_limit = ai_character_limit or 10000
            gemini_api_key = gemini_api_key or None
            gemini_project_id = gemini_project_id or None
            
            if ai_provider == "gemini" and gemini_api_key:
                lia_client = GeminiClient(
                    api_key=gemini_api_key,
                    project_id=gemini_project_id,
                    model="gemini-flash-lite-latest",
                    limit=ai_limit
                )
                
                # Check length
                ok, nb_caracteres = lia_client.verifier_longueur(content)
                if ok:
                    # Apply LIA correction
                    corrected_content, corrections = lia_client.corriger_article(
                        content,
                        page_title=article_title,
                        page_id=page.pageid if page else 0,
                        revision_id=page.latest_revision_id if page else 0
                    )
                    
                    if corrected_content != content:
                        logger.info(f"LIA correction applied: {len(corrections)} corrections")
                        content = corrected_content
                    else:
                        logger.info("LIA correction: no changes needed")
                else:
                    logger.warning(f"Content too long for LIA: {nb_caracteres} characters")
            else:
                logger.warning("AI mode requested but Gemini not configured")
                
        except Exception as e:
            logger.error(f"LIA correction failed: {e}")
            # Continue with dead link analysis even if LIA fails
        
        # Apply dead link analysis (still needed in AI mode)
        if hasattr(config, 'analysis') and hasattr(config.analysis, 'enable_dead_link_analyzer'):
            if config.analysis.enable_dead_link_analyzer:
                from wikipedia_maintenance.analyzers import DeadLinkAnalyzer
                
                # Phase 2: Initialize tracking service for correlation
                tracking_service = None
                try:
                    db_manager = DatabaseManager()
                    tracking_service = TrackingService(db_manager)
                    logger.info("Phase 2: TrackingService initialized for DeadLinkAnalyzer")
                except Exception as e:
                    logger.warning(f"Phase 2: Failed to initialize TrackingService: {e}")
                
                analyzer = DeadLinkAnalyzer(tracking_service=tracking_service)
                issues = analyzer.analyze(content)
                logger.info(f"Dead link analysis in AI mode: {len(issues)} issues found")
            else:
                issues = []
                logger.info("DeadLinkAnalyzer disabled in config")
        else:
            issues = []
            logger.info("DeadLinkAnalyzer setting not found, defaulting to enabled")
        
        # Apply ReferenceEnricherAnalyzer if enabled (enriches healthy references)
        if hasattr(config, 'reference_enricher_analyzer') and config.reference_enricher_analyzer.enabled:
            from wikipedia_maintenance.analyzers import ReferenceEnricherAnalyzer
            try:
                enricher = ReferenceEnricherAnalyzer()
                enrichment_issues = enricher.analyze(content)
                # Combine issues from both analyzers
                issues.extend(enrichment_issues)
                logger.info(f"ReferenceEnricherAnalyzer applied in AI mode: {len(enrichment_issues)} enrichments")
            except Exception as e:
                logger.warning(f"ReferenceEnricherAnalyzer failed in AI mode: {e}")
        else:
            logger.info("ReferenceEnricherAnalyzer disabled in config (AI mode)")
        
        return content, (issues, content, page.pageid if page else 0, page.latest_revision_id if page else 0, normalization_result)
    else:
        # Regex mode using DeadLinkAnalyzer (blocking CPU/IO)
        from wikipedia_maintenance.analyzers import DeadLinkAnalyzer
        from wikipedia_maintenance.utils.publisher import Corrector
        from wikipedia_maintenance.utils.config import load_config

        # Load config to check analyzer settings
        config = load_config()

        # Apply case normalization if enabled (BEFORE dead link analysis)
        # Note: In AI mode, case normalization is handled by LIA's main prompt, not by CaseNormalizer's specific AI prompt
        # In regex mode, we also disable CaseNormalizer's specific AI to use only classical normalization
        content = original_content
        if hasattr(config, 'analysis') and hasattr(config.analysis, 'enable_case_normalization'):
            if config.analysis.enable_case_normalization:
                from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer
                enable_ner = getattr(config.analysis, 'enable_ner_title_normalization', False)
                # Disable CaseNormalizer's specific AI normalization - LIA's main prompt handles case normalization in AI mode
                # In regex mode, we use only classical normalization (no AI)
                normalize_with_ai = False  # Always false - LIA main prompt handles case normalization in AI mode
                normalizer = CaseNormalizer(
                    enabled=config.analysis.enable_case_normalization,
                    enable_ner_title_normalization=enable_ner,
                    normalize_with_ai=normalize_with_ai
                )
                normalization_result = normalizer.normalize_text(content)
                if normalization_result.total_changes > 0:
                    logger.info(f"Case normalization applied: {normalization_result.total_changes} changes")
                    content = normalization_result.normalized_text
                else:
                    logger.info("Case normalization: no changes needed")
            else:
                normalization_result = None
        else:
            normalization_result = None

        # Check if DeadLinkAnalyzer is enabled in config
        if hasattr(config, 'analysis') and hasattr(config.analysis, 'enable_dead_link_analyzer'):
            if not config.analysis.enable_dead_link_analyzer:
                logger.info("DeadLinkAnalyzer disabled in config, skipping analysis")
                return original_content, ([], content, page.pageid, page.latest_revision_id, normalization_result)
            else:
                logger.info("DeadLinkAnalyzer enabled in config, proceeding with analysis")
        else:
            logger.info("DeadLinkAnalyzer setting not found in config, defaulting to enabled")

        # Phase 2: Initialize tracking service for correlation
        tracking_service = None
        try:
            db_manager = DatabaseManager()
            tracking_service = TrackingService(db_manager)
            logger.info("Phase 2: TrackingService initialized for DeadLinkAnalyzer")
        except Exception as e:
            logger.warning(f"Phase 2: Failed to initialize TrackingService: {e}")

        analyzer = DeadLinkAnalyzer(tracking_service=tracking_service)
        issues = analyzer.analyze(content)  # Blocking CPU/IO
        
        # Apply ReferenceEnricherAnalyzer if enabled (enriches healthy references)
        if hasattr(config, 'reference_enricher_analyzer') and config.reference_enricher_analyzer.enabled:
            from wikipedia_maintenance.analyzers import ReferenceEnricherAnalyzer
            try:
                enricher = ReferenceEnricherAnalyzer()
                enrichment_issues = enricher.analyze(content)
                # Combine issues from both analyzers
                issues.extend(enrichment_issues)
                logger.info(f"ReferenceEnricherAnalyzer applied: {len(enrichment_issues)} enrichments")
            except Exception as e:
                logger.warning(f"ReferenceEnricherAnalyzer failed: {e}")
        else:
            logger.info("ReferenceEnricherAnalyzer disabled in config")
        
        # Check for cancellation or pause after analysis
        job = get_analysis_job(analysis_id)
        if job and job.get("status") in ["cancelled", "paused"]:
            logger.info(f"Analysis {analysis_id} was cancelled or paused after analysis")
            return None, (None, None, None, None, normalization_result)
        
        # Generate corrected content (blocking CPU)
        corrector = Corrector(content)
        corrected_content = corrector.apply_corrections(issues)
        
        return original_content, (issues, corrected_content, page.pageid, page.latest_revision_id, normalization_result)


async def run_analysis_worker(
    analysis_id: str,
    article_title: str,
    mode: str,
    site: pywikibot.Site,
    ai_provider: Optional[str] = None,
    ai_character_limit: Optional[int] = 10800,
    gemini_api_key: Optional[str] = None,
    gemini_project_id: Optional[str] = None
):
    """
    Background worker to run analysis.
    
    This function runs the actual analysis using the existing DeadLinkAnalyzer
    and stores results in the job dictionary. Blocking operations are offloaded
    to a thread pool to avoid blocking the event loop.
    """
    try:
        loop = asyncio.get_event_loop()
        
        # Run blocking operations in dedicated thread pool to isolate load
        original_content, analysis_result = await loop.run_in_executor(
            _analysis_executor,
            _run_blocking_analysis,
            analysis_id,
            article_title,
            mode,
            site,
            ai_provider,
            ai_character_limit,
            gemini_api_key,
            gemini_project_id
        )
        
        if original_content is None:
            # Job was cancelled during blocking operations
            return
        
        # Handle AI mode separately (already async)
        if mode == "ai":
            issues, corrected_content, page_id, revision_id, normalization_result = analysis_result
            corrected_content = await run_ai_analysis(
                original_content,
                ai_provider,
                analysis_id,
                ai_character_limit,
                gemini_api_key,
                gemini_project_id
            )
        else:
            # Unpack regex mode results
            issues, corrected_content, page_id, revision_id, normalization_result = analysis_result
        
        # Convert issues to response format and collect manual review URLs
        issue_infos = []
        manual_review_urls = []  # Initialize before the loop
        
        for issue in issues:
            issue_infos.append(IssueInfo(
                issue_type=issue.issue_type,
                description=issue.description,
                severity=issue.severity,
                position=issue.position,
                original_text=issue.original_text,
                suggested_text=issue.suggested_text,
                context=issue.context,
                # Additional fields for DeadLink compatibility
                url=getattr(issue, 'url', None),
                status=getattr(issue, 'status', None),
                anchor=getattr(issue, 'anchor', None),
                candidates=getattr(issue, 'candidates', [])
            ))
            
            # Collect URLs requiring manual review
            if issue.extra and issue.extra.get('repair_status') == 'REVIEW_REQUIRED':
                url = issue.extra.get('url') or issue.original_text
                if url:
                    manual_review_urls.append(url)
        
        # Calculate link statistics (needed for both tracker and database persistence)
        import re
        
        # Count total links in the original content - improved pattern to catch all wikicode link formats
        # Matches: [https://example.com], [https://example.com text], [[File:...]], [[Image:...]], etc.
        # But we only want external links (http/https)
        link_pattern = r'\[https?://[^\s\]]+\]|\[https?://[^\s\]+ [^\]]+\]'
        # Also catch links that might have different formatting
        link_pattern2 = r'https?://[^\s<>"\'\)]+'
        all_links = set(re.findall(link_pattern, original_content) + re.findall(link_pattern2, original_content))
        total_links = len(all_links)

        # Count dead links (issues with dead link type)
        dead_links_count = len([i for i in issues if 'dead' in i.issue_type.lower()])

        # Count corrected links (issues with suggested text AND actual repair applied)
        # Only count issues that represent actual repairs, not informational/diagnostic issues
        valid_repair_statuses = [
            'REPAIR_APPLIED', 'SAFE_REPLACEMENT', 'ARCHIVE_ONLY_REPAIR', 'ENRICHMENT_APPLIED', 'BARE_URL_ENRICHMENT_APPLIED'
        ]
        
        corrected_links_count = len([
            i for i in issues 
            if i.suggested_text 
            and ('dead' in i.issue_type.lower() or 'reference_enrichment' in i.issue_type.lower())
            and i.extra 
            and i.extra.get('repair_status') in valid_repair_statuses
        ])
        
        # Track analysis with final status
        analyzed_tracker = get_analyzed_tracker()
        if analyzed_tracker:
            from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus

            # If no issues found, mark as IGNORED instead of PENDING
            final_status = AnalysisStatus.IGNORED if len(issues) == 0 else AnalysisStatus.PENDING

            analyzed_tracker.record_analysis(
                title=article_title,
                page_id=page_id if page_id else 0,
                revision_id=revision_id if revision_id else 0,
                status=final_status,
                mode=mode,
                original_content=original_content,
                corrected_content=corrected_content,
                character_count=len(original_content) if original_content else 0,
                changes_count=len(issues),
                total_links=total_links,
                dead_links_count=dead_links_count,
                corrected_links_count=corrected_links_count,
                human_verified=False,
                manual_review_urls=manual_review_urls if manual_review_urls else None
            )

        # Update article status in the analysis queue
        try:
            db = get_database()
            cursor = db.conn.cursor()

            # Remove article from articles_to_analyze table after successful analysis
            cursor.execute("""
                DELETE FROM articles_to_analyze
                WHERE title = ?
            """, (article_title,))

            db.conn.commit()
            logger.info(f"Removed '{article_title}' from articles_to_analyze after successful analysis")
        except Exception as e:
            logger.error(f"Failed to remove article from analysis queue: {e}", exc_info=True)
        
        # Update job status (results stored in analysis_results table)
        update_analysis_job(
            analysis_id,
            status="completed",
            progress=1.0,
            message="Analysis completed",
            completed_at=datetime.now().isoformat()
        )
        
        # Persist analysis result to database
        manual_review_urls_json = json.dumps(manual_review_urls) if manual_review_urls else None
        issues_json = json.dumps([issue.dict() for issue in issue_infos]) if issue_infos else None
        
        # Prepare normalization data
        normalization_changes_count = 0
        normalization_ignored_count = 0
        normalization_reports_json = None
        
        if normalization_result:
            normalization_changes_count = normalization_result.total_changes
            normalization_ignored_count = normalization_result.total_ignored
            # Convert normalization reports to JSON
            if normalization_result.reports:
                reports_data = []
                for report in normalization_result.reports:
                    reports_data.append({
                        'template_name': report.template_name,
                        'parameter_changes': report.parameter_changes,
                        'ignored_occurrences': report.ignored_occurrences
                    })
                normalization_reports_json = json.dumps(reports_data)
        
        db.create_analysis_result(
            result_id=f"{article_title}_{revision_id if revision_id else 0}",
            job_id=analysis_id,
            article_title=article_title,
            page_id=page_id if page_id else 0,
            revision_id=revision_id if revision_id else 0,
            status="pending",  # Awaiting decision (publish/ignore/reject)
            mode=mode,
            changes_count=len(issues),
            summary=f"Analysis completed with {len(issues)} issues",
            original_content=original_content,
            corrected_content=corrected_content,
            character_count=len(original_content) if original_content else 0,
            total_links=total_links,
            dead_links_count=dead_links_count,
            corrected_links_count=corrected_links_count,
            human_verified=False,
            manual_review_urls=manual_review_urls_json,
            issues_json=issues_json,
            analysis_date=datetime.now().isoformat(),
            normalization_changes_count=normalization_changes_count,
            normalization_ignored_count=normalization_ignored_count,
            normalization_reports=normalization_reports_json
        )

        # Note: Batch job tracking simplified for database persistence
        # Individual jobs are now tracked independently in the database
        # Batch coordination can be added later with a separate batch_jobs table
        logger.info(f"Analysis {analysis_id} completed for article {article_title}")
        
    except Exception as e:
        logger.error(f"Analysis {analysis_id} failed: {e}", exc_info=True)

        # Check if it's a network/Connection error
        error_message = str(e)
        if "ConnectionError" in error_message or "Max retries exceeded" in error_message or "NameResolutionError" in error_message or "getaddrinfo failed" in error_message:
            friendly_message = "Erreur de connexion à Wikipédia. Vérifiez votre connexion internet."
        else:
            friendly_message = f"Erreur lors de l'analyse: {error_message}"

        # Update tracker with ERROR status
        analyzed_tracker = get_analyzed_tracker()
        if analyzed_tracker:
            from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus
            analyzed_tracker.record_analysis(
                title=article_title,
                page_id=0,  # Unknown if we failed early
                revision_id=0,  # Unknown if we failed early
                status=AnalysisStatus.ERROR,
                mode=mode
            )

        update_analysis_job(
            analysis_id,
            status="failed",
            progress=0.0,
            message=friendly_message,
            completed_at=datetime.now().isoformat(),
            error=str(e)
        )
        
        # Also store failed analysis in analysis_results table for frontend visibility
        try:
            db = get_database()
            db.create_analysis_result(
                result_id=f"{article_title}_error",
                job_id=analysis_id,
                article_title=article_title,
                page_id=0,
                revision_id=0,
                status="error",
                mode=mode,
                changes_count=0,
                summary=friendly_message,
                original_content=None,
                corrected_content=None,
                character_count=0,
                total_links=0,
                dead_links_count=0,
                corrected_links_count=0,
                human_verified=False,
                manual_review_urls=None,
                issues_json=None,
                analysis_date=datetime.now().isoformat()
            )
            logger.info(f"Stored failed analysis result for {article_title} in database")
        except Exception as db_error:
            logger.error(f"Failed to store error result in database: {db_error}")


async def run_ai_analysis(
    content: str, 
    ai_provider: Optional[str], 
    analysis_id: str,
    ai_character_limit: Optional[int] = 10800,
    gemini_api_key: Optional[str] = None,
    gemini_project_id: Optional[str] = None
) -> str:
    """Run AI analysis using Gemini or Ollama."""
    update_analysis_job(
        analysis_id,
        progress=0.5,
        message=f"Running AI analysis with {ai_provider or 'gemini'}"
    )
    
    if ai_provider == "ollama":
        from wikipedia_maintenance.utils.lia_client import LIAOllamaClient
        client = LIAOllamaClient()
    else:
        from wikipedia_maintenance.utils.gemini_client import GeminiClient
        # Use provided API key or load from environment
        api_key = gemini_api_key or None
        project_id = gemini_project_id or None
        client = GeminiClient(api_key=api_key, project_id=project_id)
    
    # Verify length with provided limit
    from wikipedia_maintenance.utils.verif_longueur import verifier
    ok, length = verifier(content, ai_character_limit)
    if not ok:
        raise Exception(f"Article too long: {length} characters (limit: {ai_character_limit})")
    
    update_analysis_job(
        analysis_id,
        progress=0.7,
        message="Sending to AI model"
    )
    
    # Run correction
    success, corrected, error = client.corriger_article(content)
    
    if not success:
        raise Exception(f"AI correction failed: {error}")
    
    update_analysis_job(
        analysis_id,
        progress=0.9,
        message="AI correction completed"
    )
    
    return corrected


# ============================================================================
# Routes
# ============================================================================

@router.post("/start", response_model=AnalysisResponse)
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    session: dict = Depends(get_wikipedia_session)
):
    """
    Start article analysis.
    
    Creates a background job to analyze the article using the existing
    DeadLinkAnalyzer (regex mode) or AI client (AI mode).
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        # Create analysis job with AI parameters
        analysis_id = create_analysis_job(
            request.article_title, 
            request.mode,
            request.ai_provider,
            request.ai_character_limit,
            request.gemini_api_key,
            request.gemini_project_id
        )
        
        # Start background worker
        background_tasks.add_task(
            run_analysis_worker,
            analysis_id,
            request.article_title,
            request.mode,
            site,
            request.ai_provider,
            request.ai_character_limit,
            request.gemini_api_key,
            request.gemini_project_id
        )
        
        logger.info(f"Started analysis {analysis_id} for article {request.article_title}")
        
        return AnalysisResponse(
            success=True,
            job_id=analysis_id,
            status="pending",
            message="Analysis started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {str(e)}")


@router.post("/batch", response_model=AnalysisResponse)
async def start_batch_analysis(
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    session: dict = Depends(get_wikipedia_session)
):
    """
    Start batch analysis for multiple articles.

    Creates background jobs to analyze multiple articles using the existing
    DeadLinkAnalyzer (regex mode) or AI client (AI mode).
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")

        site = session.get("site")
        if not site:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")

        if not request.article_titles:
            raise HTTPException(status_code=400, detail="No article titles provided")

        # Create a batch job ID
        batch_id = create_batch_job(
            request.article_titles, 
            request.mode,
            request.ai_provider,
            request.ai_character_limit,
            request.gemini_api_key,
            request.gemini_project_id
        )

        # Start analysis for each article as independent jobs
        # Batch coordination simplified for database persistence
        for title in request.article_titles:
            analysis_id = create_analysis_job(
                title, 
                request.mode,
                request.ai_provider,
                request.ai_character_limit,
                request.gemini_api_key,
                request.gemini_project_id
            )

            background_tasks.add_task(
                run_analysis_worker,
                analysis_id,
                title,
                request.mode,
                site,
                request.ai_provider,
                request.ai_character_limit,
                request.gemini_api_key,
                request.gemini_project_id
            )

        logger.info(f"Started batch analysis {batch_id} for {len(request.article_titles)} articles")

        return AnalysisResponse(
            success=True,
            job_id=batch_id,  # Return batch ID for tracking
            status="pending",
            message=f"Batch analysis started for {len(request.article_titles)} articles (individual jobs tracked in database)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start batch analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start batch analysis: {str(e)}")


@router.get("/{job_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(job_id: str):
    """
    Get analysis job status.

    Returns the current status and progress of an analysis job from database.
    """
    try:
        job = get_analysis_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        # Handle database job structure
        return AnalysisStatusResponse(
            job_id=job.get("id", job_id),
            article_title=job.get("article_title", "Unknown"),
            status=job.get("status", "unknown"),
            progress=job.get("progress", 0.0),
            message=job.get("message", ""),
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            error=job.get("error"),
            results=job.get("results")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis status: {e}", exc_info=True)


@router.get("/{job_id}/stream")
async def stream_analysis_status(job_id: str):
    """
    Stream analysis job status using Server-Sent Events.

    This endpoint provides real-time updates for the analysis job status,
    allowing the UI to receive progress updates without polling.
    """
    async def event_stream():
        job = get_analysis_job(job_id)
        if not job:
            yield f"data: {json.dumps({'error': 'Analysis job not found'})}\n\n"
            return

        # Send initial status
        yield f"data: {json.dumps({'status': job['status'], 'message': job['message'], 'progress': job.get('progress', 0.0)})}\n\n"

        # If already completed or failed, send final status and close
        if job['status'] in ['completed', 'failed']:
            yield f"data: {json.dumps({'status': job['status'], 'message': job['message'], 'progress': job.get('progress', 0.0), 'error': job.get('error')})}\n\n"
            return

        # Wait for status changes
        last_status = job['status']
        max_wait = 600  # 10 minutes max for analysis
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < max_wait:
            await asyncio.sleep(2)  # Check every 2 seconds

            current_job = get_analysis_job(job_id)
            if not current_job:
                yield f"data: {json.dumps({'error': 'Analysis job not found'})}\n\n"
                return

            if current_job['status'] != last_status:
                last_status = current_job['status']
                yield f"data: {json.dumps({'status': current_job['status'], 'message': current_job['message'], 'progress': current_job.get('progress', 0.0), 'error': current_job.get('error')})}\n\n"

                # Close stream if completed or failed
                if current_job['status'] in ['completed', 'failed']:
                    break

        # Timeout
        yield f"data: {json.dumps({'error': 'Timeout waiting for analysis'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{job_id}/cancel")
async def cancel_analysis(job_id: str):
    """
    Cancel an analysis job.
    
    Updates job status to cancelled in database.
    """
    try:
        job = get_analysis_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        if job.get("status") in ["completed", "cancelled"]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed or already cancelled job")

        # Update job status in database
        update_analysis_job(job_id, status="cancelled", message="Job cancelled by user")

        logger.info(f"Analysis job {job_id} cancelled")

        return {"success": True, "message": "Job cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel analysis job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")

@router.post("/{job_id}/pause")
async def pause_analysis(job_id: str):
    """
    Pause an analysis job.
    
    Updates job status to paused in database.
    """
    try:
        job = get_analysis_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        if job.get("status") != "running":
            raise HTTPException(status_code=400, detail="Can only pause running jobs")

        # Update job status in database
        update_analysis_job(job_id, status="paused", message="Analysis paused")

        logger.info(f"Paused analysis {job_id}")

        return {"success": True, "message": "Analysis paused"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to pause analysis: {str(e)}")


@router.post("/{job_id}/resume")
async def resume_analysis(job_id: str):
    """
    Resume a paused analysis job.
    
    Updates job status back to running in database.
    """
    try:
        job = get_analysis_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")

        if job.get("status") != "paused":
            raise HTTPException(status_code=400, detail="Can only resume paused jobs")

        # Update job status in database
        update_analysis_job(job_id, status="running", message="Analysis resumed")

        logger.info(f"Resumed analysis {job_id}")

        return {"success": True, "message": "Analysis resumed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to resume analysis: {str(e)}")


@router.get("/{job_id}/results", response_model=AnalysisResultsResponse)
async def get_analysis_results(job_id: str, database = Depends(get_database)):
    """
    Get analysis results.

    Returns the detailed results of a completed analysis from database.
    """
    try:
        logger.info(f"Getting analysis results for job_id: {job_id}")
        
        # First try to get from in-memory job tracker
        job = get_analysis_job(job_id)
        logger.info(f"Job found in memory: {job is not None}")

        if not job:
            # If not found in memory, try to get from database
            logger.info(f"Job not found in memory, checking database")
            try:
                cursor = database.conn.cursor()
                cursor.execute("""
                    SELECT article_title, original_content, corrected_content, 
                           dead_links_count, corrected_links_count, character_count, 
                           total_links, changes_count, analysis_date, issues_json
                    FROM analysis_results
                    WHERE job_id = ?
                    ORDER BY analysis_date DESC
                    LIMIT 1
                """, (job_id,))
                
                row = cursor.fetchone()
                logger.info(f"Database query result: {row is not None}")
                
                if row:
                    logger.info(f"Found job in database: article_title={row[0]}, dead_links_count={row[3]}, corrected_links_count={row[4]}")
                    
                    # Parse issues_json if available
                    issues_data = []
                    if row[9]:  # issues_json column
                        try:
                            issues_data = json.loads(row[9])
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse issues_json: {e}")
                    
                    job = {
                        "job_id": job_id,
                        "article_title": row[0],
                        "original_content": row[1],
                        "corrected_content": row[2],
                        "dead_links_count": row[3],
                        "corrected_links_count": row[4],
                        "character_count": row[5],
                        "total_links": row[6],
                        "changes_count": row[7],
                        "analysis_date": row[8],
                        "status": "completed",
                        "results": {
                            "article_title": row[0],
                            "original_content": row[1],
                            "corrected_content": row[2],
                            "dead_links_count": row[3],
                            "corrected_links_count": row[4],
                            "character_count": row[5],
                            "total_links": row[6],
                            "changes_count": row[7],
                            "stats": {
                                "total_issues": row[3],  # dead_links_count
                                "dead_links_count": row[3],
                                "corrected_links_count": row[4],
                                "high_severity": 0,  # Will be calculated from actual issues
                                "medium_severity": 0,  # Will be calculated from actual issues
                                "low_severity": 0  # Will be calculated from actual issues
                            },
                            "issues": issues_data
                        }
                    }
                else:
                    logger.warning(f"Job not found in database for job_id: {job_id}")
                    # Check what job_ids exist in database
                    cursor.execute("SELECT job_id, article_title FROM analysis_results LIMIT 5")
                    sample_jobs = cursor.fetchall()
                    logger.info(f"Sample job_ids in database: {sample_jobs}")
                    raise HTTPException(status_code=404, detail="Analysis job not found")
            except Exception as e:
                logger.error(f"Failed to get job from database: {e}")
                raise HTTPException(status_code=404, detail="Analysis job not found")

        if job.get("status") != "completed":
            logger.warning(f"Job status is not completed: {job.get('status')}")
            raise HTTPException(status_code=400, detail="Analysis not completed")

        results = job.get("results")
        
        # Results are stored in analysis_results table, not in analysis_jobs
        if results is None:
            logger.info(f"Reading results from analysis_results table")
            try:
                cursor = database.conn.cursor()
                cursor.execute("""
                    SELECT article_title, original_content, corrected_content, 
                           dead_links_count, corrected_links_count, character_count, 
                           total_links, changes_count, analysis_date, issues_json
                    FROM analysis_results
                    WHERE job_id = ?
                    ORDER BY analysis_date DESC
                    LIMIT 1
                """, (job_id,))
                
                row = cursor.fetchone()
                if row:
                    logger.info(f"Found analysis_results for job_id: {job_id}")
                    
                    # Parse issues_json if available
                    issues_data = []
                    if row[9]:  # issues_json column
                        try:
                            issues_data = json.loads(row[9])
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse issues_json: {e}")
                    
                    results = {
                        "article_title": row[0],
                        "original_content": row[1],
                        "corrected_content": row[2],
                        "dead_links_count": row[3],
                        "corrected_links_count": row[4],
                        "character_count": row[5],
                        "total_links": row[6],
                        "changes_count": row[7],
                        "stats": {
                            "total_issues": row[3],
                            "dead_links_count": row[3],
                            "corrected_links_count": row[4],
                            "high_severity": 0,
                            "medium_severity": 0,
                            "low_severity": 0
                        },
                        "issues": issues_data
                    }
                else:
                    logger.warning(f"No analysis_results found for job_id: {job_id}")
                    results = {}
            except Exception as e:
                logger.error(f"Failed to get results from analysis_results: {e}")
                results = {}
        else:
            logger.info(f"Using results from analysis_jobs (should not happen)")
        
        logger.info(f"Results structure: dead_links_count={results.get('dead_links_count')}, issues_count={len(results.get('issues', []))}")

        # Convert issues to IssueInfo objects
        issue_infos = []
        for issue_data in results.get("issues", []):
            issue_infos.append(IssueInfo(**issue_data))

        # Calculate actual severity distribution from issues
        high_severity = sum(1 for issue in issue_infos if issue.severity == "high")
        medium_severity = sum(1 for issue in issue_infos if issue.severity == "medium")
        low_severity = sum(1 for issue in issue_infos if issue.severity == "low")

        # Update stats with actual calculated values
        stats = results.get("stats", {})
        stats.update({
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity
        })

        logger.info(f"Returning {len(issue_infos)} issues to frontend with stats: high={high_severity}, medium={medium_severity}, low={low_severity}")
        return AnalysisResultsResponse(
            success=True,
            job_id=job_id,
            article_title=results.get("article_title") or job.get("article_title") or "Unknown",
            original_content=results.get("original_content"),
            corrected_content=results.get("corrected_content"),
            issues=issue_infos,
            stats=stats,
            completed_at=job.get("completed_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")
