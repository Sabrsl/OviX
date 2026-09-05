"""
OVIX Backend API - Publication Routes

Handles article publication using the existing Publisher.
"""

import logging
import uuid
import os
import asyncio
import json
from typing import Optional, Dict, Any, Union
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime

# Import AnalysisStatus for updating analyzed tracker
from wikipedia_maintenance.utils.analyzed_tracker import AnalysisStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class PublicationValidationRequest(BaseModel):
    """Publication validation request."""
    article_title: str
    corrected_content: str
    original_content: str = ""  # Optional, will be fetched if needed
    summary: str
    dry_run: bool = True


class PublicationRequest(BaseModel):
    """Publication request."""
    article_title: str
    corrected_content: str
    original_content: str = ""  # Optional, will be fetched if needed
    summary: str
    dry_run: bool = True


class PublicationResponse(BaseModel):
    """Publication response."""
    success: bool
    publication_id: str
    status: str
    message: str


class PublicationStatusResponse(BaseModel):
    """Publication status response."""
    publication_id: str
    status: str
    message: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    revision_id: Optional[Union[int, str]] = None  # Accept both int and str for backward compatibility
    diff: Optional[str] = None


# ============================================================================
# Publication Job Management
# ============================================================================

# In-memory publication job storage
_publication_jobs: Dict[str, Dict[str, Any]] = {}


def create_publication_job(article_title: str, dry_run: bool) -> str:
    """Create a new publication job."""
    publication_id = str(uuid.uuid4())
    
    _publication_jobs[publication_id] = {
        "id": publication_id,
        "article_title": article_title,
        "dry_run": dry_run,
        "status": "pending",
        "message": "Publication queued",
        "started_at": None,
        "completed_at": None,
        "error": None,
        "revision_id": None,
        "diff": None
    }
    
    return publication_id


def update_publication_job(publication_id: str, **kwargs):
    """Update publication job status."""
    if publication_id in _publication_jobs:
        _publication_jobs[publication_id].update(kwargs)


def get_publication_job(publication_id: str) -> Optional[Dict[str, Any]]:
    """Get publication job."""
    return _publication_jobs.get(publication_id)


# ============================================================================
# Dependencies
# ============================================================================

def get_wikipedia_session():
    """Get current Wikipedia session."""
    from backend.api.routes.auth import get_wikipedia_session as get_session
    return get_session()


def get_kill_switch():
    """Get kill switch manager."""
    try:
        from backend.api.main import get_kill_switch
        return get_kill_switch()
    except Exception as e:
        logger.warning(f"Kill switch manager not available: {e}")
        return None


def get_published_tracker():
    """Get published tracker."""
    from backend.api.main import get_published_tracker
    return get_published_tracker()


def get_database():
    """Get database."""
    try:
        from backend.api.main import get_database
        return get_database()
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        return None


def get_analyzed_tracker():
    """Get analyzed tracker."""
    from backend.api.main import get_analyzed_tracker
    return get_analyzed_tracker()


# ============================================================================
# Publication Worker
# ============================================================================

