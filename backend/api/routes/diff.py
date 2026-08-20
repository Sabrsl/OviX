"""
OVIX Backend API - Diff Routes

Handles diff generation using the existing Corrector.
"""

import logging
import difflib
import html
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class DiffRequest(BaseModel):
    """Diff generation request."""
    original: str
    corrected: str
    diff_type: str = "html"  # "html" or "unified"


class DiffResponse(BaseModel):
    """Diff response."""
    success: bool
    diff_id: str
    diff_type: str
    html_diff: Optional[str] = None
    unified_diff: Optional[str] = None
    stats: dict


class DiffInfo(BaseModel):
    """Diff information."""
    diff_id: str
    diff_type: str
    html_diff: Optional[str] = None
    unified_diff: Optional[str] = None
    stats: dict


# ============================================================================
# Diff Storage
# ============================================================================

# In-memory diff storage (could be enhanced with Redis)
_diffs: dict = {}


def create_diff(original: str, corrected: str, diff_type: str = "html") -> str:
    """Create a diff and store it."""
    import uuid
    diff_id = str(uuid.uuid4())
    
    # Generate diffs
    html_diff = None
    unified_diff = None
    stats = {}
    
    if diff_type == "html" or diff_type == "both":
        html_diff = generate_html_diff(original, corrected)
    
    if diff_type == "unified" or diff_type == "both":
        unified_diff = generate_unified_diff(original, corrected)
    
    # Calculate stats
    stats = {
        "original_length": len(original),
        "corrected_length": len(corrected),
        "difference": len(corrected) - len(original),
        "changes_count": count_changes(original, corrected)
    }
    
    _diffs[diff_id] = {
        "id": diff_id,
        "original": original,
        "corrected": corrected,
        "diff_type": diff_type,
        "html_diff": html_diff,
        "unified_diff": unified_diff,
        "stats": stats
    }
    
    return diff_id


def get_diff(diff_id: str) -> Optional[dict]:
    """Get diff by ID."""
    return _diffs.get(diff_id)


# ============================================================================
# Diff Generation Functions
# ============================================================================

def generate_html_diff(original: str, corrected: str) -> str:
    """Génère un diff HTML qui préserve la structure wikicode (sauts de ligne, sections) - identique à Streamlit."""
    orig_lines = original.split('\n')
    corr_lines = corrected.split('\n')

    matcher = difflib.SequenceMatcher(None, orig_lines, corr_lines)

    out_lines = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in orig_lines[i1:i2]:
                out_lines.append(html.escape(line))
        elif tag == "delete":
            for line in orig_lines[i1:i2]:
                out_lines.append(f'<span class="wm-diff-del">{html.escape(line)}</span>')
        elif tag == "insert":
            for line in corr_lines[j1:j2]:
                # Detect and make archive URLs copiable
                processed_line = _make_urls_copiable(html.escape(line))
                out_lines.append(f'<span class="wm-diff-ins">{processed_line}</span>')
        elif tag == "replace":
            for orig_line, corr_line in zip(orig_lines[i1:i2], corr_lines[j1:j2]):
                out_lines.append(_diff_line(orig_line, corr_line))

    return '<br>'.join(out_lines)


def _make_urls_copiable(text: str) -> str:
    """Detect web.archive.org URLs and add copy buttons."""
    import re
    
    # Pattern to match web.archive.org URLs
    archive_pattern = r'(https://web\.archive\.org/[^\s<>"\']+)'
    
    def replace_url(match):
        url = match.group(1)
        # Create a copy button next to the URL
        return f'{url} <button class="copy-url-btn" data-url="{url}" title="Copier l\'URL">📋</button>'
    
    return re.sub(archive_pattern, replace_url, text)


def _diff_line(original: str, corrected: str) -> str:
    """Diff mot-à-mot pour une seule ligne - identique à Streamlit."""
    orig_words = original.split()
    corr_words = corrected.split()
    matcher = difflib.SequenceMatcher(None, orig_words, corr_words)

    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            out.append(html.escape(" ".join(orig_words[i1:i2])))
        elif tag == "delete":
            out.append(f'<span class="wm-diff-del">{html.escape(" ".join(orig_words[i1:i2]))}</span>')
        elif tag == "insert":
            out.append(f'<span class="wm-diff-ins">{html.escape(" ".join(corr_words[j1:j2]))}</span>')
        elif tag == "replace":
            out.append(
                f'<span class="wm-diff-del">{html.escape(" ".join(orig_words[i1:i2]))}</span> '
                f'<span class="wm-diff-ins">{html.escape(" ".join(corr_words[j1:j2]))}</span>'
            )
    return " ".join(out)


def generate_unified_diff(original: str, corrected: str) -> str:
    """Generate unified diff."""
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        corrected.splitlines(keepends=True),
        fromfile="original",
        tofile="corrected"
    )
    return "".join(diff)


def count_changes(original: str, corrected: str) -> int:
    """Count the number of changes in the diff."""
    matcher = difflib.SequenceMatcher(None, original, corrected)
    changes = sum(1 for tag, _, _, _, _ in matcher.get_opcodes() if tag != "equal")
    return changes


# ============================================================================
# Routes
# ============================================================================

@router.post("/generate", response_model=DiffResponse)
async def generate_diff(request: DiffRequest):
    """
    Generate a diff between original and corrected content.
    
    Uses the existing difflib library to generate both HTML and unified diffs.
    """
    try:
        diff_id = create_diff(request.original, request.corrected, request.diff_type)
        diff = get_diff(diff_id)
        
        return DiffResponse(
            success=True,
            diff_id=diff_id,
            diff_type=request.diff_type,
            html_diff=diff.get("html_diff"),
            unified_diff=diff.get("unified_diff"),
            stats=diff.get("stats", {})
        )
        
    except Exception as e:
        logger.error(f"Failed to generate diff: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate diff: {str(e)}")


@router.get("/{diff_id}", response_model=DiffInfo)
async def get_diff_info(diff_id: str):
    """
    Get diff information by ID.
    
    Returns the stored diff with its statistics.
    """
    try:
        diff = get_diff(diff_id)
        
        if not diff:
            raise HTTPException(status_code=404, detail="Diff not found")
        
        return DiffInfo(
            diff_id=diff["id"],
            diff_type=diff["diff_type"],
            html_diff=diff.get("html_diff"),
            unified_diff=diff.get("unified_diff"),
            stats=diff.get("stats", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get diff: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get diff: {str(e)}")
