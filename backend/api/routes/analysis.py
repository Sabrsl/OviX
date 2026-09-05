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
        
        # Apply XML-based typography corrections if enabled (safe integration)
        try:
            from wikipedia_maintenance.utils.typography_xml_integration import apply_xml_corrections_safely
            content, xml_corrections_count, xml_was_applied = apply_xml_corrections_safely(content)
            if xml_was_applied:
                logger.info(f"XML typography corrections applied: {xml_corrections_count} corrections")
        except Exception as e:
            logger.warning(f"XML typography corrections failed (non-critical): {e}")
            # Continue without XML corrections - don't break the existing flow
        
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
        
        # Apply XML typography corrections if enabled (in AI mode)
        typo_corrections_count = 0
        try:
            from wikipedia_maintenance.analyzers import XMLTypographyAnalyzer
            from wikipedia_maintenance.utils.typography_xml_analyzer_config import TypographyXMLAnalyzerConfig
            
            xml_config = TypographyXMLAnalyzerConfig.load()
            if xml_config.enabled:
                xml_analyzer = XMLTypographyAnalyzer.from_config(xml_config)
                content, typo_corrections_count = xml_analyzer.apply_corrections(content)
                logger.info(f"XML typography analyzer in AI mode: {typo_corrections_count} typo corrections applied")
        except Exception as e:
            logger.warning(f"XML typography analyzer failed in AI mode (non-critical): {e}")
        
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
        
        # Add a single issue to track typo corrections count (AI mode)
        if typo_corrections_count > 0:
            from wikipedia_maintenance.analyzers.base import Issue
            typo_issue = Issue(
                issue_type='typo',
                description=f"Applied {typo_corrections_count} typo corrections via XML analyzer",
                position=0,
                original_text="",
                suggested_text="",
                severity='low'
            )
            issues.append(typo_issue)
        
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
        
        return content, (issues, content, page.pageid if page else 0, page.latest_revision_id if page else 0, normalization_result, typo_corrections_count)
    else:
        # Regex mode using DeadLinkAnalyzer (blocking CPU/IO)
        from wikipedia_maintenance.analyzers import DeadLinkAnalyzer
        from wikipedia_maintenance.utils.publisher import Corrector
        from wikipedia_maintenance.utils.config import load_config

        # Load config to check analyzer settings
        config = load_config()

        # Initialize content with original content for reference analyzers
        content = original_content

        # Initialize issues list
        issues = []

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
                # Still apply XML typography corrections even if dead link analysis is disabled
                typo_corrections_count = 0
                try:
                    from wikipedia_maintenance.analyzers import XMLTypographyAnalyzer
                    from wikipedia_maintenance.utils.typography_xml_analyzer_config import TypographyXMLAnalyzerConfig
                    
                    xml_config = TypographyXMLAnalyzerConfig.load()
                    if xml_config.enabled:
                        xml_analyzer = XMLTypographyAnalyzer.from_config(xml_config)
                        content, typo_corrections_count = xml_analyzer.apply_corrections(content)
                        logger.info(f"XML typography analyzer: {typo_corrections_count} typo corrections applied")
                except Exception as e:
                    logger.warning(f"XML typography analyzer failed (non-critical): {e}")
                
                # Apply new reference analyzers (independent of DeadLinkAnalyzer)
                # Apply ReferenceAnalyzer if enabled (bare URLs and duplicate references)
                logger.info(f"Checking ReferenceAnalyzer: has references={hasattr(config, 'references')}")
                if hasattr(config, 'references'):
                    logger.info(f"ReferenceAnalyzer config: check_bare_refs={config.references.check_bare_refs}, check_duplicate_refs={config.references.check_duplicate_refs}")
                
                if hasattr(config, 'references') and (config.references.check_bare_refs or config.references.check_duplicate_refs):
                    from wikipedia_maintenance.analyzers import ReferenceAnalyzer
                    try:
                        ref_analyzer = ReferenceAnalyzer()
                        ref_issues = ref_analyzer.analyze(content)
                        issues.extend(ref_issues)
                        logger.info(f"ReferenceAnalyzer applied: {len(ref_issues)} reference issues")
                    except Exception as e:
                        logger.warning(f"ReferenceAnalyzer failed: {e}")
                else:
                    logger.info("ReferenceAnalyzer disabled: config not found or both checks disabled")
                
                # Apply ReferenceValidatorAnalyzer if enabled (uppercase, ISBN, template type)
                logger.info(f"Checking ReferenceValidatorAnalyzer: has references={hasattr(config, 'references')}")
                if hasattr(config, 'references'):
                    logger.info(f"ReferenceValidatorAnalyzer config: check_uppercase_refs={config.references.check_uppercase_refs}, check_isbn_format={config.references.check_isbn_format}, check_template_type={config.references.check_template_type}")
                
                if hasattr(config, 'references') and (config.references.check_uppercase_refs or config.references.check_isbn_format or config.references.check_template_type):
                    from wikipedia_maintenance.analyzers import ReferenceValidatorAnalyzer
                    try:
                        validator_analyzer = ReferenceValidatorAnalyzer()
                        validator_issues = validator_analyzer.analyze(content)
                        issues.extend(validator_issues)
                        logger.info(f"ReferenceValidatorAnalyzer applied: {len(validator_issues)} validation issues")
                    except Exception as e:
                        logger.warning(f"ReferenceValidatorAnalyzer failed: {e}")
                else:
                    logger.info("ReferenceValidatorAnalyzer disabled: config not found or all checks disabled")
                
                # Apply BrokenLinkAnalyzer if enabled (check broken links)
                logger.info(f"Checking BrokenLinkAnalyzer: has references={hasattr(config, 'references')}")
                if hasattr(config, 'references'):
                    logger.info(f"BrokenLinkAnalyzer config: check_broken_links={config.references.check_broken_links}")
                
                if hasattr(config, 'references') and config.references.check_broken_links:
                    from wikipedia_maintenance.analyzers import BrokenLinkAnalyzer
                    try:
                        broken_link_analyzer = BrokenLinkAnalyzer()
                        broken_link_issues = broken_link_analyzer.analyze(content)
                        issues.extend(broken_link_issues)
                        logger.info(f"BrokenLinkAnalyzer applied: {len(broken_link_issues)} broken links")
                    except Exception as e:
                        logger.warning(f"BrokenLinkAnalyzer failed: {e}")
                else:
                    logger.info("BrokenLinkAnalyzer disabled: config not found or check disabled")
                
                # Apply HttpLinksAnalyzer if enabled (HTTP to HTTPS conversion)
                logger.info(f"Checking HttpLinksAnalyzer: has https_verification={hasattr(config, 'https_verification')}")
                if hasattr(config, 'https_verification'):
                    logger.info(f"HttpLinksAnalyzer config: enabled={config.https_verification.enabled}")
                
                if hasattr(config, 'https_verification') and config.https_verification.enabled:
                    from wikipedia_maintenance.analyzers import HttpLinksAnalyzer
                    try:
                        http_analyzer = HttpLinksAnalyzer()
                        http_issues = http_analyzer.analyze(content)
                        issues.extend(http_issues)
                        logger.info(f"HttpLinksAnalyzer applied: {len(http_issues)} HTTP to HTTPS conversions")
                    except Exception as e:
                        logger.warning(f"HttpLinksAnalyzer failed: {e}")
                else:
                    logger.info("HttpLinksAnalyzer disabled in config")
                
                # Apply corrections from reference analyzers
                corrector = Corrector(content)  # Re-enable strict position check
                corrected_content = corrector.apply_corrections(issues)
                
                # Log correction application results
                logger.info(f"Corrector applied {len(corrector.corrections)} corrections out of {len(issues)} issues")
                applied_count = sum(1 for c in corrector.corrections if c.applied)
                logger.info(f"Successfully applied: {applied_count}, Failed: {len(corrector.corrections) - applied_count}")
                
                # Log content comparison for debugging
                if corrected_content != content:
                    logger.info(f"Content changed after corrections: original_length={len(content)}, corrected_length={len(corrected_content)}, diff={len(corrected_content) - len(content)}")
                else:
                    logger.warning(f"Content unchanged after corrections despite {applied_count} applied corrections")
                
                # Add a single issue to track the typo corrections count
                if typo_corrections_count > 0:
                    from wikipedia_maintenance.analyzers.base import Issue
                    typo_issue = Issue(
                        issue_type='typo',
                        description=f"Applied {typo_corrections_count} typo corrections via XML analyzer",
                        position=0,
                        original_text="",
                        suggested_text="",
                        severity='low'
                    )
                    issues.append(typo_issue)
                
                return original_content, (issues, corrected_content, page.pageid if page else 0, page.latest_revision_id if page else 0, normalization_result, typo_corrections_count)
            else:
                logger.info("DeadLinkAnalyzer enabled in config, proceeding with analysis")
        else:
            logger.info("DeadLinkAnalyzer setting not found in config, defaulting to enabled")

        # Apply XML-based typography corrections if enabled (before dead link analysis)
        typo_corrections_count = 0
        typo_corrections_applied_to = "intermediate"  # Track where typo corrections were applied
        try:
            from wikipedia_maintenance.analyzers import XMLTypographyAnalyzer
            from wikipedia_maintenance.utils.typography_xml_analyzer_config import TypographyXMLAnalyzerConfig
            
            xml_config = TypographyXMLAnalyzerConfig.load()
            if xml_config.enabled:
                xml_analyzer = XMLTypographyAnalyzer.from_config(xml_config)
                content, typo_corrections_count = xml_analyzer.apply_corrections(content)
                logger.info(f"XML typography analyzer: {typo_corrections_count} typo corrections applied")
        except Exception as e:
            logger.warning(f"XML typography analyzer failed (non-critical): {e}")
            # Continue without XML corrections - don't break the existing flow

        # Phase 2: Initialize tracking service for correlation
        tracking_service = None
        try:
            db_manager = DatabaseManager()
            tracking_service = TrackingService(db_manager)
            logger.info("Phase 2: TrackingService initialized for DeadLinkAnalyzer")
        except Exception as e:
            logger.warning(f"Phase 2: Failed to initialize TrackingService: {e}")

        analyzer = DeadLinkAnalyzer(tracking_service=tracking_service)
        logger.info("Starting DeadLinkAnalyzer.analyze()")
        issues = analyzer.analyze(content)  # Blocking CPU/IO
        logger.info(f"DeadLinkAnalyzer.analyze() completed: {len(issues)} issues")
        
        # Apply new reference analyzers (independent of DeadLinkAnalyzer)
        # Apply ReferenceAnalyzer if enabled (bare URLs and duplicate references)
        logger.info(f"Checking ReferenceAnalyzer: has references={hasattr(config, 'references')}")
        if hasattr(config, 'references'):
            logger.info(f"ReferenceAnalyzer config: check_bare_refs={config.references.check_bare_refs}, check_duplicate_refs={config.references.check_duplicate_refs}")
        
        if hasattr(config, 'references') and (config.references.check_bare_refs or config.references.check_duplicate_refs):
            logger.info("Starting ReferenceAnalyzer")
            from wikipedia_maintenance.analyzers import ReferenceAnalyzer
            try:
                ref_analyzer = ReferenceAnalyzer()
                ref_issues = ref_analyzer.analyze(content)
                issues.extend(ref_issues)
                logger.info(f"ReferenceAnalyzer applied: {len(ref_issues)} reference issues")
            except Exception as e:
                logger.warning(f"ReferenceAnalyzer failed: {e}")
        else:
            logger.info("ReferenceAnalyzer disabled: config not found or both checks disabled")
        
        # Apply ReferenceValidatorAnalyzer if enabled (uppercase, ISBN, template type)
        logger.info(f"Checking ReferenceValidatorAnalyzer: has references={hasattr(config, 'references')}")
        if hasattr(config, 'references'):
            logger.info(f"ReferenceValidatorAnalyzer config: check_uppercase_refs={config.references.check_uppercase_refs}, check_isbn_format={config.references.check_isbn_format}, check_template_type={config.references.check_template_type}")
        
        if hasattr(config, 'references') and (config.references.check_uppercase_refs or config.references.check_isbn_format or config.references.check_template_type):
            logger.info("Starting ReferenceValidatorAnalyzer")
            from wikipedia_maintenance.analyzers import ReferenceValidatorAnalyzer
            try:
                validator_analyzer = ReferenceValidatorAnalyzer()
                validator_issues = validator_analyzer.analyze(content)
                issues.extend(validator_issues)
                logger.info(f"ReferenceValidatorAnalyzer applied: {len(validator_issues)} validation issues")
            except Exception as e:
                logger.warning(f"ReferenceValidatorAnalyzer failed: {e}")
        else:
            logger.info("ReferenceValidatorAnalyzer disabled: config not found or all checks disabled")
        
        # Apply BrokenLinkAnalyzer if enabled (check broken links)
        logger.info(f"Checking BrokenLinkAnalyzer: has references={hasattr(config, 'references')}")
        if hasattr(config, 'references'):
            logger.info(f"BrokenLinkAnalyzer config: check_broken_links={config.references.check_broken_links}")
        
        if hasattr(config, 'references') and config.references.check_broken_links:
            logger.info("Starting BrokenLinkAnalyzer")
            from wikipedia_maintenance.analyzers import BrokenLinkAnalyzer
            try:
                broken_link_analyzer = BrokenLinkAnalyzer()
                broken_link_issues = broken_link_analyzer.analyze(content)
                issues.extend(broken_link_issues)
                logger.info(f"BrokenLinkAnalyzer applied: {len(broken_link_issues)} broken links")
            except Exception as e:
                logger.warning(f"BrokenLinkAnalyzer failed: {e}")
        else:
            logger.info("BrokenLinkAnalyzer disabled: config not found or check disabled")
        
        # Apply HttpLinksAnalyzer if enabled (HTTP to HTTPS conversion)
        logger.info(f"Checking HttpLinksAnalyzer: has https_verification={hasattr(config, 'https_verification')}")
        if hasattr(config, 'https_verification'):
            logger.info(f"HttpLinksAnalyzer config: enabled={config.https_verification.enabled}")
        
        if hasattr(config, 'https_verification') and config.https_verification.enabled:
            logger.info("Starting HttpLinksAnalyzer")
            from wikipedia_maintenance.analyzers import HttpLinksAnalyzer
            try:
                http_analyzer = HttpLinksAnalyzer()
                http_issues = http_analyzer.analyze(content)
                issues.extend(http_issues)
                logger.info(f"HttpLinksAnalyzer applied: {len(http_issues)} HTTP to HTTPS conversions")
            except Exception as e:
                logger.warning(f"HttpLinksAnalyzer failed: {e}")
        else:
            logger.info("HttpLinksAnalyzer disabled in config")
        
        logger.info("All reference analyzers completed")
        
        # Add a single issue to track typo corrections count
        if typo_corrections_count > 0:
            from wikipedia_maintenance.analyzers.base import Issue
            typo_issue = Issue(
                issue_type='typo',
                description=f"Applied {typo_corrections_count} typo corrections via XML analyzer",
                position=0,
                original_text="",
                suggested_text="",
                severity='low'
            )
            issues.append(typo_issue)
        
        # Apply new reference analyzers (independent of DeadLinkAnalyzer)
        # Apply ReferenceAnalyzer if enabled (bare URLs and duplicate references)
        logger.info(f"Checking ReferenceAnalyzer: has references={hasattr(config, 'references')}")
        if hasattr(config, 'references'):
            logger.info(f"ReferenceAnalyzer config: check_bare_refs={config.references.check_bare_refs}, check_duplicate_refs={config.references.check_duplicate_refs}")
        
        if hasattr(config, 'references') and (config.references.check_bare_refs or config.references.check_duplicate_refs):
            from wikipedia_maintenance.analyzers import ReferenceAnalyzer
            try:
                ref_analyzer = ReferenceAnalyzer()
                ref_issues = ref_analyzer.analyze(content)
                issues.extend(ref_issues)
                logger.info(f"ReferenceAnalyzer applied: {len(ref_issues)} reference issues")
            except Exception as e:
                logger.warning(f"ReferenceAnalyzer failed: {e}")
        else:
            logger.info("ReferenceAnalyzer disabled: config not found or both checks disabled")
        
        # Apply ReferenceValidatorAnalyzer if enabled (uppercase, ISBN, template type)
        logger.info(f"Checking ReferenceValidatorAnalyzer: has references={hasattr(config, 'references')}")
        if hasattr(config, 'references'):
            logger.info(f"ReferenceValidatorAnalyzer config: check_uppercase_refs={config.references.check_uppercase_refs}, check_isbn_format={config.references.check_isbn_format}, check_template_type={config.references.check_template_type}")
        
        if hasattr(config, 'references') and (config.references.check_uppercase_refs or config.references.check_isbn_format or config.references.check_template_type):
            from wikipedia_maintenance.analyzers import ReferenceValidatorAnalyzer
            try:
                validator_analyzer = ReferenceValidatorAnalyzer()
                validator_issues = validator_analyzer.analyze(content)
                issues.extend(validator_issues)
                logger.info(f"ReferenceValidatorAnalyzer applied: {len(validator_issues)} validation issues")
            except Exception as e:
                logger.warning(f"ReferenceValidatorAnalyzer failed: {e}")
        else:
            logger.info("ReferenceValidatorAnalyzer disabled: config not found or all checks disabled")
        
        # Apply BrokenLinkAnalyzer if enabled (check broken links)
        logger.info(f"Checking BrokenLinkAnalyzer: has references={hasattr(config, 'references')}")
        if hasattr(config, 'references'):
            logger.info(f"BrokenLinkAnalyzer config: check_broken_links={config.references.check_broken_links}")
        
        if hasattr(config, 'references') and config.references.check_broken_links:
            from wikipedia_maintenance.analyzers import BrokenLinkAnalyzer
            try:
                broken_link_analyzer = BrokenLinkAnalyzer()
                broken_link_issues = broken_link_analyzer.analyze(content)
                issues.extend(broken_link_issues)
                logger.info(f"BrokenLinkAnalyzer applied: {len(broken_link_issues)} broken links")
            except Exception as e:
                logger.warning(f"BrokenLinkAnalyzer failed: {e}")
        else:
            logger.info("BrokenLinkAnalyzer disabled: config not found or check disabled")
        
        # Apply HttpLinksAnalyzer if enabled (HTTP to HTTPS conversion)
        logger.info(f"Checking HttpLinksAnalyzer: has https_verification={hasattr(config, 'https_verification')}")
        if hasattr(config, 'https_verification'):
            logger.info(f"HttpLinksAnalyzer config: enabled={config.https_verification.enabled}")
        
        if hasattr(config, 'https_verification') and config.https_verification.enabled:
            from wikipedia_maintenance.analyzers import HttpLinksAnalyzer
            try:
                http_analyzer = HttpLinksAnalyzer()
                http_issues = http_analyzer.analyze(content)
                issues.extend(http_issues)
                logger.info(f"HttpLinksAnalyzer applied: {len(http_issues)} HTTP to HTTPS conversions")
            except Exception as e:
                logger.warning(f"HttpLinksAnalyzer failed: {e}")
        else:
            logger.info("HttpLinksAnalyzer disabled in config")
        
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
            return None, (None, None, None, None, normalization_result, 0)
        
        # Generate corrected content (blocking CPU)
        corrector = Corrector(content)
        corrected_content = corrector.apply_corrections(issues)
        
        # Log correction application results
        logger.info(f"Corrector applied {len(corrector.corrections)} corrections out of {len(issues)} issues")
        applied_count = sum(1 for c in corrector.corrections if c.applied)
        logger.info(f"Successfully applied: {applied_count}, Failed: {len(corrector.corrections) - applied_count}")
        
        # Log content comparison for debugging
        if corrected_content != content:
            logger.info(f"Content changed after corrections: original_length={len(content)}, corrected_length={len(corrected_content)}, diff={len(corrected_content) - len(content)}")
        else:
            logger.warning(f"Content unchanged after corrections despite {applied_count} applied corrections")
        
        # Re-apply typo corrections to the final corrected content to ensure they are preserved
        # This ensures typo corrections don't get lost during the corrector's transformations
        if typo_corrections_count > 0:
            try:
                from wikipedia_maintenance.analyzers import XMLTypographyAnalyzer
                from wikipedia_maintenance.utils.typography_xml_analyzer_config import TypographyXMLAnalyzerConfig
                
                xml_config = TypographyXMLAnalyzerConfig.load()
                if xml_config.enabled:
                    xml_analyzer = XMLTypographyAnalyzer.from_config(xml_config)
                    corrected_content, final_typo_count = xml_analyzer.apply_corrections(corrected_content)
                    logger.info(f"Re-applied typo corrections to final content: {final_typo_count} corrections")
                    typo_corrections_count = final_typo_count
            except Exception as e:
                logger.warning(f"Failed to re-apply typo corrections to final content: {e}")

        return original_content, (issues, corrected_content, page.pageid, page.latest_revision_id, normalization_result, typo_corrections_count)


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
        # Load config to capture analysis parameters
        from wikipedia_maintenance.utils.config import load_config
        config = load_config()
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
            issues, corrected_content, page_id, revision_id, normalization_result, typo_corrections_count = analysis_result
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
            issues, corrected_content, page_id, revision_id, normalization_result, typo_corrections_count = analysis_result
        
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
            # Include both REVIEW_REQUIRED status and medium severity issues
            if issue.extra and issue.extra.get('repair_status') == 'REVIEW_REQUIRED':
                url = issue.extra.get('url') or issue.original_text
                if url:
                    manual_review_urls.append(url)
            elif issue.severity == 'medium':
                # Medium severity issues also require manual review
                url = getattr(issue, 'url', None) or issue.original_text
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

        # Count dead links corrected (only dead link repairs, not enrichments)
        dead_links_corrected_count = 0
        
        # Count enrichments (reference enrichments only)
        enrichment_count = 0
        
        # Count corrections by analyzer type
        stats_by_analyzer = {
            "bare_refs": 0,
            "duplicate_refs": 0,
            "uppercase_refs": 0,
            "isbn_format": 0,
            "template_type": 0,
            "broken_links": 0,
            "https_conversions": 0,
            "enrichments": 0,
            "manual_review": 0  # Issues without suggested_text
        }
        
        try:
            # Count dead link repairs
            dead_link_repair_statuses = [
                'REPAIR_APPLIED', 'SAFE_REPLACEMENT', 'ARCHIVE_ONLY_REPAIR'
            ]
            
            # Count enrichments
            enrichment_statuses = [
                'ENRICHMENT_APPLIED', 'BARE_URL_ENRICHMENT_APPLIED'
            ]
            
            # Count reference analyzer corrections
            reference_analyzer_types = [
                'bare_url', 'duplicate_reference', 'uppercase_parameter', 
                'invalid_isbn', 'template_type_mismatch', 'broken_link'
            ]
            
            for i in issues:
                # Count all issues by type (regardless of suggested_text)
                if i.issue_type == 'bare_url':
                    stats_by_analyzer["bare_refs"] += 1
                elif i.issue_type == 'duplicate_reference':
                    stats_by_analyzer["duplicate_refs"] += 1
                elif i.issue_type == 'uppercase_parameter':
                    stats_by_analyzer["uppercase_refs"] += 1
                elif i.issue_type == 'invalid_isbn':
                    stats_by_analyzer["isbn_format"] += 1
                elif i.issue_type == 'template_type_mismatch':
                    stats_by_analyzer["template_type"] += 1
                elif i.issue_type == 'broken_link':
                    stats_by_analyzer["broken_links"] += 1
                elif i.issue_type == 'http_link':
                    stats_by_analyzer["https_conversions"] += 1
                elif 'reference_enrichment' in i.issue_type.lower():
                    stats_by_analyzer["enrichments"] += 1
                
                # Count manual review items (issues without suggested_text)
                if not i.suggested_text:
                    stats_by_analyzer["manual_review"] += 1
                    continue  # Skip for corrected_links_count
                    
                if i.extra and i.extra.get('repair_status') in dead_link_repair_statuses:
                    if 'dead' in i.issue_type.lower():
                        dead_links_corrected_count += 1
                elif i.extra and i.extra.get('repair_status') in enrichment_statuses:
                    if 'reference_enrichment' in i.issue_type.lower():
                        enrichment_count += 1
                # Count new reference analyzer corrections
                elif i.issue_type in reference_analyzer_types:
                    enrichment_count += 1
                # Count HTTP to HTTPS conversions
                elif i.issue_type == 'http_link':
                    enrichment_count += 1
            
            logger.info(f"Dead links corrected: {dead_links_corrected_count}, Enrichments: {enrichment_count}")
            logger.info(f"Stats by analyzer: {stats_by_analyzer}")
            
        except Exception as e:
            logger.warning(f"Failed to count corrections via repair statuses: {e}")
            # Simple fallback counting
            for i in issues:
                # Count all issues by type (regardless of suggested_text)
                if i.issue_type == 'bare_url':
                    stats_by_analyzer["bare_refs"] += 1
                elif i.issue_type == 'duplicate_reference':
                    stats_by_analyzer["duplicate_refs"] += 1
                elif i.issue_type == 'uppercase_parameter':
                    stats_by_analyzer["uppercase_refs"] += 1
                elif i.issue_type == 'invalid_isbn':
                    stats_by_analyzer["isbn_format"] += 1
                elif i.issue_type == 'template_type_mismatch':
                    stats_by_analyzer["template_type"] += 1
                elif i.issue_type == 'broken_link':
                    stats_by_analyzer["broken_links"] += 1
                elif i.issue_type == 'http_link':
                    stats_by_analyzer["https_conversions"] += 1
                elif 'reference_enrichment' in i.issue_type.lower():
                    stats_by_analyzer["enrichments"] += 1
                
                # Count manual review items (issues without suggested_text)
                if not i.suggested_text:
                    stats_by_analyzer["manual_review"] += 1
                    continue
                    
                if 'dead' in i.issue_type.lower():
                    dead_links_corrected_count += 1
                elif 'reference_enrichment' in i.issue_type.lower():
                    enrichment_count += 1
                # Count new reference analyzer corrections in fallback
                elif i.issue_type in ['bare_url', 'duplicate_reference', 'uppercase_parameter', 'invalid_isbn', 'template_type_mismatch', 'broken_link', 'http_link']:
                    enrichment_count += 1

        # For backward compatibility, corrected_links_count = dead_links_corrected_count + enrichment_count
        corrected_links_count = dead_links_corrected_count + enrichment_count
        
        # Build stats dictionary with detailed breakdown
        stats = {
            "total_links": total_links,
            "dead_links_count": dead_links_count,
            "dead_links_corrected_count": dead_links_corrected_count,
            "corrected_links_count": corrected_links_count,
            "enrichment_count": enrichment_count,
            "character_count": len(original_content) if original_content else 0,
            "changes_count": len(issues),
            "stats_by_analyzer": stats_by_analyzer
        }
        
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
        
        # Build analysis config used (analyzers that were enabled during analysis)
        analysis_config_used = {}
        
        # Capture analysis configuration - only if enabled
        if hasattr(config, 'analysis'):
            if hasattr(config.analysis, 'enable_dead_link_analyzer') and config.analysis.enable_dead_link_analyzer:
                analysis_config_used['enable_dead_link_analyzer'] = True
            if hasattr(config.analysis, 'enable_case_normalization') and config.analysis.enable_case_normalization:
                analysis_config_used['enable_case_normalization'] = True
            if hasattr(config.analysis, 'normalize_with_ai') and config.analysis.normalize_with_ai:
                analysis_config_used['normalize_with_ai'] = True
        
        # Capture reference enricher configuration - only if enabled
        if hasattr(config, 'reference_enricher_analyzer'):
            if hasattr(config.reference_enricher_analyzer, 'enabled') and config.reference_enricher_analyzer.enabled:
                analysis_config_used['reference_enricher_analyzer'] = True
        
        # Capture HTTPS verification configuration - only if enabled
        if hasattr(config, 'https_verification'):
            if hasattr(config.https_verification, 'enabled') and config.https_verification.enabled:
                analysis_config_used['https_verification'] = True
        
        # Capture references configuration - only if enabled
        if hasattr(config, 'references'):
            if hasattr(config.references, 'use_wayback_api') and config.references.use_wayback_api:
                analysis_config_used['use_wayback_api'] = True
            if hasattr(config.references, 'check_bare_refs') and config.references.check_bare_refs:
                analysis_config_used['check_bare_refs'] = True
            if hasattr(config.references, 'check_duplicate_refs') and config.references.check_duplicate_refs:
                analysis_config_used['check_duplicate_refs'] = True
        
        # Add mode
        analysis_config_used['mode'] = mode
        
        analyzers_status_json = json.dumps(analysis_config_used)
        
        # Count typo corrections from issues
        # Note: typo corrections are tracked via typo_corrections_count variable, not via individual issues
        # The XML analyzer creates a single summary issue for all typo corrections
        typo_issues = [issue for issue in issues if issue.issue_type == 'typo']
        if typo_issues:
            # Extract the actual count from the description if it's a summary issue
            for issue in typo_issues:
                if issue.description and "typo corrections" in issue.description:
                    import re
                    match = re.search(r'Applied (\d+) typo corrections', issue.description)
                    if match:
                        typo_corrections_count = int(match.group(1))
                        break
        else:
            typo_corrections_count = 0
        
        # Clean up any incomplete analysis results for this article before storing new result
        try:
            cursor = db.conn.cursor()
            cursor.execute("""
                DELETE FROM analysis_results 
                WHERE article_title = ? 
                AND status IN ('analyzing', 'running', 'cancelled', 'paused')
            """, (article_title,))
            db.conn.commit()
            logger.info(f"Cleaned up incomplete analysis results for article '{article_title}'")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up incomplete analysis results: {cleanup_error}")
        
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
            normalization_reports=normalization_reports_json,
            analyzers_status=analyzers_status_json,
            typo_corrections_count=typo_corrections_count,
            stats_by_analyzer=json.dumps(stats_by_analyzer)  # Store detailed analyzer stats
        )

        # Update article status in articles_to_analyze table to 'analyzed'
        try:
            cursor = db.conn.cursor()
            cursor.execute("""
                UPDATE articles_to_analyze
                SET status = 'analyzed'
                WHERE title = ?
            """, (article_title,))
            db.conn.commit()
            logger.info(f"Updated status to 'analyzed' for article {article_title} in articles_to_analyze table")
        except Exception as update_error:
            logger.warning(f"Failed to update status in articles_to_analyze table: {update_error}")
            # Non-critical error, continue

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
                analysis_date=datetime.now().isoformat(),
                analyzers_status=json.dumps({"mode": mode, "error": "failed"})
            )
            logger.info(f"Stored failed analysis result for {article_title} in database")
            
            # Update article status in articles_to_analyze table to 'error' on error
            try:
                cursor = db.conn.cursor()
                cursor.execute("""
                    UPDATE articles_to_analyze
                    SET status = 'error'
                    WHERE title = ?
                """, (article_title,))
                db.conn.commit()
                logger.info(f"Set status to 'error' for article {article_title} in articles_to_analyze table after error")
            except Exception as update_error:
                logger.warning(f"Failed to update status in articles_to_analyze table: {update_error}")
                # Non-critical error, continue
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
                           total_links, changes_count, analysis_date, issues_json,
                           stats_by_analyzer
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
                    
                    # Parse stats_by_analyzer if available
                    stats_by_analyzer = {}
                    if len(row) > 10 and row[10]:  # stats_by_analyzer column
                        try:
                            stats_by_analyzer = json.loads(row[10])
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse stats_by_analyzer: {e}")
                    
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
                                "low_severity": 0,  # Will be calculated from actual issues
                                "stats_by_analyzer": stats_by_analyzer
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