async def run_publication_worker(
    publication_id: str,
    article_title: str,
    corrected_content: str,
    summary: str,
    dry_run: bool,
    original_content: str,
    publisher
):
    """
    Background worker to run publication.
    
    This function uses the existing Publisher to publish the article
    while respecting all safety checks (Kill Switch, throttling, etc.).
    """
    try:
        # Update job status
        update_publication_job(
            publication_id,
            status="running",
            message="Starting publication",
            started_at=datetime.now().isoformat()
        )
        
        # Check Kill Switch BEFORE publication
        kill_switch = get_kill_switch()
        if kill_switch and kill_switch.is_enabled():
            state = kill_switch.get_state()
            raise Exception(
                f"Publication blocked: Kill switch enabled. "
                f"Reason: {state.reason}, Source: {state.trigger_source}"
            )
        
        # Update publisher settings
        publisher.set_dry_run(dry_run)
        
        # Generate detailed edit summary with URL mapping for dead links
        try:
            import re
            import yaml
            from pathlib import Path
            
            # Load site names from case_normalization_data.yaml (includes Wikipedia internal links for archive sites)
            site_names = {}
            try:
                config_path = Path(__file__).parent.parent.parent.parent / "config" / "case_normalization_data.yaml"
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    if config_data and 'domain_to_site_name' in config_data:
                        # Extract the site names from the YAML format
                        # YAML format: "domain.com: [[Site Name]]" -> we want "domain.com": "[[Site Name]]"
                        for domain, wiki_links in config_data['domain_to_site_name'].items():
                            if wiki_links and isinstance(wiki_links, list) and len(wiki_links) > 0:
                                site_names[domain] = wiki_links[0]
            except Exception as e:
                logger.warning(f"Could not load site names from config: {e}")
            
            # Extract dead link replacements from the diff
            dead_link_mapping = []
            error_codes = set()
            
            # Find all archive URLs (web.archive.org, wikiwix, arquivo.pt, etc.) with full original URL
            archive_patterns = [
                (r'https://web\.archive\.org/web/(\d+)/(https?://[^\s\)]+)', 'web.archive.org'),
                (r'https://wikiwix\.cache/([^/]+)/([^/]+)', 'wikiwix'),
                (r'https://arquivo\.pt/wayback/(\d+)/https?://([^\s\)]+)', 'arquivo.pt'),
                (r'https://webcache\.googleusercontent\.com/search\?q=cache:([^\s:]+):([^\s\)]+)', 'webcache.googleusercontent.com')
            ]
            
            archive_matches = []
            for pattern, provider in archive_patterns:
                matches = re.findall(pattern, corrected_content)
                for match in matches:
                    if provider == 'web.archive.org':
                        archive_matches.append((match[0], match[1], provider))
                    elif provider == 'wikiwix':
                        # wikiwix format: (timestamp, domain)
                        archive_matches.append((match[0], f"http://{match[1]}", provider))
                    elif provider == 'arquivo.pt':
                        # arquivo.pt format: (timestamp, url)
                        archive_matches.append((match[0], match[1], provider))
                    elif provider == 'webcache.googleusercontent.com':
                        # Google cache format: (cache_id, url)
                        archive_matches.append((match[0], match[1], provider))
            
            # Check if these are NEW archive URLs (dead link replacements)
            # by comparing with original content
            original_archive_matches = []
            if original_content:
                for pattern, provider in archive_patterns:
                    matches = re.findall(pattern, original_content)
                    for match in matches:
                        if provider == 'web.archive.org':
                            original_archive_matches.append((match[0], match[1], provider))
                        elif provider == 'wikiwix':
                            original_archive_matches.append((match[0], f"http://{match[1]}", provider))
                        elif provider == 'arquivo.pt':
                            original_archive_matches.append((match[0], match[1], provider))
                        elif provider == 'webcache.googleusercontent.com':
                            original_archive_matches.append((match[0], match[1], provider))
            new_archive_urls = len(archive_matches) - len(original_archive_matches)
            
            # Only process NEW archive URLs (dead link replacements)
            # Convert to sets for easier comparison
            archive_set = set(archive_matches)
            original_set = set(original_archive_matches)
            new_matches = archive_set - original_set
            
            # Extract dead link replacements with domain only (keep summary short)
            for timestamp, original_url, provider in new_matches:
                # Format timestamp as readable date (YYYYMMDDHHMMSS -> DD/MM/YYYY)
                try:
                    if len(timestamp) >= 8:
                        readable_date = f"{timestamp[6:8]}/{timestamp[4:6]}/{timestamp[:4]}"
                    else:
                        readable_date = timestamp
                except:
                    readable_date = timestamp
                
                # Extract domain only (no path to keep summary short)
                from urllib.parse import urlparse
                parsed = urlparse(original_url)
                clean_domain = parsed.netloc.replace('www.', '')
                
                logger.info(f"Processing dead link: original_url={original_url}, clean_domain={clean_domain}, provider={provider}")
                
                # If the original URL is itself an archive URL (nested archive), extract the actual dead domain
                # e.g., web.archive.org/web/2022/https://web.archive.org/web/2010/https://example.com
                # We want to extract "example.com" as the actual dead domain
                if clean_domain in ['web.archive.org', 'wikiwix.com', 'arquivo.pt', 'webcache.googleusercontent.com']:
                    # Try to extract the actual dead domain from nested archive URL
                    # Handle multiple levels of nesting by repeatedly stripping archive prefixes
                    current_url = original_url
                    max_depth = 5  # Prevent infinite loops
                    depth = 0
                    found_non_archive = False
                    
                    while depth < max_depth:
                        # Try to strip archive prefix and get the inner URL
                        # Pattern for web.archive.org: web.archive.org/web/TIMESTAMP/INNER_URL
                        web_archive_match = re.search(r'web\.archive\.org/web/\d{8,14}/(https?://[^\s\)]+)', current_url)
                        if web_archive_match:
                            current_url = web_archive_match.group(1)
                            logger.info(f"Stripped web.archive.org prefix (depth={depth}): {current_url}")
                            depth += 1
                            continue
                        
                        # Pattern for wikiwix: wikiwix.cache/TIMESTAMP/DOMAIN
                        wikiwix_match = re.search(r'wikiwix\.cache/\d+/([^/]+)', current_url)
                        if wikiwix_match:
                            current_url = f"http://{wikiwix_match.group(1)}"
                            logger.info(f"Stripped wikiwix prefix (depth={depth}): {current_url}")
                            depth += 1
                            continue
                        
                        # Pattern for arquivo.pt: arquivo.pt/wayback/TIMESTAMP/INNER_URL
                        arquivo_match = re.search(r'arquivo\.pt/wayback/\d+/(https?://[^\s\)]+)', current_url)
                        if arquivo_match:
                            current_url = arquivo_match.group(1)
                            logger.info(f"Stripped arquivo.pt prefix (depth={depth}): {current_url}")
                            depth += 1
                            continue
                        
                        # Pattern for webcache: webcache.googleusercontent.com/search?q=cache:ID:INNER_URL
                        webcache_match = re.search(r'webcache\.googleusercontent\.com/search\?q=cache:[^:]+:(https?://[^\s\)]+)', current_url)
                        if webcache_match:
                            current_url = webcache_match.group(1)
                            logger.info(f"Stripped webcache prefix (depth={depth}): {current_url}")
                            depth += 1
                            continue
                        
                        # No more archive prefixes found
                        logger.info(f"No more archive prefixes at depth {depth}, current_url={current_url}")
                        break
                    
                    # Parse the final URL to get the domain
                    final_parsed = urlparse(current_url)
                    final_domain = final_parsed.netloc.replace('www.', '')
                    
                    # If we found a non-archive domain, use it
                    if final_domain not in ['web.archive.org', 'wikiwix.com', 'arquivo.pt', 'webcache.googleusercontent.com']:
                        clean_domain = final_domain
                        logger.info(f"Successfully extracted dead domain: {clean_domain}")
                    else:
                        logger.warning(f"Still got archive domain after unwrapping: {final_domain}, original_url={original_url}")
                        # In this case, just show the archive name without the dead site
                        dead_link_mapping.append(f"{site_names.get(provider, provider)} ({readable_date})")
                        continue
                
                # Use site name from config if available (includes Wikipedia internal links for archive sites)
                # Otherwise use provider name
                dead_site_name = site_names.get(clean_domain, clean_domain)
                
                # Extract the archive URL with timestamp for the summary using existing archive_patterns
                # Reuse the same patterns defined above for consistency
                archive_url_with_timestamp = None
                for pattern, pattern_provider in archive_patterns:
                    if pattern_provider == provider:
                        match = re.search(pattern, original_url)
                        if match:
                            # Extract the timestamp/ID from the match
                            # For web.archive.org: group(0) is full match, group(1) is timestamp
                            # Build a concise archive URL with timestamp in format web.archive.org/web/TIMESTAMP
                            if provider == 'web.archive.org':
                                archive_url_with_timestamp = f"web.archive.org/web/{match.group(1)}"
                            elif provider == 'wikiwix':
                                archive_url_with_timestamp = f"wikiwix.cache/{match.group(1)}"
                            elif provider == 'arquivo.pt':
                                archive_url_with_timestamp = f"arquivo.pt/wayback/{match.group(1)}"
                            elif provider == 'webcache.googleusercontent.com':
                                archive_url_with_timestamp = f"webcache.googleusercontent.com/{match.group(1)}"
                            break
                
                # Fallback to provider name if we couldn't extract timestamp
                if not archive_url_with_timestamp:
                    archive_url_with_timestamp = site_names.get(provider, provider)
                
                logger.info(f"Dead link mapping: dead_site={dead_site_name}, archive_url={archive_url_with_timestamp}, clean_domain={clean_domain}, original_url={original_url}")
                
                # Format: dead_site → archive_url_with_timestamp (timestamp)
                # Use the timestamp from the archive URL instead of formatted date
                # If both are the same (e.g., archive replacement), show only once
                if dead_site_name == archive_url_with_timestamp:
                    dead_link_mapping.append(f"{archive_url_with_timestamp}")
                else:
                    dead_link_mapping.append(f"{dead_site_name} → {archive_url_with_timestamp}")
                
                # Limit to 2 dead link mappings for summary
                if len(dead_link_mapping) >= 2:
                    break
            
            # Extract HTTP error codes from original content if available
            if original_content:
                # Look for common HTTP error codes mentioned in comments or context
                error_pattern = r'(?:HTTP\s*|status\s*|error\s*)[\'":\s]*(40[0-9]|41[0-9]|50[0-9])'
                error_matches = re.findall(error_pattern, original_content, re.IGNORECASE)
                error_codes.update(error_matches)
            
            # Default error codes if none found
            if not error_codes:
                error_codes = {'404', '410'}  # Common dead link codes
            
            # Detect reference enrichments (site and consulté le additions)
            enrichment_mapping = []
            if original_content and corrected_content:
                # Find all reference templates with URLs (more flexible pattern)
                # Matches: {{Lien web|url=...}}, {{Lien web|titre=...|url=...}}, etc.
                template_pattern = r'\{\{[^}]+\|url\s*=\s*(https?://[^\s|\}]+)[^}]*\}\}'
                templates = re.findall(template_pattern, corrected_content, re.IGNORECASE)
                
                for url in templates[:2]:  # Limit to 2 URLs
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    domain = parsed.netloc.replace('www.', '')
                    
                    # Find the template containing this URL
                    template_match = re.search(r'\{\{[^}]*' + re.escape(url) + r'[^}]*\}\}', corrected_content, re.IGNORECASE)
                    if not template_match:
                        continue
                    
                    template = template_match.group(0)
                    
                    # Check if this template was modified (not in original or different)
                    original_template_match = re.search(r'\{\{[^}]*' + re.escape(url) + r'[^}]*\}\}', original_content, re.IGNORECASE)
                    
                    mapping_parts = []
                    
                    # Check for site parameter
                    site_match = re.search(r'\|\s*site\s*=\s*([^|\}]+)', template, re.IGNORECASE)
                    if site_match:
                        site_value = site_match.group(1).strip()
                        # Check if site is new
                        if not original_template_match or not re.search(r'\|\s*site\s*=', original_template_match.group(0), re.IGNORECASE):
                            mapping_parts.append(f"ajouté site : {site_value}")
                    
                    # Check for consulté le parameter
                    consulte_match = re.search(r'\|\s*consulté le\s*=\s*([^|\}]+)', template, re.IGNORECASE)
                    if consulte_match:
                        consulte_value = consulte_match.group(1).strip()
                        # Check if consulté le is new
                        if not original_template_match or not re.search(r'\|\s*consulté le\s*=', original_template_match.group(0), re.IGNORECASE):
                            mapping_parts.append(f"consulté le {consulte_value}")
                    
                    if mapping_parts:
                        # Format: ajouté site : xxxx - consulté le xxxxx
                        enrichment_mapping.append(" - ".join(mapping_parts))
                    # Si on ne peut pas extraire les valeurs exactes, on ne met rien
                
                # Also check for bare URL conversions (new templates that didn't exist before)
                # Find all {{Lien web}} templates in corrected content
                lien_web_pattern = r'\{\{Lien web[^}]*\}\}'
                lien_web_templates = re.findall(lien_web_pattern, corrected_content, re.IGNORECASE)
                
                for template in lien_web_templates[:5]:
                    # Check if this template exists in original content
                    if not re.search(re.escape(template), original_content, re.IGNORECASE):
                        # This is a new template (likely from bare URL conversion)
                        mapping_parts = []
                        
                        # Check for site parameter
                        site_match = re.search(r'\|\s*site\s*=\s*([^|\}]+)', template, re.IGNORECASE)
                        if site_match:
                            site_value = site_match.group(1).strip()
                            mapping_parts.append(f"ajouté site : {site_value}")
                        
                        # Check for consulté le parameter
                        consulte_match = re.search(r'\|\s*consulté le\s*=\s*([^|\}]+)', template, re.IGNORECASE)
                        if consulte_match:
                            consulte_value = consulte_match.group(1).strip()
                            mapping_parts.append(f"consulté le {consulte_value}")
                        
                        if mapping_parts:
                            enrichment_mapping.append(" - ".join(mapping_parts))
                
                if len(enrichment_mapping) > 2:
                    enrichment_mapping = enrichment_mapping[:2]
                    enrichment_mapping.append("...")
            
            # Detect correction type by comparing original vs corrected content
            correction_types = []
            
            # Check for dead link replacements (new archive URLs)
            if new_archive_urls > 0:
                correction_types.extend(['dead_link'] * new_archive_urls)
            
            # Check for reference enrichments
            if enrichment_mapping:
                correction_types.append('reference_enrichment')
            
            # Check for case normalization (case changes without URL changes)
            if original_content and corrected_content:
                # Simple heuristic: if content is similar but case differs
                if original_content.lower() == corrected_content.lower():
                    # Only case changed
                    correction_types.append('case_normalization')
                elif corrected_content != original_content and new_archive_urls == 0 and not enrichment_mapping:
                    # Content changed but no new archive URLs or enrichments
                    correction_types.append('correction')
            
            # Use centralized summary generation system with detailed corrections info
            # The system automatically handles dead links, enrichments, case normalization, etc.
            
            # Determine which corrections are present
            has_dead_links = 'dead_link' in correction_types and dead_link_mapping
            has_enrichment = 'reference_enrichment' in correction_types and enrichment_mapping
            
            # Case 1: Only dead links
            if has_dead_links and not has_enrichment:
                base_summary = publisher.generate_edit_summary(
                    num_corrections=len(dead_link_mapping),
                    correction_types=['dead_link']
                )
                links_str = ", ".join([f"{m}" for m in dead_link_mapping[:2]])
                if len(dead_link_mapping) > 2:
                    links_str += "..."
                summary = f"{base_summary} : {links_str}"
                logger.info(f"Generated dead link summary: {summary}")
            
            # Case 2: Only enrichment
            elif has_enrichment and not has_dead_links:
                from wikipedia_maintenance.utils.edit_summaries import REFERENCE_ENRICHMENT_EDIT_SUMMARIES, get_random_summary
                base_summary = get_random_summary(REFERENCE_ENRICHMENT_EDIT_SUMMARIES)
                enrichment_str = ", ".join([f"{m}" for m in enrichment_mapping[:2]])
                if len(enrichment_mapping) > 2:
                    enrichment_str += "..."
                summary = f"{base_summary} : {enrichment_str}"
                logger.info(f"Generated enrichment summary: {summary}")
            
            # Case 3: Both dead links and enrichment (mixed)
            elif has_dead_links and has_enrichment:
                # Use dead link base summary (includes "Vérifiabilité (OviX)")
                dead_base = publisher.generate_edit_summary(
                    num_corrections=len(dead_link_mapping),
                    correction_types=['dead_link']
                )
                links_str = ", ".join([f"{m}" for m in dead_link_mapping[:2]])
                if len(dead_link_mapping) > 2:
                    links_str += "..."
                dead_link_part = f"{dead_base} : {links_str}"
                
                # Add enrichment without repeating "Vérifiabilité (OviX)"
                enrichment_str = ", ".join([f"{m}" for m in enrichment_mapping[:2]])
                if len(enrichment_mapping) > 2:
                    enrichment_str += "..."
                enrichment_part = f"enrichissement réf : {enrichment_str}"
                
                # Combine with single "Vérifiabilité (OviX)"
                summary = f"{dead_link_part} ; {enrichment_part}"
                logger.info(f"Generated mixed summary: {summary}")
            
            # Case 4: Other corrections (fallback)
            else:
                professional_summary = publisher.generate_edit_summary(
                    num_corrections=1,
                    correction_types=correction_types if correction_types else ['correction']
                )
                summary = professional_summary
                logger.info(f"Generated standard summary: {summary}")
                
        except Exception as e:
            logger.warning(f"Could not generate detailed summary, using provided: {e}")
            # Use provided summary as fallback
        
        # Perform publication
        update_publication_job(
            publication_id,
            message="Publishing to Wikipedia"
        )
        
        success, revision_id = publisher.publish(
            page_title=article_title,
            content=corrected_content,
            summary=summary
        )

        if not success:
            # Check if blocked by kill switch or talk page STOP
            error_msg = str(revision_id)
            if "STOP command" in error_msg or "kill switch" in error_msg.lower():
                logger.error(f"Publication blocked by security mechanism: {error_msg}")
                raise Exception(f"Publication bloquée par le système de sécurité: {error_msg}")
            raise Exception(f"Publication failed: {revision_id}")
        
        # Track publication
        published_tracker = get_published_tracker()
        if published_tracker:
            published_tracker.mark_as_published(
                article_title=article_title,
                category="unknown",
                mode="api",
                summary=summary,
                revision_id=int(revision_id) if revision_id.isdigit() else None
            )

        # Update database status to published
        database = get_database()
        if database:
            try:
                cursor = database.conn.cursor()
                
                # Clean up any incomplete analysis results for this article before updating status
                cursor.execute("""
                    DELETE FROM analysis_results 
                    WHERE article_title = ? 
                    AND status IN ('analyzing', 'running', 'cancelled', 'paused')
                """, (article_title,))
                
                cursor.execute("""
                    UPDATE analysis_results 
                    SET status = 'published',
                        revision_id = ?,
                        summary = ?,
                        published_at = ?,
                        human_verified = 1
                    WHERE article_title = ?
                """, (
                    int(revision_id) if revision_id.isdigit() else None,
                    summary,
                    datetime.now().isoformat(),
                    article_title
                ))
                database.conn.commit()
                logger.info(f"Updated database status to 'published' for article '{article_title}'")
            except Exception as e:
                logger.error(f"Failed to update database for article '{article_title}': {e}")

        # Update analyzed tracker status to published
        analyzed_tracker = get_analyzed_tracker()
        if analyzed_tracker:
            try:
                record = analyzed_tracker.get_record(article_title)
                if record:
                    # Update the status to published with existing data
                    analyzed_tracker.record_analysis(
                        title=article_title,
                        page_id=record.page_id,
                        revision_id=record.revision_id,
                        status=AnalysisStatus.PUBLISHED,
                        score=record.score,
                        decision=record.decision,
                        mode=record.mode,
                        changes_count=record.changes_count,
                        summary=summary,
                        original_content=record.original_content,
                        corrected_content=record.corrected_content,
                        character_count=record.character_count,
                        total_links=record.total_links,
                        dead_links_count=record.dead_links_count,
                        corrected_links_count=record.corrected_links_count,
                        human_verified=True,  # Manual publication implies human verification
                        manual_review_urls=record.manual_review_urls
                    )
                    logger.info(f"Updated analyzed tracker status to 'published' for article '{article_title}'")
                else:
                    logger.warning(f"Article '{article_title}' not found in analyzed tracker, cannot update status")
            except Exception as e:
                logger.error(f"Failed to update analyzed tracker for '{article_title}': {e}")

        # Update article status in the analysis queue (remove or mark as published)
        from wikipedia_maintenance.utils.database import DatabaseManager
        try:
            project_root = os.environ.get('PROJECT_ROOT')
            if project_root:
                db_path = str(Path(project_root) / "data" / "wikipedia_maintenance.db")
                db = DatabaseManager(db_path)
            else:
                db = DatabaseManager()
            
            cursor = db.conn.cursor()

            # Check if article exists in queue before deletion
            cursor.execute("SELECT id FROM articles_to_analyze WHERE title = ?", (article_title,))
            exists = cursor.fetchone()

            if exists:
                # Remove from queue since it's published
                cursor.execute("DELETE FROM articles_to_analyze WHERE title = ?", (article_title,))
                db.conn.commit()
                logger.info(f"Removed published article '{article_title}' from analysis queue (ID: {exists[0]})")
            else:
                logger.warning(f"Article '{article_title}' not found in analysis queue for deletion")
        except Exception as e:
            logger.error(f"Failed to remove published article '{article_title}' from analysis queue: {e}", exc_info=True)
        
        # Update job with success
        update_publication_job(
            publication_id,
            status="completed",
            message="Publication successful",
            completed_at=datetime.now().isoformat(),
            revision_id=int(revision_id) if revision_id and revision_id.isdigit() else None
        )
        
        logger.info(f"Publication {publication_id} completed for article {article_title}")
        
    except Exception as e:
        logger.error(f"Publication {publication_id} failed: {e}", exc_info=True)
        update_publication_job(
            publication_id,
            status="failed",
            message=f"Publication failed: {str(e)}",
            completed_at=datetime.now().isoformat(),
            error=str(e)
        )


