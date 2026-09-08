"""
Domain Management API endpoints.

Provides REST API endpoints for managing domain_to_site_name mappings
in case_normalization_data.yaml. This is the same source of truth used
by the domain enrichment service.
"""

import os
import tempfile
import yaml
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Domain Management"])

# Configuration file path
CASE_NORMALIZATION_FILE = Path(__file__).parent.parent.parent.parent / "config" / "case_normalization_data.yaml"


# ----------------------------------------------------------------------
# Request/Response Models
# ----------------------------------------------------------------------


class DomainEntry(BaseModel):
    """Domain entry model."""
    domain: str
    site_name: str
    source: Optional[str] = None  # 'wikidata', 'manual', etc.
    added_at: Optional[str] = None  # ISO timestamp


class AddDomainRequest(BaseModel):
    """Request model for adding a domain."""
    domain: str
    site_name: str
    source: str = "manual"


class UpdateDomainRequest(BaseModel):
    """Request model for updating a domain."""
    domain: str  # Current domain (key)
    new_domain: Optional[str] = None  # New domain if changing
    new_site_name: Optional[str] = None  # New site name if changing


class DomainListResponse(BaseModel):
    """Response model for domain list."""
    success: bool
    domains: List[DomainEntry]
    total: int
    statistics: Dict[str, int]


class DomainValidationResponse(BaseModel):
    """Response model for domain validation."""
    valid: bool
    normalized_domain: Optional[str] = None
    errors: List[str] = []
    warnings: List[str] = []


# ----------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------


