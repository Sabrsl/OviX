# DEAD LINK MODULE - TABLE CANONIQUE DES RÈGLES

Cette table contient **un seul enregistrement par règle** avec une catégorie primaire unique.

## Statistiques Globales (Correctes)

| Métrique | Count | Percentage |
|---------|-------|------------|
| **Total de règles dans la table canonique** | 53 | 100% |
| **Règles entièrement validées (PASS)** | 33 | 62.3% |
| **Règles en échec (FAIL)** | 7 | 13.2% |
| **Règles partiellement testées (PARTIAL)** | 7 | 13.2% |
| **Règles non testées (NOT_TESTED)** | 3 | 5.7% |
| **Règles non prouvées (NOT_PROVEN)** | 3 | 5.7% |
| **Taux de validation réel** | - | **62.3%** |

---

## Table Canonique (53 Règles)

| rule_id | category_primary | scenario | oracle | actual | evidence | status | test_id | note |
|---------|------------------|----------|--------|--------|----------|--------|---------|------|
| DL-001 | http_status | 200 → HEALTHY | status=healthy | status=healthy | http_status_code=200 | 🟢 PASS | DL-001 | |
| DL-002 | http_status | 301 → HEALTHY (redirect) | status=healthy | status=healthy | http_status_code=301 | 🟢 PASS | DL-002 | |
| DL-003 | http_status | 302 → HEALTHY (redirect) | status=healthy | status=healthy | http_status_code=302 | 🟢 PASS | DL-003 | |
| DL-004 | http_status | 307 → HEALTHY (redirect) | status=healthy | status=healthy | http_status_code=307 | 🟢 PASS | DL-004 | |
| DL-005 | http_status | 308 → HEALTHY (redirect) | status=healthy | status=healthy | http_status_code=308 | 🟢 PASS | DL-005 | |
| DL-006 | http_status | 404 → DEAD | status=dead | status=dead | http_status_code=404 | 🟢 PASS | DL-006 | |
| DL-007 | http_status | 410 → DEAD | status=dead | status=dead | http_status_code=410 | 🟢 PASS | DL-007 | |
| DL-008 | http_status | 400 → REVIEW_REQUIRED | status=review_required | status=review_required | http_status_code=400 | 🟢 PASS | DL-008 | |
| DL-009 | http_status | 401 → REVIEW_REQUIRED | status=review_required | status=review_required | http_status_code=401 | 🟢 PASS | DL-009 | |
| DL-010 | http_status | 403 → REVIEW_REQUIRED | status=review_required | status=review_required | http_status_code=403 | 🟢 PASS | DL-010 | |
| DL-011 | http_status | 429 → RATE_LIMITED | status=rate_limited | status=rate_limited | http_status_code=429 | 🟢 PASS | DL-011 | |
| DL-012 | http_status | 408 → TEMPORARY_ERROR | status=temporary_error | status=temporary_error | http_status_code=408 | 🟢 PASS | DL-012 | |
| DL-013 | http_status | 500 → TEMPORARY_ERROR | status=temporary_error | status=temporary_error | http_status_code=500 | 🟢 PASS | DL-013 | |
| DL-014 | http_status | 502 → TEMPORARY_ERROR | status=temporary_error | status=temporary_error | http_status_code=502 | 🟢 PASS | DL-014 | |
| DL-015 | http_status | 503 → TEMPORARY_ERROR | status=temporary_error | status=temporary_error | http_status_code=503 | 🟢 PASS | DL-015 | |
| DL-016 | http_status | 504 → TEMPORARY_ERROR | status=temporary_error | status=temporary_error | http_status_code=504 | 🟢 PASS | DL-016 | |
| DL-017 | redirect | Same domain redirect → HEALTHY | status=healthy | invalid_redirect | http_status_code=200 | 🔴 FAIL | DL-017 | Oracle vs résultat contradictoire |
| DL-018 | redirect | Redirect chain → HEALTHY | status=healthy | invalid_redirect | http_status_code=200 | 🔴 FAIL | DL-018 | Oracle vs résultat contradictoire |
| DL-019 | redirect | Different path redirect → HEALTHY | status=healthy | invalid_redirect | http_status_code=200 | 🔴 FAIL | DL-019 | Oracle vs résultat contradictoire |
| DL-021 | link_validator | HEALTHY → NO_ACTION | decision=no_action | decision=no_action | status=healthy | 🟢 PASS | LV-001 | |
| DL-022 | link_validator | TEMPORARY_ERROR → NO_ACTION | decision=no_action | decision=no_action | status=temporary_error | 🟢 PASS | LV-002 | |
| DL-023 | link_validator | RATE_LIMITED → NO_ACTION | decision=no_action | decision=no_action | status=rate_limited | 🟢 PASS | LV-003 | |
| DL-024 | link_validator | REVIEW_REQUIRED → REPAIR_REJECTED | decision=repair_rejected | decision=repair_rejected | status=review_required | 🟢 PASS | LV-004 | |
| DL-025 | link_validator | DEAD without redirect → REPAIR_REJECTED | decision=repair_rejected | decision=repair_rejected | status=dead | 🟢 PASS | LV-005 | |
| DL-026 | content_verifier | Same content → STRONG_MATCH | decision=strong_match | decision=strong_match | title_match=true | 🟢 PASS | CV-001 | |
| DL-027 | content_verifier | Different content → WEAK_MATCH | decision=weak_match | decision=weak_match | domain_match=true | 🟢 PASS | CV-002 | |
| EDGE-001 | retry | Retry on 503 | retry_count=3 | retry_count=3 | status=temporary_error | 🟢 PASS | RETRY-001 | |
| EDGE-002 | retry | Retry on 404 | retry_count=1 | retry_count=1 | status=dead | 🟢 PASS | RETRY-003 | |
| EDGE-003 | retry | Retry on 502 | retry_count=3 | retry_count=3 | status=temporary_error | 🟢 PASS | RETRY-002 | |
| EDGE-004 | ssl_dns_timeout | SSL expired → DEAD | status=dead | status=dead | error=SSL_CERTIFICATE_EXPIRED | 🟢 PASS | EDGE-004 | |
| EDGE-005 | ssl_dns_timeout | SSL verify failed → REVIEW_REQUIRED | status=review_required | status=review_required | error=SSL_VERIFY_FAILED | 🟢 PASS | EDGE-005 | |
| EDGE-006 | ssl_dns_timeout | DNS failure → TEMPORARY_ERROR | status=temporary_error | status=temporary_error | error=DNS_TRANSIENT_11001 | 🟢 PASS | EDGE-006 | |
| EDGE-007 | ssl_dns_timeout | Timeout → UNKNOWN | status=unknown | status=unknown | error=UNEXPECTED_TimeoutError | 🟢 PASS | EDGE-007 | |
| EDGE-008 | ssl_dns_timeout | URL truncation detection | Detect truncation | Test category not fully implemented | note=Test category requires additional setup | ⚪ NOT_TESTED | EDGE-008 | Catégorie non implémentée |
| EDGE-009 | academic_publisher | Academic publisher 403 → TEMPORARY_ERROR | status=temporary_error | PARTIAL: Requires real academic domain | Requires real academic domain | 🟠 PARTIAL | EDGE-009 | Nécessite vrai domaine académique |
| EDGE-010 | archive_fallback | Archive fallback | Archive check attempted | Exception: no find_archive method | Method does not exist | 🔴 FAIL | ARCH-001 | Méthode n'existe pas |
| EDGE-011 | scope_ref | URL in <ref> scope | URL dans <ref> analysée | PARTIAL: Requires full DeadLinkAnalyzer | Requires full DeadLinkAnalyzer | 🟠 PARTIAL | EDGE-011 | Test partiel |
| EDGE-012 | scope_ref | URL outside <ref> scope | URL hors <ref> ignorée | PARTIAL: Requires full DeadLinkAnalyzer | Requires full DeadLinkAnalyzer | 🟠 PARTIAL | EDGE-012 | Test partiel |
| EDGE-013 | template_handling | Unsupported template → REVIEW_REQUIRED | template_unsupported flag | PARTIAL: Requires full DeadLinkAnalyzer | Requires full DeadLinkAnalyzer | 🟠 PARTIAL | EDGE-013 | Test partiel |
| EDGE-014 | template_handling | Partial repair for unsupported template | Partial repair | PARTIAL: Requires full DeadLinkAnalyzer | Requires full DeadLinkAnalyzer | 🟠 PARTIAL | EDGE-014 | Test partiel |
| EDGE-015 | auto_repair | Auto repair disabled | AUTO_REPAIR_DISABLED | PARTIAL: Requires full DeadLinkAnalyzer | Requires full DeadLinkAnalyzer | 🟠 PARTIAL | EDGE-015 | Test partiel |
| EDGE-016 | max_checks | Max checks per article | 3 URLs analysées | PARTIAL: Requires full DeadLinkAnalyzer | Requires full DeadLinkAnalyzer | 🟠 PARTIAL | EDGE-016 | Test partiel |
| RETRY-200 | retry | 200 no retry | retry_count=0 | retry_count=1 | Retry inutile sur succès | 🔴 FAIL | RETRY-005 | Retry inutile |
| INT-001 | scope_ref | URL in <ref> should be analyzed | URL dans <ref> analysée | 2 issues créées | issues_count=2 | 🔴 FAIL | INT-001 | Scope non implémenté |
| INT-002 | scope_ref | URL outside <ref> should be skipped | URL hors <ref> ignorée | issues_count=0 | issues_count=0 | ⚠️ NOT_PROVEN | INT-002 | Preuve insuffisante (0 issue peut être accidentel) |
| INT-003 | scope_ref | Multiple URLs in <ref> all analyzed | 3 URLs analysées | 5 issues créées | issues_count=5 | ⚠️ NOT_PROVEN | INT-003 | Confusion issues_count/urls_checked |
| INT-004 | template_handling | Supported template - dead link detected | Dead link détecté | Repair tenté | issues_count=2 | 🟢 PASS | INT-004 | |
| INT-005 | template_handling | Unsupported template - REVIEW_REQUIRED | template_unsupported flag | Template traité comme supporté | Pas de flag template_unsupported | 🔴 FAIL | INT-005 | Template non supporté ne fonctionne pas |
| INT-006 | template_handling | Supported template with healthy link → NO_ACTION | Aucune issue | 0 issues créées | issues_count=0 | 🟢 PASS | INT-006 | |
| INT-007 | auto_repair | Auto-repair disabled - NOT TESTED | AUTO_REPAIR_DISABLED | NOT TESTED | Requires config.yaml modification | ⚪ NOT_TESTED | INT-007 | Non testable sans config |
| INT-008 | auto_repair | Auto-repair enabled - NOT TESTED | Repair tenté | NOT TESTED | Requires config.yaml modification | ⚪ NOT_TESTED | INT-008 | Non testable sans config |
| INT-009 | max_checks | Max checks limit respected | 3 URLs analysées | 2 issues créées | issues_count=2 | ⚠️ NOT_PROVEN | INT-009 | Confusion issues_count/urls_checked |
| INT-010 | max_checks | Max checks limit not reached | 2 URLs analysées | 2 issues créées | issues_count=2 | 🟢 PASS | INT-010 | |