# ============================================================================
# Routes
# ============================================================================

@router.get("/pending")
async def get_pending_publications():
    """
    Get all pending publications.

    Returns a list of publication jobs that are currently pending or running.
    """
    try:
        pending_jobs = []

        for job_id, job in _publication_jobs.items():
            if job["status"] in ["pending", "running"]:
                pending_jobs.append({
                    "publication_id": job_id,
                    "article_title": job["article_title"],
                    "status": job["status"],
                    "message": job["message"],
                    "started_at": job.get("started_at"),
                    "dry_run": job.get("dry_run", True)
                })

        return {
            "success": True,
            "count": len(pending_jobs),
            "publications": pending_jobs
        }

    except Exception as e:
        logger.error(f"Failed to get pending publications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get pending publications: {str(e)}")

@router.post("/validate")
async def validate_publication(
    request: PublicationValidationRequest,
    session: dict = Depends(get_wikipedia_session),
    kill_switch = Depends(get_kill_switch)
):
    """
    Validate publication without actually publishing.
    
    Performs all safety checks (Kill Switch, authentication, etc.)
    without making actual changes to Wikipedia.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        publisher = session.get("publisher")
        if not publisher:
            raise HTTPException(status_code=500, detail="Publisher not initialized")
        
        # Check Kill Switch (if available)
        if kill_switch and kill_switch.is_enabled():
            state = kill_switch.get_state()
            return {
                "success": False,
                "valid": False,
                "reason": "kill_switch_enabled",
                "message": f"Kill switch enabled: {state.reason}",
                "details": {
                    "trigger_source": state.trigger_source,
                    "requested_by": state.requested_by,
                    "requested_at": state.requested_at
                }
            }
        
        # Check authentication
        if not hasattr(publisher, 'authenticated') or not publisher.authenticated:
            return {
                "success": False,
                "valid": False,
                "reason": "not_authenticated",
                "message": "Publisher not authenticated with Wikipedia"
            }
        
        # Check dry-run mode
        if not request.dry_run:
            return {
                "success": True,
                "valid": True,
                "warning": "production_mode",
                "message": "Validation passed, but this will publish to Wikipedia"
            }
        
        return {
            "success": True,
            "valid": True,
            "message": "Validation passed - ready for publication"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publication validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/publish", response_model=PublicationResponse)
async def publish_article(
    request: PublicationRequest,
    background_tasks: BackgroundTasks,
    session: dict = Depends(get_wikipedia_session),
    kill_switch = Depends(get_kill_switch)
):
    """
    Publish article to Wikipedia.
    
    Creates a background job to publish the article using the existing
    Publisher while respecting all safety checks.
    """
    try:
        if not session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated with Wikipedia")
        
        publisher = session.get("publisher")
        if not publisher:
            raise HTTPException(status_code=500, detail="Publisher not initialized")
        
        # Check Kill Switch BEFORE starting job (if available)
        if kill_switch and kill_switch.is_enabled():
            state = kill_switch.get_state()
            raise HTTPException(
                status_code=403,
                detail=f"Publication blocked: Kill switch enabled. Reason: {state.reason}"
            )
        
        # Create publication job
        publication_id = create_publication_job(request.article_title, request.dry_run)
        
        # Start background worker
        background_tasks.add_task(
            run_publication_worker,
            publication_id,
            request.article_title,
            request.corrected_content,
            request.summary,
            request.dry_run,
            request.original_content,
            publisher
        )
        
        logger.info(f"Started publication {publication_id} for article {request.article_title}")
        
        return PublicationResponse(
            success=True,
            publication_id=publication_id,
            status="pending",
            message="Publication started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start publication: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start publication: {str(e)}")


@router.get("/{publication_id}", response_model=PublicationStatusResponse)
async def get_publication_status(publication_id: str):
    """
    Get publication job status.

    Returns the current status of a publication job.
    """
    try:
        job = get_publication_job(publication_id)

        if not job:
            raise HTTPException(status_code=404, detail="Publication job not found")

        return PublicationStatusResponse(
            publication_id=job["id"],
            status=job["status"],
            message=job["message"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            error=job.get("error"),
            revision_id=job.get("revision_id"),
            diff=job.get("diff")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get publication status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/{publication_id}/stream")
async def stream_publication_status(publication_id: str):
    """
    Stream publication status updates using Server-Sent Events (SSE).

    This endpoint sends real-time updates when the publication status changes.
    """
    async def event_stream():
        job = get_publication_job(publication_id)
        if not job:
            yield f"data: {json.dumps({'error': 'Publication job not found'})}\n\n"
            return

        # Send initial status
        yield f"data: {json.dumps({'status': job['status'], 'message': job['message']})}\n\n"

        # If already completed or failed, send final status and close
        if job['status'] in ['completed', 'failed']:
            yield f"data: {json.dumps({'status': job['status'], 'message': job['message'], 'revision_id': job.get('revision_id'), 'error': job.get('error')})}\n\n"
            return

        # Wait for status changes
        last_status = job['status']
        max_wait = 300  # 5 minutes max
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < max_wait:
            await asyncio.sleep(2)  # Check every 2 seconds

            current_job = get_publication_job(publication_id)
            if not current_job:
                yield f"data: {json.dumps({'error': 'Publication job not found'})}\n\n"
                return

            if current_job['status'] != last_status:
                last_status = current_job['status']
                yield f"data: {json.dumps({'status': current_job['status'], 'message': current_job['message'], 'revision_id': current_job.get('revision_id'), 'error': current_job.get('error')})}\n\n"

                # Close stream if completed or failed
                if current_job['status'] in ['completed', 'failed']:
                    break

        # Timeout
        yield f"data: {json.dumps({'error': 'Timeout waiting for publication'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
