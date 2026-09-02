# Versions du Bot OviX

## Identité Technique

| Élément | Information |
|---------|-------------|
| Nom du projet | OviX |
| Nom technique du bot | SynsOperatorBot (configuré dans bot_identity.py) |
| Compte Wikipédia | À configurer (par défaut: Sysoperator) |
| Version actuelle | 1.0.0 |
| Version du bot | 1.0 |
| User-Agent technique | WikipediaMaintenanceTool/1.0 (mode humain par défaut) |
| User-Agent bot | SynsOperatorBot/1.0 (mode bot après approbation) |
| Domaine d'intervention | Maintenance des liens et références |

---

## Historique des Versions

### Version 3.0.0 (Actuelle)

**Statut**: Version stable en développement

**Versions techniques**:
- Backend API: 1.0.0 (FastAPI)
- Core library: 1.0.0 (wikipedia_maintenance)
- Bot version: 1.0 (bot_identity.py)
- Version projet: 3.0.0 (changement majeur d'architecture)

**Architecture**:
- Frontend React avec pages spécialisées
- Backend FastAPI avec routes RESTful
- Base de données SQLite
- Multi-archivage (Internet Archive, CommonCrawl, Arquivo.pt)

**Fonctionnalités principales**:
- Détection parallèle des liens morts
- Classification des erreurs (permanentes/temporaires/ambiguës)
- Recherche de redirections et multi-archives
- Validation par système de preuves (3 preuves indépendantes)
- Remplacement ciblé des URLs
- Mode Dry-Run
- Publication contrôlée sur Wikipédia
- Orchestration automatisée avec scheduler
- Interface utilisateur moderne (React + FastAPI)
- Kill switch et monitoring
- Bot Telegram pour notifications

**Fichiers principaux**:
- `backend/api/main.py` - Point d'entrée FastAPI (version 1.0.0)
- `backend/api/__init__.py` - Version API (1.0.0)
- `src/wikipedia_maintenance/__init__.py` - Version core (1.0.0)
- `src/wikipedia_maintenance/utils/bot_identity.py` - Identité bot (version 1.0)
- `src/wikipedia_maintenance/analyzers/base.py` - Classe de base (version 1.0)
- `src/wikipedia_maintenance/analyzers/dead_links.py` - Analyseur principal
- `src/wikipedia_maintenance/orchestrator/scheduler.py` - Orchestrateur
- `frontend/src/pages/` - Pages React

**Configuration**:
- `config/config.yaml` - Configuration principale
- `config/academic_domains.yaml` - Domaines académiques
- `config/case_normalization_data.yaml` - Normalisation de cas
- Variables d'environnement pour bot_identity:
  - `BOT_NAME` (défaut: SynsOperatorBot)
  - `BOT_VERSION` (défaut: 1.0)
  - `OPERATOR_NAME` (défaut: Sysoperator)
  - `USE_BOT_USER_AGENT` (défaut: false)

---

### Version 2.0 (Réorganisation)

**Statut**: Version intermédiaire (non maintenue)

**Commit**: 394ac84 - Réorganisation du projet : déplacement des fichiers et mise à jour de la configuration

**Changements**:
- Déplacement des scripts d'automatisation vers scripts/
- Déplacement des fichiers de configuration vers config/
- Déplacement des fichiers de données mineures vers backend/data/
- Nettoyage des fichiers temporaires
- Mise à jour des imports pour categories_config
- Réécriture du README.md en français

**Architecture**:
- Interface Streamlit
- Script d'automatisation `app.py`
- Script d'automatisation `app_new.py` (version refactorisée)

**Fichiers historiques**:
- `app.py` - Application principale Streamlit
- `app_new.py` - Version refactorisée Streamlit

---

### Version 1.0 (Initiale)

**Statut**: Version historique (non maintenue)

**Commit**: db0c40d - Premier commit : Bot de maintenance Wikipédia avec améliorations de sécurité

**Caractéristiques**:
- Bot de maintenance Wikipédia initial
- Améliorations de sécurité
- Fonctionnalités de base de détection de liens morts

**Note**: Les versions 1.0 et 2.0 utilisent l'interface Streamlit qui n'est plus maintenue. L'architecture actuelle (version 3.0) utilise exclusivement React + FastAPI.

---

## Évolution du Projet

### Chronologie des Commits Principaux

**Version 1.0 (Initiale)**:
1. **db0c40d** - Premier commit : Bot de maintenance Wikipédia avec améliorations de sécurité
2. **352fe89** - Ajout rapport d'audit Git
3. **1b9090f** - Mise à jour README : clarification de la nature de l'outil
4. **85342a9** - Ajout template passwords.py.example

**Version 2.0 (Réorganisation)**:
5. **aaba298** - Réorganisation : déplacement de la documentation technique dans docs/
6. **f378a34** - Réorganisation : déplacement des fichiers test dans tests/
7. **394ac84** - Réorganisation du projet : déplacement des fichiers et mise à jour de la configuration

**Version 3.0 (Architecture Moderne)**:
8. **b15877e** - Migration complète vers architecture moderne React + FastAPI (+53,111 lignes, -20,135 lignes)
9. **06bc087** - Suppression des emojis du README.md pour une présentation plus professionnelle

---

## Différences entre Versions

### Architecture

| Aspect | Version 1.0 (Streamlit) | Version 2.0 (Streamlit réorganisé) | Version 3.0 (React + FastAPI) |
|--------|-------------------------|-------------------------------------|------------------------------|
| Frontend | Streamlit | Streamlit | React |
| Backend | Script Python | Script Python réorganisé | FastAPI |
| API | Non structurée | Non structurée | RESTful |
| Base de données | JSON trackers | JSON trackers | SQLite + JSON |
| Orchestration | Basique | Basique | Avancée (scheduler, kill switch) |
| Monitoring | Limité | Limité | Complet (Telegram, UI) |
| Organisation | Structure basique | Structure réorganisée | Architecture moderne |

### Fonctionnalités

| Fonctionnalité | Version 1.0 | Version 2.0 | Version 3.0 |
|--------------|-------------|-------------|-------------|
| Détection liens morts | ✅ | ✅ | ✅ |
| Multi-archivage | ✅ | ✅ | ✅ |
| Validation par preuves | ✅ | ✅ | ✅ |
| Mode Dry-Run | ✅ | ✅ | ✅ |
| Publication contrôlée | ✅ | ✅ | ✅ |
| Orchestration automatisée | Limitée | Limitée | ✅ Complète |
| Interface moderne | ❌ | ❌ | ✅ React |
| API RESTful | ❌ | ❌ | ✅ |
| Kill switch | ❌ | ❌ | ✅ |
| Notifications Telegram | ❌ | ❌ | ✅ |
| Statistiques avancées | ❌ | ❌ | ✅ |
| Organisation du projet | Basique | Réorganisée | Moderne |

---

## Configuration des Versions

### User-Agent

**Mode humain (par défaut, sans approbation bot)**:
```
Mozilla/5.0 (compatible; WikipediaMaintenanceTool/1.0; +https://fr.wikipedia.org/wiki/Discussion_utilisateur:Sysoperator)
```

**Mode bot (après approbation Wikipédia)**:
```
SynsOperatorBot/1.0 (https://fr.wikipedia.org/wiki/Discussion_utilisateur:SynsOperatorBot) - https://fr.wikipedia.org/wiki/Discussion_utilisateur:Sysoperator - https://github.com/Sabrsl/OviX
```

### Compte Wikipédia

- **Nom technique configuré**: SynsOperatorBot (via `bot_identity.py`)
- **Opérateur par défaut**: Sysoperator
- **Contact**: https://fr.wikipedia.org/wiki/Discussion_utilisateur:Sysoperator
- **Page de discussion bot**: https://fr.wikipedia.org/wiki/Discussion_utilisateur:SynsOperatorBot
- **Note**: Le compte Wikipédia réel doit être configuré via les variables d'environnement ou modifié dans `bot_identity.py`

### Domaine d'intervention

- Maintenance des liens et références
- Détection et réparation des liens morts
- Conversion HTTP → HTTPS
- Enrichissement des références

---

## Modules et Composants par Version

### Version 3.0 (Actuelle)

**Analyzers**:
- `dead_links.py` - Analyseur principal (Ultra-Simple Version)
- `reference_enricher_analyzer.py` - Enrichissement des références (Single-Objective Version)
- `base.py` - Classe de base (version 1.0)

**Utils** (40+ modules):
- `link_checker.py` - Vérification HTTP
- `link_validator.py` - Validation par preuves
- `redirect_finder.py` - Recherche de redirections
- `archive_provider.py` - Coordination multi-archives
- `commoncrawl_provider.py` - Provider CommonCrawl
- `arquivo_provider.py` - Provider Arquivo.pt
- `content_verifier.py` - Validation de contenu
- `api_throttler.py` - Rate limiting avancé
- `retry_handler.py` - Gestion des retries
- `safe_url_replacer.py` - Remplacement sécurisé
- `database.py` - Accès base de données
- `publisher.py` - Publication Wikipédia
- `gemini_client.py` - Client IA Gemini
- `kill_switch_manager.py` - Gestion kill switch
- `telegram_bot.py` - Bot Telegram
- `bare_url_helper.py` - Conversion URLs nues (Hardened version)
- `reference_template_helper.py` - Templates de références (Hardened version)

**Orchestrator**:
- `automation_orchestrator.py` - Orchestrateur avancé
- `scheduler.py` - Planificateur de tâches
- `telegram_bot.py` - Bot Telegram
- `kill_switch_manager.py` - Gestion kill switch
- `checklist.py` - Checklist de validation

**Retrievers**:
- `category.py` - Récupération par catégorie
- `user_contribs.py` - Récupération par contributions
- `petscan.py` - Récupération via PetScan
- `manual.py` - Récupération manuelle
- `file.py` - Récupération depuis fichier

**Backend API**:
- `main.py` - Point d'entrée FastAPI (version 1.0.0)
- `routes/analysis.py` - Routes d'analyse
- `routes/articles.py` - Gestion des articles
- `routes/system.py` - Contrôles système
- `routes/stats_v2.py` - Statistiques avancées
- `routes/publication.py` - Publication
- `routes/auth.py` - Authentification
- `routes/config.py` - Configuration
- `routes/diff.py` - Diff
- `routes/history.py` - Historique
- `routes/logs.py` - Logs
- `routes/settings.py` - Paramètres
- `routes/manual_review.py` - Revue manuelle
- `routes/migration.py` - Migration
- `routes/stats_compare.py` - Comparaison de statistiques
- `routes/article_scheduler.py` - Scheduler d'articles

**Frontend React**:
- `pages/ReadyToPublish.tsx` - Articles prêts à publication
- `pages/SystemKillSwitch.tsx` - Contrôle kill switch
- `pages/AnalysisResults.tsx` - Résultats d'analyse
- `pages/PublicationHistory.tsx` - Historique des publications
- `components/` - Composants React

---

## Roadmap Future

### Version 3.1.0 (Planifiée)

- Amélioration de l'interface utilisateur
- Nouveaux analyseurs de typographie
- Intégration avancée avec l'IA Gemini
- Optimisation des performances
- Nouveaux providers d'archivage
- Mise à jour de bot_identity vers 1.1

### Version 4.0.0 (Futur)

- Architecture microservices
- Support multi-langues
- Analyse sémantique avancée
- Collaboration communautaire
- Intégration avec d'autres projets de maintenance
- Refonte complète de l'identité bot

---

## Documentation Technique

Pour plus de détails sur chaque version, consultez:

- `docs/WIKI_DOCUMENTATION.md` - Documentation complète du bot
- `docs/IMPLEMENTATION_REPORT.md` - Rapport d'implémentation
- `docs/INFRASTRUCTURE_STATUS.md` - Statut de l'infrastructure
- `docs/DEPLOYMENT.md` - Guide de déploiement
- `docs/USER_GUIDE.md` - Guide utilisateur

---

## Notes de Version

### Version 3.0.0 (Actuelle)

**Commit**: b15877e - Migration complète vers architecture moderne React + FastAPI

**Changements majeurs**:
- Migration complète vers React + FastAPI (+53,111 lignes, -20,135 lignes)
- Backend FastAPI complet avec routes API (analysis, articles, auth, config, diff, history, logs, manual_review, migration, publication, settings, system, stats_v2)
- Frontend React avec TypeScript et Vite, pages spécialisées
- Base de données SQLite avec migrations et sauvegardes automatiques
- Système multi-archives (Wayback Machine, CommonCrawl, Arquivo.pt) avec fallback automatique
- Validation par preuves multiples (ORIGINAL_PAGE_EXISTS, CANDIDATE_PAGE_EXISTS, SAME_RESOURCE_CONFIRMED)
- Orchestrateur d'automatisation avec scheduler, bot Telegram et kill switch
- Détection parallèle des liens morts (5 workers, jusqu'à 50 liens par article)
- Classification intelligente des erreurs (DEAD, TEMPORARY_ERROR, REVIEW_REQUIRED, RATE_LIMITED)
- Réparation multi-stratégie (redirections prioritaires, puis archives)
- Remplacement ciblé des URLs (SafeUrlReplacer)
- Mode Dry-Run pour simulation sans publication
- Rate limiting avancé avec backoff exponentiel et randomisation
- Interface utilisateur moderne avec tableau de bord et monitoring

### Version 2.0 (Réorganisation)

**Commit**: 394ac84 - Réorganisation du projet : déplacement des fichiers et mise à jour de la configuration

**Changements**:
- Déplacement des scripts d'automatisation vers scripts/
- Déplacement des fichiers de configuration vers config/
- Déplacement des fichiers de données mineures vers backend/data/
- Nettoyage des fichiers temporaires
- Mise à jour des imports pour categories_config
- Réécriture du README.md en français

### Version 1.0 (Initiale)

**Commit**: db0c40d - Premier commit : Bot de maintenance Wikipédia avec améliorations de sécurité

**Caractéristiques**:
- Bot de maintenance Wikipédia initial
- Améliorations de sécurité
- Fonctionnalités de base de détection de liens morts
- Interface Streamlit
- JSON trackers pour le suivi

---

## Contact et Support

- **Compte Wikipédia**: SynsOperatorBot (configurable via bot_identity.py)
- **Opérateur**: Sysoperator (configurable)
- **Projet**: Maintenance des liens et références sur Wikipédia
- **Documentation**: Voir le dossier `docs/` pour plus d'informations
