# DEAD LINK MODULE - MATRICE DE VALIDATION CONSOLIDÉE

**Date de génération :** Automatique

**Total de règles identifiées :** 72

## Statistiques (au niveau des règles)

| Métrique | Count | Percentage |
|---------|-------|------------|
| Total de tests exécutés | 72 | - |
| 🟢 Règles entièrement validées (PASS) | 56 | 77.8% |
| 🔴 Règles en échec (FAIL) | 6 | 8.3% |
| 🟠 Règles partiellement testées (PARTIAL) | 8 | 11.1% |
| ⚪ Règles non testées (NOT_TESTED) | 2 | 2.8% |
| **Taux de validation réel** | - | **77.8%** |

## Matrice de Validation (une ligne par règle unique)

| ID | Règle | Catégorie | Scénario | Oracle attendu | Résultat réel | Preuve | Statut | Source |
|----|-------|-----------|----------|----------------|---------------|--------|--------|--------|
| ARCH-001 | Archive check attempted for dead link | Archive Fallback | URL: http://localhost:5000/tes... | Archive providers should be ch... |  | {'exception': "'ArchiveProvide... | 🔴 FAIL | dead_link_retry_archive_test_results.json |
| ARCH-002 | Archive check for healthy link | Archive Fallback | URL: http://localhost:5000/tes... | Archive should not be checked ... |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_retry_archive_test_results.json |
| ARCH-003 | Archive check for temporary error | Archive Fallback | URL: http://localhost:5000/tes... | Archive should not be checked ... |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_retry_archive_test_results.json |
| CV-001 | Same content → STRONG_MATCH | Content Verifier |  |  |  | {'content': {'decision': 'stro... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| CV-002 | Different content same domain → WEAK_MATCH | Content Verifier |  |  |  | {'content': {'decision': 'weak... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| CV-003 | Different domain → NO_MATCH | Content Verifier |  |  |  | {'content': {'decision': 'no_m... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| DL-001 | 200 → HEALTHY | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-002 | 301 → HEALTHY (redirect) | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-003 | 302 → HEALTHY (redirect) | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-004 | 307 → HEALTHY (redirect) | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-005 | 308 → HEALTHY (redirect) | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-006 | 404 → DEAD | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-007 | 410 → DEAD | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-008 | 400 → REVIEW_REQUIRED | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rev... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-009 | 401 → REVIEW_REQUIRED | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rev... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-010 | 403 → REVIEW_REQUIRED | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rev... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-011 | 429 → RATE_LIMITED | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rat... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-012 | 408 → TEMPORARY_ERROR | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-013 | 500 → TEMPORARY_ERROR | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-014 | 502 → TEMPORARY_ERROR | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-015 | 503 → TEMPORARY_ERROR | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-016 | 504 → TEMPORARY_ERROR | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-017 | Same domain redirect → HEALTHY | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-018 | Redirect chain → HEALTHY | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-019 | Different path redirect → HEALTHY | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-021 | HEALTHY → NO_ACTION | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-022 | TEMPORARY_ERROR → NO_ACTION | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-023 | RATE_LIMITED → NO_ACTION | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rat... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-024 | REVIEW_REQUIRED → REPAIR_REJECTED | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rev... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-025 | DEAD without redirect → REPAIR_REJECTED | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-026 | Same content → STRONG_MATCH | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-027 | Different content → WEAK_MATCH | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-028 | 404 should NOT be HEALTHY | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-029 | 403 should NOT be DEAD | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rev... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-030 | 429 should NOT be DEAD | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'rat... | 🟢 PASS | dead_link_rules_test_results.json |
| DL-031 | 503 should NOT be DEAD | HTTP Status / Redirect / Validator | URL: http://localhost:5000/tes... |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_rules_test_results.json |
| EDGE-001 | Retry on 503 | Edge Cases | URL: http://localhost:5000/tes... | Should retry up to max_retries... |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-002 | Retry on 404 (actual behavior) | Edge Cases | URL: http://localhost:5000/tes... | Retries once (retry_count: 1) |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-003 | Retry on 502 | Edge Cases | URL: http://localhost:5000/tes... | Should retry up to max_retries... |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-004 | SSL expired → DEAD | Edge Cases | URL: https://expired.badssl.co... | Should be classified as DEAD |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-005 | SSL verify failed → REVIEW_REQUIRED | Edge Cases | URL: https://wrong.host.badssl... | Should be classified as REVIEW... |  | {'link_check': {'status': 'rev... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-006 | DNS failure → TEMPORARY_ERROR | Edge Cases | URL: http://this-domain-does-n... | Should be classified as TEMPOR... |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-007 | Timeout → UNKNOWN (actual behavior) | Edge Cases | URL: http://localhost:5000/tes... | Should be classified as UNKNOW... |  | {'link_check': {'status': 'unk... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-008 | URL truncation detection | Edge Cases | URL: http://localhost:5000/tes... | Should detect truncation if pr... |  | note=Test category requires ad... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| EDGE-009 | Academic publisher 403 → TEMPORARY_ERROR | Edge Cases | URL: https://journals.sagepub.... | Should be classified as TEMPOR... |  | {'link_check': {'status': 'rev... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| EDGE-010 | Archive fallback | Edge Cases | URL: http://localhost:5000/tes... | Should attempt to find archive... |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_edge_cases_test_results.json |
| EDGE-011 | URL in reference scope | Edge Cases | URL: http://localhost:5000/tes... | Should be checked if in refere... |  | note=This edge case requires f... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| EDGE-012 | URL outside reference scope | Edge Cases | URL: http://localhost:5000/tes... | Should be skipped if not in re... |  | note=This edge case requires f... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| EDGE-013 | Unsupported template → REVIEW_REQUIRED | Edge Cases | URL: http://localhost:5000/tes... | Should be marked as REVIEW_REQ... |  | note=This edge case requires f... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| EDGE-014 | Partial repair for unsupported template | Edge Cases | URL: http://localhost:5000/tes... | Should add archive parameters ... |  | note=This edge case requires f... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| EDGE-015 | Auto repair disabled → NO_ACTION | Edge Cases | URL: http://localhost:5000/tes... | Should be marked as AUTO_REPAI... |  | note=This edge case requires f... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| EDGE-016 | Max checks per article | Edge Cases | URL: http://localhost:5000/tes... | Should respect max_checks_per_... |  | note=This edge case requires f... | 🟠 PARTIAL | dead_link_edge_cases_test_results.json |
| INT-001 | URL in <ref> should be analyzed | Integration | Article: Article test

Referen... | URL inside <ref> should be che... |  | {'issues_count': 2, 'issues': ... | 🔴 FAIL | dead_link_integration_test_results.json |
| INT-002 | URL outside <ref> should be skipped | Integration | Article: Article test

Text ou... | URLs outside <ref> should be s... |  | {'issues_count': 0, 'issues': ... | 🔴 FAIL | dead_link_integration_test_results.json |
| INT-003 | Multiple URLs in <ref> all analyzed | Integration | Article: Article test

<ref>{{... | All 3 URLs should be analyzed |  | {'issues_count': 5, 'issues': ... | 🔴 FAIL | dead_link_integration_test_results.json |
| INT-004 | Supported template - dead link detected | Integration | Article: Article test

<ref>{{... | Dead link detected, repair att... |  | {'issues_count': 2, 'issues': ... | 🟢 PASS | dead_link_integration_test_results.json |
| INT-005 | Unsupported template - REVIEW_REQUIRED | Integration | Article: Article test

<ref>{{... | Marked as REVIEW_REQUIRED with... |  | {'issues_count': 2, 'issues': ... | 🔴 FAIL | dead_link_integration_test_results.json |
| INT-006 | Supported template with healthy link - NO_ACTION | Integration | Article: Article test

<ref>{{... | No issue created (link is heal... |  | {'issues_count': 0, 'issues': ... | 🟢 PASS | dead_link_integration_test_results.json |
| INT-007 | Auto-repair disabled - NOT TESTED | Integration | Article: Article test

<ref>{{... | Requires config file modificat... |  | note=This test requires config... | ⚪ NOT_TESTED | dead_link_integration_test_results.json |
| INT-008 | Auto-repair enabled - NOT TESTED | Integration | Article: Article test

<ref>{{... | Requires config file modificat... |  | note=This test requires config... | ⚪ NOT_TESTED | dead_link_integration_test_results.json |
| INT-009 | Max checks limit respected | Integration | Article: Article test with man... | Only 3 URLs checked, remaining... |  | {'issues_count': 2, 'issues': ... | 🟢 PASS | dead_link_integration_test_results.json |
| INT-010 | Max checks limit not reached | Integration | Article: Article test with man... | All 2 URLs checked |  | {'issues_count': 2, 'issues': ... | 🟢 PASS | dead_link_integration_test_results.json |
| LV-001 | HEALTHY → NO_ACTION | Link Validator |  |  |  | {'link_check': {'status': 'hea... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| LV-002 | TEMPORARY_ERROR → NO_ACTION | Link Validator |  |  |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| LV-003 | RATE_LIMITED → NO_ACTION | Link Validator |  |  |  | {'link_check': {'status': 'rat... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| LV-004 | REVIEW_REQUIRED → REPAIR_REJECTED | Link Validator |  |  |  | {'link_check': {'status': 'rev... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| LV-005 | DEAD without redirect → REPAIR_REJECTED | Link Validator |  |  |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_strict_validation_test_results.json |
| RETRY-001 | 503 retries up to max_retries | Retry Logic | URL: http://localhost:5000/tes... | retry_count should be 3 |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_retry_archive_test_results.json |
| RETRY-002 | 502 retries up to max_retries | Retry Logic | URL: http://localhost:5000/tes... | retry_count should be 3 |  | {'link_check': {'status': 'tem... | 🟢 PASS | dead_link_retry_archive_test_results.json |
| RETRY-003 | 404 retries once (actual behavior) | Retry Logic | URL: http://localhost:5000/tes... | retry_count should be 1 |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_retry_archive_test_results.json |
| RETRY-004 | 410 retries once (actual behavior) | Retry Logic | URL: http://localhost:5000/tes... | retry_count should be 1 |  | {'link_check': {'status': 'dea... | 🟢 PASS | dead_link_retry_archive_test_results.json |
| RETRY-005 | 200 no retry | Retry Logic | URL: http://localhost:5000/tes... | retry_count should be 0 |  | {'link_check': {'status': 'hea... | 🔴 FAIL | dead_link_retry_archive_test_results.json |
