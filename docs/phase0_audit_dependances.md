# Phase 0 - Étape 0.1 : Audit de dépendances

**Date :** 2025-01-XX
**Objectif :** Cartographier les imports et consommateurs avant tout refactoring

---

## 1. DeadLinkAnalyzer

### Imports

**Qui importe DeadLinkAnalyzer :**
- `src/wikipedia_maintenance/analyzers/__init__.py` (ligne 7)
  ```python
  from .dead_links import DeadLinkAnalyzer
  ```

**Qui appelle analyze() :**
- `src/wikipedia_maintenance/orchestrator/orchestrator.py` (ligne 83)
  ```python
  dead_link_issues = self.dead_link_analyzer.analyze(content)
  ```
- `src/wikipedia_maintenance/orchestrator/automation_orchestrator.py` (ligne 1555)
  ```python
  issues = analyzer.analyze(content)
  ```

**Qui consomme Issue :**
- `DeadLinkAnalyzer` lui-même (écriture via `self.issues.append()`)
- `ReferenceEnricherAnalyzer` (écriture via `self.issues.append()`)
- `Orchestrator` (lecture, combine issues)
- `Corrector` (lecture, application)

**Qui consomme Issue.extra :**
- `DeadLinkAnalyzer` (écriture et lecture pour statut de réparation)
- Aucun autre consommateur identifié dans le code actuel

---

## 2. Corrector - Duplication

### utils/corrector.py::Corrector

**Exports :**
- Exporté dans `src/wikipedia_maintenance/utils/__init__.py` (ligne 6)
  ```python
  from .corrector import Corrector, Correction
  ```

**Imports directs :**
- Aucun import direct trouvé dans le code
- Disponible uniquement via `from wikipedia_maintenance.utils import Corrector`

**Utilisation réelle :**
- Apparemment NON UTILISÉ directement dans le code actuel
- L'export dans `__init__.py` suggère une utilisation historique ou future

### utils/publisher.py::Corrector

**Imports directs :**
- `src/wikipedia_maintenance/orchestrator/orchestrator.py` (ligne 19)
  ```python
  from ..utils.publisher import Corrector
  ```
- `src/wikipedia_maintenance/orchestrator/automation_orchestrator.py` (ligne 33)
  ```python
  from wikipedia_maintenance.utils.publisher import Publisher, Corrector
  ```

**Utilisation réelle :**
- **PRINCIPAL** : Utilisé par Orchestrator et AutomationOrchestrator
- Utilisé pour appliquer les corrections issues de DeadLinkAnalyzer

### Conclusion sur la duplication

**Stratégie recommandée :**
1. `utils/publisher.py::Corrector` est le principal utilisé → CONSERVER
2. `utils/corrector.py::Corrector` n'est pas importé directement → SUPPRIMER
3. Supprimer l'export de `utils/corrector.py::Corrector` dans `utils/__init__.py`
4. Supprimer le fichier `utils/corrector.py` après vérification qu'aucun code ne l'utilise

---

## 3. AnalyzedTracker

### Imports

**Qui importe AnalyzedTracker :**
- `src/wikipedia_maintenance/orchestrator/automation_orchestrator.py` (ligne 30)
  ```python
  from wikipedia_maintenance.utils.analyzed_tracker import AnalyzedTracker, AnalysisStatus, AnalysisRecord, get_analyzed_tracker
  ```
- `src/wikipedia_maintenance/orchestrator/scheduler.py` (ligne 19)
  ```python
  from wikipedia_maintenance.utils.analyzed_tracker import AnalyzedTracker, AnalysisStatus
  ```

**Qui écrit dans AnalyzedTracker :**
- `AutomationOrchestrator` (via `analyzed_tracker.record_analysis()`)
- `Scheduler` (via `analyzed_tracker`)

**Qui lit depuis AnalyzedTracker :**
- `AutomationOrchestrator` (via `analyzed_tracker.get_analyzed_but_not_published()`)
- `Scheduler` (via `analyzed_tracker`)

**Persistance :**
- JSON : `data/analyzed_articles.json`
- Singleton via `get_analyzed_tracker()`

---

## 4. PublishedTracker

### Imports

**Qui importe PublishedTracker :**
- `src/wikipedia_maintenance/orchestrator/automation_orchestrator.py` (ligne 34)
  ```python
  from wikipedia_maintenance.utils.published_tracker import PublishedTracker
  ```
- `src/wikipedia_maintenance/orchestrator/scheduler.py` (ligne 18)
  ```python
  from wikipedia_maintenance.utils.published_tracker import PublishedTracker
  ```
- `src/wikipedia_maintenance/utils/publisher.py` (ligne 23)
  ```python
  from .published_tracker import PublishedTracker
  ```
