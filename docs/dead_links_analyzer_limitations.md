# DeadLinkAnalyzer - Limitations and Recommendations

## Overview

The DeadLinkAnalyzer is designed to automatically repair dead external links in Wikipedia articles by finding replacement URLs that represent the same source and resource. This document outlines current limitations, API constraints, and recommendations for production use.

## Design Philosophy

**Fail-Closed by Default**: The system will NEVER make automatic repairs unless all conditions are met. Any error, ambiguity, or insufficient proof results in NO_REPAIR.

**Reliability > Coverage**: The priority is to ensure that every automatic repair is correct, rather than maximizing the number of repairs.

## Current Limitations

### 1. API Availability

#### Wayback Machine (Internet Archive)
- **Status**: Intermittently unavailable (503 Service Unavailable errors observed)
- **Impact**: Archive-driven candidate search may fail when Wayback API is rate-limited
- **Mitigation**: Health check system monitors provider availability; system falls back gracefully
- **Recommendation**: Implement exponential backoff for retries; consider Wayback as secondary source

#### Common Crawl
- **Status**: Available but complex integration
- **Limitations**: 
  - Requires specific crawl selection (e.g., CC-MAIN-2025-43)
  - Content retrieval requires HTTP range requests to S3
  - Better suited for bulk analysis than individual URL lookup
- **Recommendation**: Use as secondary proof source, not primary candidate finder

### 2. Candidate Search Limitations

#### URL Pattern Generation
- **Current Approach**: Generates candidate URLs based on title slug and common URL patterns
- **Limitations**:
  - Only works when archive provides title
  - Limited to same-domain candidates (by design)
  - May miss valid candidates with different URL structures
- **Recommendation**: Consider domain-specific search APIs for high-value domains

#### No External Search APIs
- **Reason**: External search APIs (Google, Bing, etc.) require API keys and have rate limits
- **Impact**: Cannot search the broader web for candidates
- **Recommendation**: For production, consider implementing domain-specific search for major sites

### 3. Proof Requirements

#### Three-Proof System
The system requires ALL three proofs to be confirmed for repair:

1. **ORIGINAL_PAGE_EXISTS**: Archive evidence that original page existed
2. **CANDIDATE_PAGE_EXISTS**: Live check that candidate is accessible
3. **SAME_RESOURCE_CONFIRMED**: Multiple independent proofs (domain, title, content, redirect)

**Limitations**:
- If any proof fails, repair is rejected (by design)
- Archive unavailability blocks all repairs
- Title matching is strict (case-sensitive comparison)

**Recommendation**: This strictness is intentional for fail-closed behavior. Do not relax proof requirements.

### 4. Content Verification

#### Current Implementation
- Uses ContentVerifier for live comparison
- Checks domain match, path similarity, title match
- Requires STRONG_MATCH (multiple proofs)

**Limitations**:
- Content comparison may fail for pages that changed legitimately
- Title matching is strict and may reject valid moves
- No semantic content analysis

**Recommendation**: Consider adding semantic similarity as optional proof (not required)

### 5. Rate Limiting and Throttling

#### Current Implementation
- Uses global API throttler
- Configurable max_requests_per_minute
- Exponential backoff on 429 errors

**Limitations**:
- Wayback Machine has its own rate limits (not controlled by our throttler)
- Multiple concurrent article checks may hit external limits
- No per-provider rate limiting

**Recommendation**: Implement per-provider rate limiting; add request queuing

## Production Recommendations

### 1. Configuration

#### Recommended Settings for Production

```yaml
dead_links_analyzer:
  enable_auto_repair: false  # Start with manual review
  max_checks_per_article: 5  # Conservative limit
  timeout: 15  # Longer timeout for unreliable APIs
  
  archive_search:
    enabled: true
    wayback_enabled: true
    health_check_interval: 600  # Check every 10 minutes
  
  candidate_search:
    enabled: true
    max_candidates: 2  # Conservative limit
    same_domain_only: true  # Strict domain requirement
  
  validation:
    require_unique_candidate: true  # Reject ambiguity
    require_same_domain: true  # Strict domain requirement
    require_title_match: true  # Strict title requirement
    require_archive_evidence: true  # Require archive proof
    min_confidence_threshold: 0.8  # High confidence threshold
  
  repair:
    require_minimal_diff: true  # Only URL changes
    replace_url_only: true  # No other modifications
    fail_on_ambiguity: true  # Reject any ambiguity
```

### 2. Deployment Strategy

#### Phase 1: Detection Only (Recommended First Step)
- Set `enable_auto_repair: false`
- Run analyzer to identify dead links
- Review detected issues manually
- Validate candidate suggestions
- Build confidence in system

#### Phase 2: Semi-Automatic with Review
- Set `enable_auto_repair: true` but require manual confirmation
- Use system to suggest repairs
- Human reviewer approves each repair
- Monitor accuracy and false positives

#### Phase 3: Fully Automatic (Only After Validation)
- Enable automatic repairs after proving accuracy
- Start with high-confidence repairs only
- Monitor for issues continuously
- Maintain manual review capability

### 3. Monitoring and Logging

