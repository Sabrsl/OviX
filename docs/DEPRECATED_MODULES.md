# Deprecated and Experimental Modules

This document describes modules that are deprecated, experimental, or have special usage considerations.

## Dead Code (Removed)

### typography_old.py ✅ REMOVED
**Location**: `src/wikipedia_maintenance/analyzers/typography_old.py`

**Status**: ❌ DEAD CODE - Successfully removed

**Reason**: 
- No imports found in the codebase
- Replaced by newer typography analysis modules
- Not referenced in any active code

**Action Taken**: File deleted on 2026-08-09

**Migration**: Use the newer typography analysis modules in `src/wikipedia_maintenance/analyzers/typography.py` and related detectors.

---

## Experimental Modules (Use with Caution)

### candidate_finder.py
**Location**: `src/wikipedia_maintenance/utils/candidate_finder.py`

**Status**: ⚠️ EXPERIMENTAL - Disabled in production

**Reason**:
- Commented out in `dead_links.py` (line 33: `# from ..utils.candidate_finder import CandidateFinder`)
- Only used in test files with mocking
- Not ready for production use

**Current Usage**:
- Test files: `tests/test_candidate_finder.py`, `tests/integration/test_real_world_cases.py`
- Disabled in production code

**Recommendation**: 
- Keep for development/testing
- Document experimental status clearly
- Consider enabling after thorough testing

**Notes**:
- Used for finding current URLs based on archived content
- Has comprehensive test coverage
- May be useful for future dead link repair features

---

## Legacy Code (Planned for Replacement)

### Manual credential loading in publisher.py
**Location**: `src/wikipedia_maintenance/utils/publisher.py` (lines 502-515)

**Status**: ⚠️ LEGACY - Fallback code

**Reason**:
- Provides fallback to direct environment variable access
- Only used if secure credential manager fails to import
- Should be removed once secure credentials are fully deployed

**Recommendation**:
- Keep as temporary fallback
- Remove after P1 security improvements are fully deployed
- Monitor for import failures

**Migration**: Ensure all environments use the new `SecureCredentialManager`

---

## Configuration Overrides

### config.yaml user_agent override
**Location**: `config/config.yaml` (line 92)

**Status**: ⚠️ DEPRECATED - Overridden by bot identity

**Reason**:
- Bot identity system now manages User-Agent strings
- Config-based override is commented out in publisher.py
- Environment variables take precedence

**Recommendation**:
- Remove from config.yaml in future version
- Use BOT_IDENTITY environment variables instead
- Document deprecation in configuration guide

**Migration**: Use bot identity environment variables (BOT_NAME, BOT_VERSION, etc.)

---

## Summary

### Files Safe to Delete
- ✅ `src/wikipedia_maintenance/analyzers/typography_old.py` - REMOVED

### Files to Keep with Documentation
- `src/wikipedia_maintenance/utils/candidate_finder.py` (experimental)

### Code to Refactor
- Legacy credential loading in publisher.py
- Config-based User-Agent override

### Migration Path
1. Remove `typography_old.py`
2. Document `candidate_finder.py` as experimental
3. Monitor fallback credential usage
4. Remove deprecated config options in next major version

---

## Maintenance Notes

- Review this document quarterly
- Update module status as features mature
- Remove deprecated code after appropriate grace period
- Ensure tests cover experimental modules before promotion