- `src/wikipedia_maintenance/retrievers/user_contribs.py` (ligne 14)
  ```python
  from ..utils.published_tracker import PublishedTracker
  ```
- `src/wikipedia_maintenance/retrievers/category.py` (ligne 13)
  ```python
  from ..utils.published_tracker import PublishedTracker
  ```
- `src/wikipedia_maintenance/retrievers/manual.py` (ligne 7)
  ```python
  from ..utils.published_tracker import PublishedTracker
  ```
- `src/wikipedia_maintenance/retrievers/petscan.py` (ligne 11)
  ```python
  from ..utils.published_tracker import PublishedTracker
  ```
- `src/wikipedia_maintenance/retrievers/file.py` (ligne 8)
  ```python
  from ..utils.published_tracker import PublishedTracker
  ```

**Qui écrit dans PublishedTracker :**
- `Publisher` (via `tracker.mark_as_published()`)
- `AutomationOrchestrator` (via `published_tracker.mark_as_published()`)
- `UserContribsRetriever` (via `tracker.mark_as_published()`)
- `CategoryRetriever` (via `tracker.mark_as_published()`)
- `ManualRetriever` (via `tracker.mark_as_published()`)
- `PetscanRetriever` (via `tracker.mark_as_published()`)
- `FileRetriever` (via `tracker.mark_as_published()`)

**Qui lit depuis PublishedTracker :**
- `Scheduler` (via `published_tracker` pour vérifier si déjà publié)
- Backend API (probablement, à vérifier)

**Persistance :**
- JSON : `data/published_articles.json`
- Pas de singleton (instances créées directement)

---

## 5. Écriture directe en SQLite

### Qui écrit directement en SQLite (DatabaseManager) :

**Identifié via grep sur "database" ou "conn.execute" :**
- `backend/api/routes/publication.py` (écrit dans `analysis_results`, `articles_to_analyze`)
- `scheduler.py` (via `database` parameter)
- `automation_orchestrator.py` (via `database` parameter)

**À vérifier plus en détail :**
- Quelles tables sont écrites par qui
- Quelles tables sont lues par qui

---

## 6. Flux de données actuel

```
Article content
    ↓
Orchestrator.analyze()
    ↓
DeadLinkAnalyzer.analyze() → Issue[] (avec Issue.extra)
    ↓
Orchestrator.combine_issues()
    ↓
Corrector.apply_corrections(issues) → Correction[]
    ↓
Publisher.publish() → Wikipedia API
    ↓
[PARALLÈLE]
    ↓
AnalyzedTracker.record_analysis() → JSON
    ↓
PublishedTracker.mark_as_published() → JSON
    ↓
DatabaseManager.update_*() → SQLite
```

---

## 7. Problèmes identifiés

### P1 : Duplication Corrector
- `utils/corrector.py::Corrector` existe mais n'est pas utilisé
- `utils/publisher.py::Corrector` est le principal
- **Action :** Supprimer `utils/corrector.py` après vérification

### P2 : Tracking dispersé
- AnalyzedTracker (JSON) pour articles analysés
- PublishedTracker (JSON) pour articles publiés
- DatabaseManager (SQLite) pour autres données
- **Action :** Migrer vers SQLite comme source unique

### P3 : Issue.extra non structuré
- Issue.extra contient des données de tracking non structurées
- Impossible de requêter ces données
- **Action :** Créer table dédiée dans SQLite

---

## 8. Recommandations pour Phase 0 - Étape 0.2

### Tests de caractérisation à créer

1. **Test de flux DeadLink → Issue → Correction**
   - Simuler un article avec un lien mort
   - Capturer Issue et Issue.extra
   - Capturer Correction
   - Documenter la structure exacte

2. **Test de flux AnalyzedTracker**
   - Simuler une analyse
   - Capturer ce qui est écrit dans AnalyzedTracker
   - Comparer avec DatabaseManager

3. **Test de flux PublishedTracker**
   - Simuler une publication
   - Capturer ce qui est écrit dans PublishedTracker
   - Comparer avec DatabaseManager

4. **Test de flux SQLite**
   - Simuler une analyse complète
   - Capturer toutes les écritures SQLite
   - Identifier les tables utilisées

---

## 9. État de l'audit

**Complété :**
- ✅ Cartographie des imports DeadLinkAnalyzer
- ✅ Cartographie des appels analyze()
- ✅ Cartographie des consommateurs Issue
- ✅ Cartographie des consommateurs Issue.extra
- ✅ Résolution de la duplication Corrector
- ✅ Cartographie AnalyzedTracker
- ✅ Cartographie PublishedTracker

**À compléter :**
- ⏳ Cartographie détaillée des écritures SQLite (par table)
- ⏳ Tests de caractérisation (étape 0.2)
- ⏳ Baseline (étape 0.3)