def _write_yaml_atomic(path: Path, data: Dict[str, Any]) -> None:
    """
    Write YAML data to `path` atomically.
    
    Copied from config.py to avoid circular imports.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=None, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on POSIX and Windows
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _normalize_domain(domain: str, keep_www: bool = False) -> Optional[str]:
    """
    Normalize a domain name.
    
    Args:
        domain: Domain to normalize
        keep_www: If True, preserve www prefix. If False, remove it.
    
    Copied from domain_enrichment_service.py for consistency.
    """
    try:
        from urllib.parse import urlparse
        
        # Add scheme if missing for parsing
        if not domain.startswith(('http://', 'https://')):
            domain = f'https://{domain}'
        
        parsed = urlparse(domain)
        
        if not parsed.scheme or not parsed.netloc:
            logger.debug(f"Invalid domain: missing scheme or netloc for {domain}")
            return None
        
        # Extract domain
        domain = parsed.netloc.lower()
        
        # Remove userinfo
        if '@' in domain:
            domain = domain.rsplit('@', 1)[-1]
        
        # Remove port
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Remove www. prefix only if keep_www is False
        if not keep_www and domain.startswith('www.'):
            domain = domain[4:]
        
        # Basic validation
        if not domain or len(domain) < 3:
            logger.debug(f"Invalid domain: too short or empty: {domain}")
            return None
        
        # Check for invalid characters
        if not re.match(r'^[a-z0-9.-]+$', domain):
            logger.debug(f"Invalid domain: contains invalid characters: {domain}")
            return None
        
        # Reject domains with no dot
        if '.' not in domain:
            logger.debug(f"Invalid domain: no dot found: {domain}")
            return None
        
        return domain
    except Exception as e:
        logger.debug(f"Error normalizing domain: {e}")
        return None


def _load_case_normalization() -> Dict[str, Any]:
    """Load case_normalization_data.yaml."""
    if not CASE_NORMALIZATION_FILE.exists():
        logger.warning(f"Case normalization file not found: {CASE_NORMALIZATION_FILE}")
        return {}
    
    try:
        with open(CASE_NORMALIZATION_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return data
    except Exception as e:
        logger.error(f"Error loading case normalization file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load case normalization data: {e}")


def _save_case_normalization(data: Dict[str, Any]) -> None:
    """Save case_normalization_data.yaml atomically."""
    try:
        _write_yaml_atomic(CASE_NORMALIZATION_FILE, data)
        logger.info(f"Saved case normalization data to {CASE_NORMALIZATION_FILE}")
    except Exception as e:
        logger.error(f"Error saving case normalization data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save case normalization data: {e}")


def _extract_site_name(site_name_value: Any) -> str:
    """
    Extract site name from YAML value (handles both string and list format).
    
    Format in YAML: domain: [[site_name]]
    """
    if isinstance(site_name_value, str):
        return site_name_value
    
    if isinstance(site_name_value, list):
        # Handle nested list format [[site_name]]
        while isinstance(site_name_value, list) and len(site_name_value) > 0:
            site_name_value = site_name_value[0]
        return str(site_name_value) if site_name_value else ""
    
    return str(site_name_value) if site_name_value else ""


# ----------------------------------------------------------------------
# API Endpoints
# ----------------------------------------------------------------------


@router.get("/", response_model=DomainListResponse)
async def list_domains(search: Optional[str] = None):
    """
    List all domain_to_site_name mappings.
    
    Args:
        search: Optional search term to filter by domain or site name
    """
    try:
        data = _load_case_normalization()
        domain_to_site_name = data.get('domain_to_site_name', {})
        
        domains = []
        for domain, site_name_value in domain_to_site_name.items():
            site_name = _extract_site_name(site_name_value)
            
            # Apply search filter
            if search:
                search_lower = search.lower()
                if search_lower not in domain.lower() and search_lower not in site_name.lower():
                    continue
            
            domains.append(DomainEntry(
                domain=domain,
                site_name=site_name,
                source=None,  # Not tracked in current YAML
                added_at=None  # Not tracked in current YAML
            ))
        
        # Calculate statistics
        total = len(domains)
        
        return DomainListResponse(
            success=True,
            domains=domains,
            total=total,
            statistics={
                "total": total,
                "valid": total,  # All entries in YAML are considered valid
                "conflicts": 0,  # Not tracked separately
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing domains: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing domains: {str(e)}")


@router.get("/validate", response_model=DomainValidationResponse)
async def validate_domain(domain: str, site_name: str):
    """
    Validate a domain entry before adding/updating.
    
    Args:
        domain: Domain to validate
        site_name: Site name to validate
    """
    errors = []
    warnings = []
    
    # Normalize domain (keep www to allow variants)
    normalized = _normalize_domain(domain, keep_www=True)
    if not normalized:
        errors.append("Invalid domain format")
        return DomainValidationResponse(valid=False, errors=errors)
    
    # Check for conflicts
    data = _load_case_normalization()
    domain_to_site_name = data.get('domain_to_site_name', {})
    
    if normalized in domain_to_site_name:
        existing_site = _extract_site_name(domain_to_site_name[normalized])
        if existing_site != site_name:
            errors.append(f"Domain already mapped to '{existing_site}'")
        else:
            warnings.append("Domain already exists with same site name")
    
    # Check for subdomain conflicts (e.g., if wikiwix.com exists, warn about archive.wikiwix.com)
    domain_parts = normalized.split('.')
    if len(domain_parts) >= 2:
        # Check if parent domain exists
        parent_domain = '.'.join(domain_parts[1:])
        if parent_domain in domain_to_site_name:
            parent_site = _extract_site_name(domain_to_site_name[parent_domain])
            warnings.append(f"Parent domain '{parent_domain}' (mapped to '{parent_site}') already exists. This may be intentional if they are different services.")
    
    return DomainValidationResponse(
        valid=len(errors) == 0,
        normalized_domain=normalized,
        errors=errors,
        warnings=warnings
    )


@router.post("/")
async def add_domain(request: AddDomainRequest):
    """
    Add a new domain_to_site_name mapping.
    
    Args:
        request: AddDomainRequest with domain and site_name
    """
    # Validate and normalize (keep www to allow variants)
    normalized = _normalize_domain(request.domain, keep_www=True)
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid domain format")
    
    # Check for conflicts
    data = _load_case_normalization()
    if 'domain_to_site_name' not in data:
        data['domain_to_site_name'] = {}
    
    domain_to_site_name = data['domain_to_site_name']
    
    if normalized in domain_to_site_name:
        existing_site = _extract_site_name(domain_to_site_name[normalized])
        if existing_site != request.site_name:
            raise HTTPException(
                status_code=409,
                detail=f"Domain already mapped to '{existing_site}'"
            )
    
    # Add entry (format: domain: [[site_name]])
    logger.info(f"Adding domain: {normalized}, site_name: '{request.site_name}' (length: {len(request.site_name)})")
    domain_to_site_name[normalized] = [[request.site_name]]
    
    # Save
    _save_case_normalization(data)
    
    logger.info(f"Added domain mapping: {normalized} -> {request.site_name}")
    
    return {"success": True, "message": "Domain added successfully"}


@router.put("/{domain}")
async def update_domain(domain: str, request: UpdateDomainRequest):
    """
    Update an existing domain_to_site_name mapping.
    
    Args:
        domain: Current domain (key to update)
        request: UpdateDomainRequest with new_domain and/or new_site_name
    """
    data = _load_case_normalization()
    domain_to_site_name = data.get('domain_to_site_name', {})
    
    # Check if domain exists
    if domain not in domain_to_site_name:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")
    
    # Determine new key
    new_domain_key = request.new_domain if request.new_domain else domain
    
    # Normalize new domain if provided (keep www to allow variants)
    if request.new_domain:
        normalized_new = _normalize_domain(request.new_domain, keep_www=True)
        if not normalized_new:
            raise HTTPException(status_code=400, detail="Invalid new domain format")
        new_domain_key = normalized_new
    
    # Check for conflicts if changing domain
    if new_domain_key != domain and new_domain_key in domain_to_site_name:
        existing_site = _extract_site_name(domain_to_site_name[new_domain_key])
        raise HTTPException(
            status_code=409,
            detail=f"Target domain already mapped to '{existing_site}'"
        )
    
    # Get new site name
    new_site_name = request.new_site_name
    if new_site_name is None:
        new_site_name = _extract_site_name(domain_to_site_name[domain])
    
    # Remove old entry if domain changed
    if new_domain_key != domain:
        del domain_to_site_name[domain]
    
    # Add/update entry
    domain_to_site_name[new_domain_key] = [[new_site_name]]
    
    # Save
    _save_case_normalization(data)
    
    logger.info(f"Updated domain mapping: {domain} -> {new_domain_key} ({new_site_name})")
    
    return {"success": True, "message": "Domain updated successfully"}


@router.delete("/{domain}")
async def delete_domain(domain: str):
    """
    Delete a domain_to_site_name mapping.
    
    Args:
        domain: Domain to delete
    """
    data = _load_case_normalization()
    domain_to_site_name = data.get('domain_to_site_name', {})
    
    # Check if domain exists
    if domain not in domain_to_site_name:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")
    
    # Delete entry
    del domain_to_site_name[domain]
    
    # Save
    _save_case_normalization(data)
    
    logger.info(f"Deleted domain mapping: {domain}")
    
    return {"success": True, "message": "Domain deleted successfully"}
