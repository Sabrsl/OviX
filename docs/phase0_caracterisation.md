# Phase 0 - Étape 0.2 : Tests de caractérisation

**Date :** 2025-01-XX
**Objectif :** Capturer le comportement actuel du système sans modifier le code

---

## 1. Structure Issue

### Champs de Issue

**Champs principaux (13) :**
- issue_type
- description
- position
- original_text
- suggested_text
- severity
- line
- column
- context
- confidence
- rule_reference
- fix_options
- extra

### Issue.extra - Contenu typique

**11 champs identifiés :**
- url : URL originale
- old_url : URL originale (dupliqué)
- new_url : URL cible (dupliqué avec suggested_text)
- http_status_code : Code HTTP (ex: 404)
- repair_decision : Décision de réparation (ex: REPLACEMENT_CONFIRMED)
- repair_status : Statut de réparation (ex: REPAIR_APPLIED)
- archive_url : URL d'archive
- archive_date : Date d'archive
- provider : Fournisseur d'archive (ex: web.archive.org)
- template_name : Nom du template (ex: Lien web)
- repair_type : Type de réparation (ex: template)

**Observations :**
- Duplication : url/old_url et new_url/suggested_text sont dupliqués
- Non structuré : Issue.extra est un dict générique, impossible de requêter
- Tracking dispersé : Les méta-données de tracking sont dans extra, pas dans une table dédiée

---

## 2. AnalyzedTracker

### Structure AnalysisRecord

**18 champs :**
- title
- page_id
- revision_id
- analysis_date
- status (pending, published, rejected, ignored, error)
- score
- decision
- mode (regex, IA)
- changes_count
- summary
- original_content (contenu wikitext complet)
- corrected_content (contenu wikitext complet)
- character_count
- total_links
- dead_links_count
- corrected_links_count
- human_verified
- manual_review_urls

**Observations :**
- Stockage JSON lourd (contenu complet)
- Pas de tracking granulaire par URL
- Pas de corrélation avec Issue ou Correction

---

## 3. PublishedTracker

### Structure PublishedTracker entry

**5 champs :**
- published_at
- category
- mode
- summary
- revision_id

**Observations :**
- Structure très simple
- Pas de tracking par URL
- Pas de corrélation avec Issue ou Correction

---

## 4. Database (SQLite)

### Tables existantes (21)

**Tables principales :**
- articles : Articles analysés
- issues : Problèmes détectés
- actions : Actions utilisateur
- sessions : Sessions d'analyse
- analysis_results : Résultats d'analyse complets
- analysis_jobs : Jobs d'analyse
- articles_to_analyze : File d'attente d'analyse

**Tables automation :**
- automation_sessions : Sessions d'automatisation
- automation_article_states : États des articles en automation
- automation_interruptions : Interruptions d'automatisation
- scheduler_queue : File d'attente du scheduler
- scheduler_state : État du scheduler
- scheduler_statistics : Statistiques du scheduler

**Tables utilitaires :**
- https_verification_cache : Cache HTTPS
- manual_review_decisions : Décisions de révision manuelle
- kill_switch_state : État du kill switch
- automation_lock : Verrou d'automatisation
- settings : Paramètres
- user_contributions : Contributions utilisateur

**Observations :**
- Aucune table dédiée aux DeadLink operations
- Aucune table dédiée aux événements de tracking
- analysis_results contient le contenu complet (comme AnalyzedTracker)

---

## 5. Corrector

### Problème identifié

Le test de caractérisation a révélé que `Corrector.apply_corrections()` retourne une liste de 52 chaînes de caractères au lieu d'objets Correction.

**Cela indique :**
- Soit un bug dans le test (utilisation incorrecte)
- Soit un comportement inattendu de Corrector
- Soit une incohérence entre les deux implémentations de Corrector

**À investiguer dans Phase 0 - Étape 0.3 :**
- Vérifier le comportement réel de Corrector dans le code de production
- Confirmer que publisher.py::Corrector est bien celui utilisé

---

## 6. Problèmes identifiés pour le refactoring

### P1 : Issue.extra non structuré
- Issue.extra contient 11 champs de tracking non structurés
- Impossible de requêter ces données
- Duplication (url/old_url, new_url/suggested_text)

### P2 : Pas de corrélation Issue ↔ Correction
- Issue et Correction ne partagent pas d'ID
- Impossible de tracer "quelle détection → quelle correction"

### P3 : Pas de tracking granulaire par URL
- AnalyzedTracker et PublishedTracker travaillent au niveau article
- Impossible de répondre "quelle URL modifiée quand ?"

### P4 : Tracking dispersé
- 3 systèmes parallèles (AnalyzedTracker JSON, PublishedTracker JSON, SQLite)
- Aucune source unique de vérité

### P5 : Pas de table DeadLink dédiée
- SQLite a 21 tables mais aucune dédiée aux DeadLink operations
- Les méta-données de tracking sont perdues après publication

---

## 7. Recommandations pour Phase 0 - Étape 0.3 (Baseline)

### Tests de baseline à créer

1. **Test Lien web mort avec archive**
   - Mock réseau pour simuler 404
   - Capturer Issue et Issue.extra
   - Vérifier que archive params sont ajoutés

2. **Test Ouvrage mort**
   - Mock réseau pour simuler 404
   - Vérifier que AUCUNE modification n'est appliquée
   - Vérifier que Issue est créé avec suggested_text=None

3. **Test URL nue dans <ref>**
   - Mock réseau pour simuler 404
   - Vérifier la conversion en {{Lien web}}
   - Vérifier les protections (patterns académiques)

4. **Test URL hors <ref>**
   - Mock réseau pour simuler 404
   - Vérifier que AUCUNE issue n'est créée

### Baseline à sauvegarder

Pour chaque test :
- Sortie JSON de Issue
- Sortie JSON de Issue.extra
- Sortie de corrected_content
- Logs du système

---

## 8. État de l'étape 0.2

**Complété :**
- ✅ Structure Issue caractérisée
- ✅ Issue.extra caractérisé (11 champs)
- ✅ AnalyzedTracker caractérisé (18 champs)
- ✅ PublishedTracker caractérisé (5 champs)
- ✅ Database caractérisé (21 tables)

**À compléter :**
- ⏳ Baseline (étape 0.3)
- ⏳ Investigation du comportement Corrector