---

## Répartition par Catégorie Primaire (Sans Chevauchement)

### http_status (16 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 13 | 81.3% |
| 🔴 FAIL | 3 | 18.7% |
| 🟠 PARTIAL | 0 | 0% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **81.3%** |

**Règles :** DL-001 à DL-016

---

### redirect (3 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 0 | 0% |
| 🔴 FAIL | 3 | 100% |
| 🟠 PARTIAL | 0 | 0% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **0%** |

**Règles :** DL-017, DL-018, DL-019

---

### link_validator (5 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 5 | 100% |
| 🔴 FAIL | 0 | 0% |
| 🟠 PARTIAL | 0 | 0% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **100%** |

**Règles :** DL-021 à DL-025

---

### content_verifier (2 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 2 | 100% |
| 🔴 FAIL | 0 | 0% |
| 🟠 PARTIAL | 0 | 0% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **100%** |

**Règles :** DL-026, DL-027

---

### retry (4 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 3 | 75% |
| 🔴 FAIL | 1 | 25% |
| 🟠 PARTIAL | 0 | 0% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **75%** |

**Règles :** EDGE-001, EDGE-002, EDGE-003, RETRY-200

---

### ssl_dns_timeout (5 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 4 | 80% |
| 🔴 FAIL | 0 | 0% |
| 🟠 PARTIAL | 0 | 0% |
| ⚪ NOT_TESTED | 1 | 20% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **80%** |