#### Critical Metrics to Monitor
- Dead links detected per article
- Candidate search success rate
- Archive provider availability
- Repair approval rate (if semi-automatic)
- False positive rate
- API error rates (503, 429, timeouts)

#### Log Analysis
- Monitor for "SERVICE_UNAVAILABLE" messages
- Track "INSUFFICIENT_PROOFS" reasons
- Analyze "REPAIR_REJECTED" patterns
- Review "CANDIDATE_UNHEALTHY" frequency

### 4. Error Handling

#### Graceful Degradation
- Archive provider unavailable → Continue with redirect-only mode
- Candidate finder fails → Log as NO_REPAIR, continue
- Content verification fails → Log as NO_REPAIR, continue
- Any unexpected error → Log as NO_REPAIR, continue

#### Never Block on Single Failure
- Single URL failure should not stop article processing
- Provider unavailability should not stop entire batch
- Network errors should trigger retry, not abort

## Testing Recommendations

### 1. Unit Tests
- Run `pytest tests/test_link_validator.py -v`
- Run `pytest tests/test_candidate_finder.py -v`
- Run `pytest tests/test_fail_closed_behavior.py -v`

### 2. Integration Tests
- Run `python tests/integration/test_wayback_api.py` to check API availability
- Monitor for SERVICE_UNAVAILABLE status (expected during rate limiting)

### 3. Fail-Closed Verification
- All tests in `test_fail_closed_behavior.py` must pass
- These tests verify that errors result in NO_REPAIR
- Critical for production safety

### 4. Real-World Testing
- Test with actual Wikipedia articles
- Verify repairs in preview mode before publication
- Monitor for false positives
- Collect feedback from reviewers

## Known Issues

### 1. Wayback Machine Rate Limiting
- **Issue**: Frequent 503 errors during testing
- **Impact**: Archive-driven search may be unreliable
- **Workaround**: System falls back to redirect-only mode
- **Long-term**: Implement retry with exponential backoff

### 2. Limited Candidate Discovery
- **Issue**: URL pattern generation may miss valid candidates
- **Impact**: Some repairable links may not be repaired
- **Workaround**: Manual review for missed cases
- **Long-term**: Implement domain-specific search APIs

### 3. Strict Title Matching
- **Issue**: Title changes may reject valid moves
- **Impact**: Over-conservative, may miss valid repairs
- **Workaround**: Manual review for title mismatches
- **Long-term**: Add semantic similarity as optional proof

### 4. No Archive URL Replacement
- **Issue**: System never replaces with archive URLs (by design)
- **Impact**: Some links may remain dead even if archived
- **Workaround**: Manual addition of archive links if appropriate
- **Long-term**: Consider optional archive URL replacement with clear labeling

## Security and Compliance

### 1. Data Privacy
- Archive providers may store request logs
- Candidate URLs are logged for debugging
- No personal data is processed

### 2. Wikipedia Compliance
- All repairs must comply with Wikipedia policies
- Minimal diff requirement ensures no unintended changes
- Manual review recommended for controversial changes

### 3. Rate Limiting Respect
- System respects configured rate limits
- Does not abuse external APIs
- Implements exponential backoff

## Future Enhancements

### 1. Improved Candidate Search
- Domain-specific search APIs for major sites
- Machine learning for semantic similarity
- Historical URL pattern analysis

### 2. Enhanced Proof System
- Optional semantic similarity proof
- Content fingerprinting
- Author/metadata matching

### 3. Better Archive Integration
- Multiple archive providers with fallback
- Archive content caching
- Differential archive comparison

### 4. User Interface
- Repair suggestion review interface
- Confidence visualization
- Proof evidence display

## Conclusion

The DeadLinkAnalyzer is designed with fail-closed behavior as the primary requirement. It will only make automatic repairs when all conditions are met and all proofs are confirmed. This conservative approach ensures reliability but may limit coverage.

**IMPORTANT: The module is NOT yet ready for Wikipedia production use.**

The current implementation has the following limitations that must be addressed before production deployment:

1. **Candidate Search**: Currently uses URL pattern generation (slug-based) rather than real archive-driven discovery. This does not prove that candidates represent the same resource.

2. **Archive Providers**: Only Wayback Machine is partially implemented. Arquivo.pt and Common Crawl need to be added as functional providers.

3. **Real-World Validation**: No real-world testing has been performed with known dead links. The system needs validation against a real dataset of 100-500 known dead links.

4. **Integration Tests**: Integration tests for archive providers are incomplete. Each provider needs real API testing.

5. **False Positive Rate**: The false positive rate must be measured and proven to be practically zero before Wikipedia production use.

**Required for Production**:

- Implement Arquivo.pt as a functional archive provider with search capabilities
- Implement Common Crawl with CDXJ index for candidate discovery
- Modify CandidateFinder to use archive evidence for real candidate discovery (not pattern generation)
- Create comprehensive integration tests for all providers
- Create real-world test cases with known dead links and expected outcomes
- Measure false positive rate on real dataset
- Prove that the system can correctly find replacement URLs in the real web

**Key Principle**: When in doubt, NO_REPAIR is always the correct decision. The system may miss 90% of repairs; this is preferable to publishing a single incorrect URL on Wikipedia.