**Règles :** EDGE-004, EDGE-005, EDGE-006, EDGE-007, EDGE-008

---

### academic_publisher (1 règle)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 0 | 0% |
| 🔴 FAIL | 0 | 0% |
| 🟠 PARTIAL | 1 | 100% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **0%** |

**Règles :** EDGE-009

---

### archive_fallback (1 règle)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 0 | 0% |
| 🔴 FAIL | 1 | 100% |
| 🟠 PARTIAL | 0 | 0% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **0%** |

**Règles :** EDGE-010

---

### scope_ref (5 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 0 | 0% |
| 🔴 FAIL | 1 | 20% |
| 🟠 PARTIAL | 2 | 40% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 2 | 40% |
| **Taux de validation** | - | **0%** |

**Règles :** EDGE-011, EDGE-012, INT-001, INT-002, INT-003

---

### template_handling (5 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 2 | 40% |
| 🔴 FAIL | 1 | 20% |
| 🟠 PARTIAL | 2 | 40% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **40%** |

**Règles :** EDGE-013, EDGE-014, INT-004, INT-005, INT-006

---

### auto_repair (3 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 0 | 0% |
| 🔴 FAIL | 0 | 0% |
| 🟠 PARTIAL | 1 | 33.3% |
| ⚪ NOT_TESTED | 2 | 66.7% |
| ⚠️ NOT_PROVEN | 0 | 0% |
| **Taux de validation** | - | **0%** |

**Règles :** EDGE-015, INT-007, INT-008

---

### max_checks (3 règles)
| Statut | Count | Percentage |
|--------|-------|------------|
| 🟢 PASS | 1 | 33.3% |
| 🔴 FAIL | 0 | 0% |
| 🟠 PARTIAL | 1 | 33.3% |
| ⚪ NOT_TESTED | 0 | 0% |
| ⚠️ NOT_PROVEN | 1 | 33.3% |
| **Taux de validation** | - | **33.3%** |

**Règles :** EDGE-016, INT-009, INT-010

---

## Vérification du Comptage

**Total des catégories :**
- http_status: 16
- redirect: 3
- link_validator: 5
- content_verifier: 2
- retry: 4
- ssl_dns_timeout: 5
- academic_publisher: 1
- archive_fallback: 1
- scope_ref: 5
- template_handling: 5
- auto_repair: 3
- max_checks: 3

**Total : 16 + 3 + 5 + 2 + 4 + 5 + 1 + 1 + 5 + 5 + 3 + 3 = 53** ✓

---

## Conclusion

**Sur les 53 règles actuellement représentées dans la table canonique, 33 ont été entièrement démontrées conformes à leur oracle, soit 62.3%.**

Les 7 PARTIAL, les 3 NOT_TESTED et les 3 NOT_PROVEN ne permettent pas de conclure qu'elles fonctionnent ou qu'elles ne fonctionnent pas.

**Note importante :** Le chiffre "47" mentionné précédemment ne correspond ni au nombre de lignes dans la matrice (53) ni à un référentiel officiel établi. Il faut établir un référentiel officiel avant de pouvoir comparer le taux de validation à un objectif.
