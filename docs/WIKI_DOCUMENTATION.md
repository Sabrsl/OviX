<div style="border:1px solid #a3b0bf; background:#eef3f8; border-radius:4px; padding:0.8em 1.2em; margin-bottom:1em;">
[[Fichier:Ambox warning pn.svg|24px|alt=Attention]] '''Outil en cours de développement.''' OviX n'est pas encore déployé en production. Les fonctionnalités, seuils et comportements décrits ci-dessous peuvent évoluer avant toute mise en service.
</div>

'''OviX''' est un outil de maintenance conçu pour détecter, analyser et réparer les liens externes morts présents dans les articles Wikipédia.

Le projet automatise les étapes répétitives de vérification tout en conservant une approche prudente : un lien n'est jamais remplacé au seul motif qu'il renvoie une erreur. OviX recherche systématiquement des éléments de preuve permettant de confirmer qu'une nouvelle URL — ou une version archivée — correspond bien à la ressource originale avant de proposer une modification.__TOC__

== Aperçu ==

OviX combine plusieurs mécanismes complémentaires :

* vérification parallèle des liens ;
* classification des erreurs (permanentes / temporaires / ambiguës) ;
* recherche de redirections ;
* recherche dans les services d'archivage multiples (Wayback Machine, CommonCrawl, Arquivo.pt) ;
* vérification de la correspondance de contenu ;
* validation stricte des propositions de remplacement par système de preuves ;
* remplacement ciblé des URLs (et non global) ;
* mode {{Lang|en|Dry-Run}} (simulation sans publication) ;
* publication contrôlée sur Wikipédia ;
* suivi persistant des analyses et des publications ;
* orchestration automatisée avec scheduler et notifications ;
* interface utilisateur moderne (React + FastAPI).

== Fonctionnement général ==

L'analyse d'un article suit un pipeline en trois passes, volontairement séparées afin qu'une simple vérification de lien ne puisse jamais entraîner, à elle seule, une modification du contenu.

{| class="wikitable"
|-
! Passe !! Rôle
|-
| 1. Détection || Vérifier l'état de chaque lien externe de l'article
|-
| 2. Réparation || Rechercher et valider une nouvelle URL pour les liens morts
|-
| 3. Application || Appliquer uniquement les corrections retenues et validées
|}

<pre>
Article Wikipédia
       │
       ▼
Extraction des URLs
       │
       ▼
Vérification des liens (parallèle)
       │
       ├── HEALTHY ───────────────► Aucune action
       ├── TEMPORARY_ERROR ───────► Révision
       ├── REVIEW_REQUIRED ───────► Révision
       └── DEAD
            │
            ▼
       Recherche de redirection
            │
            ├── Redirection valide ──► Validation par preuves
            └── Redirection absente/rejetée
                    │
                    ▼
              Recherche multi-archives ──► Validation finale
                    │
                    ▼
             Proposition de correction ──► Diff / Dry-Run ──► Publication
</pre>

== Fonctionnalités principales ==

=== Détection parallèle ===
OviX vérifie plusieurs URLs simultanément grâce à un pool de threads ({{Lang|en|ThreadPoolExecutor}}). Jusqu'à 50 liens par article peuvent être analysés selon la configuration actuelle, avec 5 workers parallèles.

=== Classification des résultats ===
Chaque lien est classé afin de distinguer les liens réellement morts des erreurs susceptibles d'être temporaires :

{| class="wikitable"
|-
! État !! Signification !! Action
|-
| HEALTHY || Le lien fonctionne || Aucune action
|-
| DEAD || Le lien est considéré comme mort || Recherche de réparation
|-
| TEMPORARY_ERROR || L'erreur peut être temporaire || Révision
|-
| REVIEW_REQUIRED || Le résultat est ambigu || Révision
|-
| RATE_LIMITED || Limitation de taux (429) || Attente avec backoff
|}

Exemples documentés : les réponses 404 et 410, ainsi que les erreurs DNS ou SSL, sont classées ''DEAD''. Les {{Lang|en|timeouts}}, les erreurs 5xx et certains 403 sur des domaines académiques sont classés ''TEMPORARY_ERROR'' afin de limiter les faux positifs.

=== Réparation multi-stratégie ===
Pour un lien classé ''DEAD'', OviX tente d'abord de trouver une redirection. Si celle-ci ne peut être validée, le système recherche en second recours une version archivée de la ressource via plusieurs services d'archivage (Wayback Machine, CommonCrawl, Arquivo.pt) avec fallback automatique entre providers.

=== Validation par preuves ===
Le système utilise un mécanisme de validation basé sur trois types de preuves indépendantes :

# '''ORIGINAL_PAGE_EXISTS''' — Preuve que la page originale existait (via archive)
# '''CANDIDATE_PAGE_EXISTS''' — Preuve que la page candidate existe (vérification live)
# '''SAME_RESOURCE_CONFIRMED''' — Preuve que les deux pages représentent la même ressource

Chaque preuve nécessite des validations multiples : correspondance de domaine, similarité de chemin, correspondance de titre, correspondance de contenu, cohérence des redirections. Une réparation n'est confirmée que si '''les 3 preuves sont validées'''.

=== Remplacement ciblé ===
Le composant SafeUrlReplacer remplace l'occurrence exacte de l'URL fautive dans le wikitexte, plutôt que d'effectuer un remplacement global non contrôlé — ce qui évite toute substitution accidentelle d'une URL similaire mais distincte.

=== Mode Dry-Run ===
Le mode {{Lang|en|Dry-Run}} permet de visualiser l'intégralité des changements proposés sans publier aucune modification sur Wikipédia, pour faciliter la relecture humaine avant publication.

=== Suivi des traitements ===
OviX conserve un historique portant sur :
* les articles analysés ;
* les articles publiés ;
* les résultats détaillés des traitements ;
* l'état de l'automatisation et du scheduler.

=== Orchestration automatisée ===
Le système inclut un orchestrateur d'automatisation avec :
* '''Scheduler''' : Planification automatique des tâches
* '''Telegram Bot''' : Notifications en temps réel et contrôle à distance
* '''Kill Switch''' : Arrêt d'urgence du système
* '''Checklist''' : Validation avant publication
* '''Timing Manager''' : Gestion du timing des opérations

=== Architecture moderne ===
OviX utilise une architecture moderne composée de :
* '''Frontend React''' : Interface utilisateur avec pages spécialisées (ReadyToPublish, SystemKillSwitch, AnalysisResults, etc.)
* '''Backend FastAPI''' : API RESTful avec routes complètes (analysis, articles, auth, config, system, stats, etc.)
* '''Base de données SQLite''' : Stockage persistant avec migrations
* '''Multi-archivage''' : Fallback automatique entre Wayback Machine, CommonCrawl, Arquivo.pt

{{Note|L'interface Streamlit mentionnée dans certaines sections historiques n'est plus maintenue. L'architecture actuelle utilise exclusivement React + FastAPI.}}

---

== Flux de données ==

=== Récupération d'un article ===
Un article peut être récupéré depuis plusieurs sources via {{Lang|en|Pywikibot}} pour les interactions documentées avec l'API Wikipédia :

* Catégorie (CategoryRetriever)
* Contributions utilisateur (UserContribsRetriever)
* PetScan (PetscanRetriever)
* Liste de suivi (WatchlistRetriever)
* Entrée manuelle (ManualRetriever)
* Fichier (FileRetriever)

<pre>
Entrée utilisateur (catégorie / watchlist / recherche / PetScan)
        │
        ▼
Retriever approprié
        │
        ▼
API Wikipédia (Pywikibot)
        │
        ▼
Base de données SQLite + JSON Trackers
        │
        ▼
API FastAPI → Frontend React
</pre>

=== Analyse d'un article ===

<pre>
Contenu de l'article
        │
        ▼
DeadLinkAnalyzer.analyze()
        │
        ▼
Pass 1 — Détection (parallèle) ──► Pass 2 — Réparation (séquentielle) ──► Pass 3 — Application
        │
        ▼
Liste des problèmes avec preuves
</pre>

Pass 1 — Détection. Les URLs sont vérifiées en parallèle avec ThreadPoolExecutor (5 workers) ; les résultats sont mis en cache afin d'éviter des vérifications redondantes.

Pass 2 — Réparation. Pour chaque lien ''DEAD'', une redirection est recherchée en priorité ; à défaut, un mécanisme de secours interroge les services d'archivage multiples avec fallback automatique, puis vérifie et valide la candidate retenue via le système de preuves.

Pass 3 — Application. Une fois les réparations validées par les 3 preuves, SafeUrlReplacer applique les changements ciblés et une entrée de suivi ({{Lang|en|issue}}) est créée dans la base de données.

== Validation d'une réparation ==

Une redirection ou une archive n'est jamais considérée comme correcte par défaut. OviX s'appuie sur un système de '''trois preuves indépendantes''' pour valider une URL candidate :

# '''ORIGINAL_PAGE_EXISTS''' — Preuve que la page originale existait (via archive avec URL de capture et date)
# '''CANDIDATE_PAGE_EXISTS''' — Preuve que la page candidate existe (vérification live avec code HTTP)
# '''SAME_RESOURCE_CONFIRMED''' — Preuve que les deux pages représentent la même ressource (domaine, titre, contenu, redirections)

=== Critères de validation ===

Chaque preuve nécessite des validations spécifiques :

* '''Correspondance du domaine''' — le domaine ou sous-domaine de l'URL candidate doit rester cohérent avec celui de l'URL originale
* '''Similarité du chemin''' — le chemin de l'URL candidate doit présenter une similarité suffisante avec celui de l'URL d'origine
* '''Correspondance du titre''' — le titre de la ressource candidate doit correspondre à celui de la ressource originale, y compris lorsque cette information doit être extraite d'une archive
* '''Correspondance du contenu''' — comparaison du contenu entre original et candidat
* '''Cohérence des redirections''' — validation de la chaîne de redirection

Lorsque '''les 3 preuves sont validées**, la réparation peut être classée REPLACEMENT_CONFIRMED.

=== Recherche dans les archives multiples ===

Lorsque la redirection n'est pas suffisamment fiable, OviX recourt à un mécanisme de secours basé sur les services d'archivage multiples, comprenant notamment :

* validation syntaxique de l'URL ;
* recherche d'une archive disponible sur plusieurs providers (Wayback Machine, CommonCrawl, Arquivo.pt) ;
* nouvelle vérification de l'URL originale pour éviter les faux positifs ;
* vérification de l'accessibilité de l'archive avec retry et exponential backoff ;
* détection d'une éventuelle page d'erreur archivée (soft-404) ;
* '''fallback automatique''' entre providers si l'un échoue temporairement (503, 502, 429) ;
* validation finale du remplacement.

L'objectif est d'éviter qu'un lien mort soit remplacé par une archive qui ne contient pas réellement la ressource recherchée, tout en maximisant les chances de trouver une archive valide via plusieurs sources.

=== Décisions de réparation ===

{| class="wikitable"
|-
! Décision !! Signification
|-
| REPLACEMENT_CONFIRMED || Le remplacement est suffisamment validé (3 preuves concordantes)
|-
| NO_ACTION || Aucune action requise (lien healthy ou erreur temporaire)
|-
| DEAD_NO_REPLACEMENT || Lien mort sans remplacement valide trouvé
|-
| REPAIR_REJECTED || Réparation rejetée (preuves insuffisantes ou validation échouée)
|-
| REPAIR_DIFF_REJECTED || Diff rejeté (changements non sécurisés détectés)
|-
| REPAIR_SKIPPED || La réparation automatique est désactivée
|-
| ARCHIVE_NOT_FOUND || Aucune archive disponible sur tous les providers
|-
| ARCHIVE_NOT_ACCESSIBLE || L'archive trouvée n'est pas accessible (tous providers échouent)
|}

== Configuration ==

La configuration principale se trouve dans <code>config/config.yaml</code>. Le fichier de configuration réel est beaucoup plus complet que l'exemple simplifié ci-dessous :

<syntaxhighlight lang="yaml">
dead_links_analyzer:
  confidence_threshold: 0.95
  enable_auto_repair: true
  max_checks_per_article: 50
  max_retries: 3
  prefer_redirect_over_archive: true
  timeout: 15

api_throttling:
  max_requests_per_minute: 10.0
  min_delay: 11.5
  min_delay_min: 8.0
  min_delay_max: 15.0
  random_delay: true
  max_requests_per_minute_min: 1
  max_requests_per_minute_max: 60

wikipedia:
  lang: fr
  family: wikipedia
  api_url: null
  user_agent: null
  timeout: 30.0

rate_limiting:
  min_edit_delay: 1.0
  max_edits_per_minute: 10
  max_requests_per_second: 2.0
  burst: 5

safety:
  dry_run_default: true
  require_confirmation: true
  max_article_batch_size: 50
  max_edits_per_session: 100
  max_change_bytes: 50000
</syntaxhighlight>

Un fichier de configuration distinct (<code>academic_domains.yaml</code>) permet de définir les domaines académiques traités spécifiquement lorsqu'ils renvoient des 403.

== Architecture du projet ==

Le projet est organisé en couches distinctes pour séparer l'interface, la logique métier, les services techniques et les mécanismes de suivi. L'architecture moderne comprend un frontend React, un backend FastAPI, et des services d'orchestration avancés.

<pre>
OviX/
├── app.py                     # Application principale (script d'automatisation)
├── run_automation.py          # Script d'automatisation
├── config/
│   ├── config.yaml            # Configuration principale
│   ├── config.example.yaml    # Exemple de configuration
│   └── academic_domains.yaml  # Domaines académiques whitelist
├── data/
│   ├── wikipedia_maintenance.db  # Base de données SQLite principale
│   ├── analyzed_articles.json    # Tracker des analyses
│   ├── published_articles.json    # Tracker des publications
│   ├── automation_state.json     # État de l'automatisation
│   ├── api_cache/                 # Cache des réponses API
│   └── automation_reports/        # Rapports d'automatisation
├── backend/                   # API FastAPI
│   ├── api/
│   │   ├── main.py           # Point d'entrée FastAPI
│   │   └── routes/           # Routes API (analysis, articles, auth, config, system, stats, etc.)
│   ├── stats/               # Service de statistiques
│   └── tests/              # Tests backend
├── frontend/               # Application React
│   ├── src/
│   │   ├── pages/         # Pages React (ReadyToPublish, SystemKillSwitch, AnalysisResults, etc.)
│   │   └── components/    # Composants React
│   └── package.json
├── src/wikipedia_maintenance/
│   ├── analyzers/
│   │   ├── dead_links.py      # Orchestrateur principal (DeadLinkAnalyzer)
│   │   └── base.py            # Classe de base pour les analyseurs
│   ├── utils/                 # 40+ modules utilitaires
│   │   ├── link_checker.py    # Vérificateur de liens HTTP
│   │   ├── link_validator.py   # Décision de réparation par preuves
│   │   ├── redirect_finder.py  # Recherche de redirections
│   │   ├── archive_provider.py # Accès multi-archives
│   │   ├── commoncrawl_provider.py  # Provider CommonCrawl
│   │   ├── arquivo_provider.py      # Provider Arquivo.pt
│   │   ├── content_verifier.py # Validation de contenu
│   │   ├── api_throttler.py    # Gestion du rate limiting avancée
│   │   ├── retry_handler.py    # Gestion des retries avec backoff
│   │   ├── safe_url_replacer.py  # Remplacement sécurisé d'URLs
│   │   ├── database.py         # Accès base de données
│   │   ├── publisher.py        # Publication sur Wikipédia
│   │   ├── gemini_client.py    # Client IA Gemini
│   │   ├── kill_switch_manager.py  # Gestion du kill switch
│   │   ├── telegram_bot.py     # Bot Telegram pour notifications
│   │   └── ... (30+ autres modules)
│   ├── retrievers/
│   │   ├── base.py            # Classe de base des retrievers
│   │   ├── category.py        # Récupération par catégorie
│   │   ├── user_contribs.py   # Récupération par contributions utilisateur
│   │   ├── petscan.py         # Récupération via PetScan
│   │   ├── manual.py          # Récupération manuelle
│   │   └── file.py            # Récupération depuis fichier
│   ├── orchestrator/
│   │   ├── automation_orchestrator.py  # Orchestrateur d'automatisation avancé
│   │   ├── scheduler.py       # Planificateur de tâches
│   │   ├── telegram_bot.py   # Bot Telegram pour notifications
│   │   ├── kill_switch_manager.py # Gestion du kill switch
│   │   └── checklist.py       # Checklist de validation
│   └── trackers/
│       ├── published_tracker.py  # Tracking des publications
│       └── analyzed_tracker.py   # Tracking des analyses
├── scripts/                 # Scripts utilitaires et migrations
├── state/                   # Gestion d'état
└── docs/                    # Documentation
</pre>

=== Rôle des principaux composants ===

{| class="wikitable"
|-
! Composant !! Rôle
|-
| colspan="2" style="background:#f0f0f0;" | Frontend React
|-
| ReadyToPublish.tsx || Gestion des articles prêts à publication avec validation
|-
| SystemKillSwitch.tsx || Contrôle du kill switch système avec monitoring
|-
| AnalysisResults.tsx || Affichage détaillé des résultats d'analyse avec diffs
|-
| PublicationHistory.tsx || Historique complet des publications avec filtres
|-
| colspan="2" style="background:#f0f0f0;" | Backend FastAPI
|-
| routes/analysis.py || Routes d'analyse de liens
|-
| routes/articles.py || Gestion des articles
|-
| routes/system.py || Contrôles système et monitoring
|-
| routes/stats_v2.py || Statistiques avancées
|-
| colspan="2" style="background:#f0f0f0;" | analyzers/
|-
| <code>dead_links.py</code> || Orchestration des étapes de détection et de réparation ({{Lang|en|DeadLinkAnalyzer}})
|-
| <code>base.py</code> || Éléments communs aux analyseurs
|-
| colspan="2" style="background:#f0f0f0;" | utils/ (40+ modules)
|-
| <code>link_checker.py</code> || Vérification HTTP des URLs avec gestion académique
|-
| <code>link_validator.py</code> || Validation par preuves (ORIGINAL_PAGE_EXISTS, CANDIDATE_PAGE_EXISTS, SAME_RESOURCE_CONFIRMED)
|-
| <code>redirect_finder.py</code> || Recherche de redirections avec critères déterministes
|-
| <code>archive_provider.py</code> || Coordination multi-archives avec fallback automatique
|-
| <code>commoncrawl_provider.py</code> || Provider CommonCrawl pour archives web massives
|-
| <code>arquivo_provider.py</code> || Provider Arquivo.pt pour archives portugaises
|-
| <code>content_verifier.py</code> || Comparaison de contenu et validation de ressource
|-
| <code>api_throttler.py</code> || Limitation des requêtes avec exponential backoff et randomisation
|-
| <code>retry_handler.py</code> || Gestion des retries avec stratégies de backoff
|-
| <code>safe_url_replacer.py</code> || Remplacement sécurisé des URLs (occurrence exacte)
|-
| <code>database.py</code> || Accès base de données SQLite avec migrations
|-
| <code>publisher.py</code> || Publication sur Wikipédia via Pywikibot
|-
| <code>gemini_client.py</code> || Client IA Gemini pour analyse avancée
|-
| <code>kill_switch_manager.py</code> || Gestion du kill switch avec monitoring
|-
| <code>telegram_bot.py</code> || Bot Telegram pour notifications et contrôle
|-
| colspan="2" style="background:#f0f0f0;" | retrievers/
|-
| <code>category.py</code> || Récupération d'articles depuis une catégorie
|-
| <code>user_contribs.py</code> || Récupération par contributions utilisateur
|-
| <code>petscan.py</code> || Récupération via PetScan
|-
| <code>manual.py</code> || Récupération manuelle
|-
| colspan="2" style="background:#f0f0f0;" | orchestrator/
|-
| <code>automation_orchestrator.py</code> || Orchestrateur d'automatisation avancé (80KB)
|-
| <code>scheduler.py</code> || Planificateur de tâches avec gestion d'état
|-
| <code>telegram_bot.py</code> || Bot Telegram pour notifications
|-
| <code>kill_switch_manager.py</code> || Gestion du kill switch
|-
| <code>checklist.py</code> || Checklist de validation avant publication
|-
| colspan="2" style="background:#f0f0f0;" | trackers/
|-
| <code>published_tracker.py</code> || Suivi des publications
|-
| <code>analyzed_tracker.py</code> || Suivi des analyses
|}

== Gestion du débit des requêtes (rate limiting) ==

OviX distingue deux mécanismes de throttler avec gestion avancée du rate limiting.

{| class="wikitable"
|-
! !! Throttler global !! Throttler dédié aux liens
|-
| Usage || Opérations générales, API Wikipédia || Vérification des liens, redirections, archives
|-
| Débit || 10 requêtes/minute (configurable) || 30 requêtes/minute
|-
| Délai minimal || 11,5 secondes (randomisation 8-15s) || 2 secondes
|-
| Randomisation || Activée par défaut (min_delay_min/max_delay_max) || Non applicable
|-
| Exponential backoff || Activé automatiquement sur 429 || Activé automatiquement sur 429
|-
| Configuration || Charge depuis config.yaml || Indépendante (load_from_config=false)
|}

Le throttling est conçu pour limiter la charge sur les services externes tout en permettant la vérification parallèle des liens. Le système inclut :

* '''Randomisation avancée''' : Délai aléatoire entre min_delay_min et max_delay_max pour éviter les patterns
* '''Exponential backoff''' : Multiplication par 2^n (jusqu'à n=5) sur 429 consécutifs
* '''Gestion parallèle''' : time.sleep() exécuté hors du verrou pour permettre le vrai parallélisme
* '''Reset automatique''' : Remise à zéro du compteur de 429 sur succès

=== Gestion des 429 ===

Le système gère automatiquement les réponses HTTP 429 :

1. '''Détection''' : report_429() appelé sur réception de 429
2. '''Backoff''' : Exponential backoff automatique (2^n jusqu'à n=5)
3. '''Reset''' : report_success() reset le compteur de 429
4. '''Logging''' : Avertissements automatiques sur 429 consécutifs

== Gestion des erreurs ==

=== Erreurs DNS et SSL ===
Les erreurs suivantes sont actuellement traitées comme des erreurs permanentes (DEAD) :
* <code>getaddrinfo failed</code> — Échec DNS (domaine inexistant)
* <code>certificate has expired</code> — Certificat SSL expiré
* <code>certificate verify failed</code> — Certificat SSL invalide

=== Erreurs temporaires ===
Les cas suivants sont considérés comme temporaires (TEMPORARY_ERROR) :
* <code>timed out</code> — Timeout de connexion
* <code>ConnectionRefusedError</code> — Serveur inaccessible
* <code>ConnectionResetError</code> — Connexion réinitialisée
* Codes de réponse HTTP 5xx — Erreurs serveur temporaires

=== Sites académiques ===
Certains domaines académiques peuvent répondre 403 aux requêtes automatisées sans que la ressource soit nécessairement morte. Ils sont donc traités comme des cas temporaires (TEMPORARY_ERROR) plutôt que permanents.

La liste des domaines académiques est configurée dans <code>academic_domains.yaml</code> et inclut notamment : sciencedirect.com, springer.com, wiley.com, nature.com, jstor.org, sagepub.com, etc.

=== Erreurs d'archives ===
Les erreurs spécifiques aux archives sont gérées avec distinction :

* '''ARCHIVE_NOT_FOUND''' — Aucune archive disponible sur tous les providers
* '''ARCHIVE_NOT_ACCESSIBLE''' — Archive non accessible (erreurs HTTP sur tous les providers)
* '''ARCHIVE_CONTENT_SUSPICIOUS''' — Archive trouvée mais contenu suspect (page 404 archivée)
* '''REVIEW_REQUIRED''' — Archive disponible mais service temporairement indisponible (503, 502, 429)

== Articles connexes ==

* [[Wikipédia:Liens externes]]
* [[Wikipédia:Vérifiabilité]]

### Composants Principaux

```
OviX/
├── app.py                     # Application principale (script d'automatisation)
├── run_automation.py          # Script d'automatisation
├── config/
│   ├── config.yaml            # Configuration principale
│   ├── config.example.yaml    # Exemple de configuration
│   └── academic_domains.yaml  # Domaines académiques whitelist
├── data/
│   ├── wikipedia_maintenance.db  # Base de données SQLite principale
│   ├── ovix.db                # Base de données secondaire
│   ├── analyzed_articles.json  # Tracker des analyses
│   ├── published_articles.json  # Tracker des publications
│   ├── automation_state.json   # État de l'automatisation
│   ├── api_cache/             # Cache des réponses API
│   └── automation_reports/    # Rapports d'automatisation
├── backend/                   # API FastAPI
│   ├── api/
│   │   ├── main.py           # Point d'entrée FastAPI
│   │   ├── routes/           # Routes API
│   │   │   ├── analysis.py  # Routes d'analyse
│   │   │   ├── articles.py  # Routes d'articles
│   │   │   ├── auth.py      # Routes d'authentification
│   │   │   ├── config.py    # Routes de configuration
│   │   │   ├── diff.py      # Routes de diff
│   │   │   ├── history.py   # Routes d'historique
│   │   │   ├── logs.py      # Routes de logs
│   │   │   ├── manual_review.py  # Routes de révision manuelle
│   │   │   ├── migration.py # Routes de migration
│   │   │   ├── publication.py  # Routes de publication
│   │   │   ├── settings.py  # Routes de paramètres
│   │   │   ├── system.py    # Routes système
│   │   │   └── stats_v2.py  # Routes de statistiques
│   ├── stats/               # Service de statistiques
│   │   ├── service.py      # Logique métier statistiques
│   │   ├── repository.py   # Accès données statistiques
│   │   └── schemas.py      # Schémas de données
│   ├── tests/              # Tests backend
│   └── utils/              # Utilitaires backend
├── frontend/               # Application React
│   ├── src/
│   │   ├── pages/         # Pages React
│   │   │   ├── ReadyToPublish.tsx
│   │   │   ├── SystemKillSwitch.tsx
│   │   │   ├── AnalysisResults.tsx
│   │   │   ├── PublicationHistory.tsx
│   │   │   ├── ArticlesToAnalyze.tsx
│   │   │   └── AnalyzedHistory.tsx
│   │   └── components/    # Composants React
│   ├── package.json
│   └── vite.config.ts
├── src/wikipedia_maintenance/
│   ├── analyzers/
│   │   ├── dead_links.py      # Orchestrateur principal (DeadLinkAnalyzer)
│   │   └── base.py            # Classe de base pour les analyseurs
│   ├── utils/
│   │   ├── link_checker.py    # Vérificateur de liens HTTP
│   │   ├── link_validator.py   # Décision de réparation par preuves
│   │   ├── redirect_finder.py  # Recherche de redirections
│   │   ├── archive_provider.py # Accès multi-archives (Wayback, CommonCrawl, Arquivo)
│   │   ├── commoncrawl_provider.py  # Provider CommonCrawl
│   │   ├── arquivo_provider.py      # Provider Arquivo.pt
│   │   ├── content_verifier.py # Validation de contenu
│   │   ├── api_throttler.py    # Gestion du rate limiting avancée
│   │   ├── https_verification_service.py  # Vérification HTTPS
│   │   ├── safe_url_replacer.py  # Remplacement sécurisé d'URLs
│   │   ├── performance_optimizer.py  # Optimisation de performance
│   │   ├── retry_handler.py    # Gestion des retries avec backoff
│   │   ├── config.py           # Gestion de configuration
│   │   ├── database.py         # Accès base de données
│   │   ├── publisher.py        # Publication sur Wikipédia
│   │   ├── corrector.py        # Corrections avancées
│   │   ├── gemini_client.py    # Client IA Gemini
│   │   ├── lia_client.py       # Client LIA
│   │   ├── kill_switch_manager.py  # Gestion du kill switch
│   │   ├── bot_discussion.py   # Gestion des discussions bot
│   │   ├── talk_page_monitor.py # Surveillance des pages de discussion
│   │   ├── api_cache.py        # Cache des appels API
│   │   ├── automation_report.py # Génération de rapports
│   │   ├── automation_state.py # Gestion de l'état d'automatisation
│   │   ├── structured_logging.py  # Logging structuré
│   │   ├── ui_settings.py      # Paramètres UI
│   │   ├── edit_summaries.py   # Résumés d'édition
│   │   ├── reference_utils.py  # Utilitaires de références
│   │   ├── connection_checker.py # Vérification de connexion
│   │   ├── https_verification_cache.py # Cache HTTPS
│   │   ├── bot_identity.py     # Identité du bot
│   │   ├── pending_publish_queue.py # File de publication
│   │   ├── secure_credentials.py # Gestion sécurisée des credentials
│   │   ├── archive_health_check.py # Vérification santé archives
│   │   ├── candidate_finder.py # Recherche de candidats
│   │   └── analyzed_tracker.py # Tracking des analyses
│   ├── retrievers/
│   │   ├── base.py            # Classe de base des retrievers
│   │   ├── category.py        # Récupération par catégorie
│   │   ├── user_contribs.py   # Récupération par contributions utilisateur
│   │   ├── petscan.py         # Récupération via PetScan
│   │   ├── manual.py          # Récupération manuelle
│   │   └── file.py            # Récupération depuis fichier
│   ├── orchestrator/
│   │   ├── automation_orchestrator.py  # Orchestrateur d'automatisation avancé
│   │   ├── scheduler.py       # Planificateur de tâches
│   │   ├── scheduler_state.py # État du scheduler
│   │   ├── timing_manager.py  # Gestion du timing
│   │   ├── telegram_bot.py   # Bot Telegram pour notifications
│   │   ├── checklist.py       # Checklist de validation
│   │   └── orchestrator.py    # Orchestrateur de base
├── scripts/                 # Scripts utilitaires
│   ├── audit_status.py
│   ├── check_article_status.py
│   ├── migrate_json_to_sqlite.py
│   └── ...
├── state/                   # Gestion d'état
├── docs/                    # Documentation
└── requirements.txt         # Dépendances Python
```

### Diagramme d'Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    React Frontend (Modern UI)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ReadyTo   │  │System    │  │Analysis  │  │Publication   │  │
│  │Publish   │  │KillSwitch│  │Results   │  │History       │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │             │             │                │           │
└───────┼─────────────┼─────────────┼────────────────┼───────────┘
        │             │             │                │
        ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (REST API)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Routes: analysis │ articles │ auth │ config │ system    │   │
│  │         stats │ history │ logs │ publication │ settings   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │             │             │                │
        ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Analyzers Layer                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              DeadLinkAnalyzer                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ Pass 1:      │  │ Pass 2:      │  │ Pass 3:      │   │   │
│  │  │ Parallel     │  │ Sequential   │  │ Apply        │   │   │
│  │  │ Check        │  │ Repair       │  │ Changes      │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │             │             │                │
        ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Utils Layer                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
│  │LinkChecker│ │Redirect  │ │Multi-    │ │Content       │     │
│  │          │ │Finder    │ │Archive   │ │Verifier      │     │
│  └──────────┘ └──────────┘ │Provider  │ └──────────────┘     │
│  ┌──────────┐ ┌──────────┘ └──────────┘ ┌──────────────┐     │
│  │API       │ │Retry     │ │Gemini        │     │
│  │Throttler │ │Handler   │ │Client        │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
│  │Publisher │ │Database  │ │Kill      │ │Telegram      │     │
│  │          │ │          │ │Switch    │ │Bot           │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
        │             │             │                │
        ▼             ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
│  │Wikipedia │ │Wayback   │ │Common    │ │Arquivo       │     │
│  │API       │ │Machine   │ │Crawl     │ │.pt           │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
│  │Pywikibot │ │Gemini    │ │Telegram  │ │SQLite DB     │     │
│  │          │ │AI        │ │API       │ │              │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture Moderne (React + FastAPI)

### Frontend React

L'interface utilisateur moderne utilise React avec les pages principales :

* '''ReadyToPublish.tsx''' — Gestion des articles prêts à publication avec validation
* '''SystemKillSwitch.tsx''' — Contrôle du kill switch système avec monitoring
* '''AnalysisResults.tsx''' — Affichage des résultats d'analyse avec diffs
* '''PublicationHistory.tsx''' — Historique complet des publications avec filtres
* '''ArticlesToAnalyze.tsx''' — Queue d'articles à analyser avec priorisation
* '''AnalyzedHistory.tsx''' — Historique des analyses avec statistiques

### Backend FastAPI

L'API RESTful fournit les routes suivantes :

* '''analysis.py''' — Routes d'analyse de liens
* '''articles.py''' — Gestion des articles
* '''auth.py''' — Authentification
* '''config.py''' — Configuration système
* '''diff.py''' — Génération de diffs
* '''history.py''' — Historique
* '''logs.py''' — Accès aux logs
* '''manual_review.py''' — Révision manuelle
* '''migration.py''' — Migrations de base de données
* '''publication.py''' — Publication sur Wikipédia
* '''settings.py''' — Paramètres
* '''system.py''' — Contrôles système
* '''stats_v2.py''' — Statistiques avancées

### Services de Statistiques

Le module <code>backend/stats/</code> fournit :
* <code>service.py</code> — Logique métier des statistiques
* <code>repository.py</code> — Accès aux données de statistiques
* <code>schemas.py</code> — Schémas de validation

## Architecture Moderne (React + FastAPI)

#### 1. Récupération d'Article (Architecture Moderne)

```
User Input (React UI)
    ↓
FastAPI Backend (/api/articles/retrieve)
    ↓
CategoryRetriever / UserContribsRetriever / PetscanRetriever
    ↓
Wikipedia API (pywikibot)
    ↓
SQLite Database + JSON Trackers
    ↓
API Response → React Frontend
```

#### 2. Analyse d'Article (Architecture Moderne)

```
React UI → Request Analysis
    ↓
FastAPI Backend (/api/analysis/analyze)
    ↓
DeadLinkAnalyzer.analyze()
    ↓
Pass 1: Parallel Link Check (ThreadPoolExecutor)
    ├─ LinkChecker.check_link() → LinkCheckResult
    ├─ Classification: DEAD/HEALTHY/TEMPORARY_ERROR/REVIEW_REQUIRED
    └─ _check_cache[url] = result
    ↓
Pass 2: Sequential Repair
    ├─ For each DEAD link:
    │   ├─ RedirectFinder.find_redirect()
    │   ├─ ContentVerifier.verify_same_resource()
    │   ├─ Multi-ArchiveProvider.verify_content_match()
    │   │   ├─ Wayback Machine
    │   │   ├─ CommonCrawl
    │   │   └─ Arquivo.pt
    │   ├─ LinkValidator.validate_repair() (Proof-based)
    │   └─ If rejected: _attempt_archive_fallback()
    └─ RepairResult → _repair_cache[url]
    ↓
Pass 3: Apply Changes
    ├─ SafeUrlReplacer.replace_exact_occurrence()
    ├─ Content update
    └─ Issue creation
    ↓
Database Storage → API Response → React UI
```

#### 3. Publication (Architecture Moderne)

```
React UI → Request Publication
    ↓
FastAPI Backend (/api/publication/publish)
    ↓
Kill Switch Check
    ↓
Dry-run validation
    ↓
If dry_run: Show diff only
    ↓
If not dry_run:
    ├─ Publisher.publish() via Pywikibot
    ├─ Database record (SQLite)
    ├─ PublishedTracker.record()
    ├─ Telegram notification (if configured)
    └─ API Response → React UI
```

### Interactions Entre Composants

#### DeadLinkAnalyzer ↔ Utils

```
DeadLinkAnalyzer
    ├─→ LinkChecker.check_link(url)
    │   ←─ LinkCheckResult
    ├─→ RedirectFinder.find_redirect(url)
    │   ←─ RedirectResult
    ├─→ ContentVerifier.verify_same_resource(original, candidate)
    │   ←─ ContentVerificationResult
    ├─→ ArchiveProvider.check_archive(url)
    │   ←─ ArchiveResult
    ├─→ LinkValidator.validate_repair(check_result, redirect_result, archive_evidence)
    │   ←─ RepairResult
    └─→ SafeUrlReplacer.replace_exact_occurrence(content, old_url, new_url, position)
        ←─ ReplacementResult
```

#### UI ↔ Application Layer

```
React Frontend
    ├─→ API Request (/api/articles/retrieve)
    │   ←─ JSON Response
    ├─→ API Request (/api/analysis/analyze)
    │   ←─ JSON Response
    ├─→ API Request (/api/publication/publish)
    │   ←─ JSON Response
    └─→ State Management (React hooks)
```

#### Orchestrator ↔ Analyzers

```
AutomationOrchestrator
    ├─→ CategoryRetriever.fetch_articles(category)
    │   ←─ List[Article]
    ├─→ DeadLinkAnalyzer.analyze(article)
    │   ←─ List[Issue]
    └─→ Publisher.publish(article, content)
        ←─ bool (success)
```

### Flux de Traitement

#### Phase 1 : Détection Parallèle (Pass 1)

```python
# ThreadPoolExecutor avec 5 workers
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(link_checker.check_link, url): url for url in urls}
    for future in as_completed(futures):
        result = future.result()
        _check_cache[url] = result
```

**Caractéristiques :**
- Vérification simultanée de 50 liens maximum par article
- Cache des résultats pour éviter les doublons
- Classification automatique : `DEAD`, `HEALTHY`, `TEMPORARY_ERROR`, `REVIEW_REQUIRED`

#### Phase 2 : Réparation Séquentielle (Pass 2)

```python
for match in valid_matches:
    url = match.group(0)
    result = _check_cache[url]
    
    if result.status == LinkStatus.DEAD:
        # 1. Recherche de redirection
        redirect_result = redirect_finder.find_redirect(url)
        
        if redirect_result and redirect_result.decision == "valid_redirect":
            # Validation du contenu
            content_result = content_verifier.verify_same_resource(url, redirect_result.redirected_url)
            archive_evidence = archive_provider.verify_content_match(url, redirect_result.redirected_url)
            
            # Décision de réparation
            repair_result = link_validator.validate_repair(...)
            
            if repair_result.decision != REPLACEMENT_CONFIRMED:
                # 2. Fallback archive si redirect rejeté
                repair_result = _attempt_archive_fallback(url, ...)
        else:
            # Pas de redirect → tentative archive directe
            repair_result = _attempt_archive_fallback(url, ...)
```

---

## Classification des Liens

### États de Lien (LinkStatus)

| État | Description | Action |
|------|-------------|--------|
| `DEAD` | Lien définitivement mort (404, 410, DNS failure, SSL expired) | Tentative de réparation |
| `HEALTHY` | Lien fonctionnel (HTTP 200-299) | Aucune action |
| `TEMPORARY_ERROR` | Erreur temporaire (timeout, 5xx, 403 académique) | Révision manuelle |
| `REVIEW_REQUIRED` | Cas ambigu (403 non académique, 402) | Révision manuelle |

### Décisions de Réparation (RepairDecision)

| Décision | Description | Condition |
|----------|-------------|-----------|
| `REPLACEMENT_CONFIRMED` | Réparation validée | 3 preuves concordantes |
| `REPAIR_FAILED` | Échec de réparation | Preuves insuffisantes |
| `REPAIR_SKIPPED` | Réparation ignorée | Auto-répair désactivé |
| `ARCHIVE_NOT_FOUND` | Aucune archive disponible | Wayback vide |
| `ARCHIVE_NOT_ACCESSIBLE` | Archive inaccessible | Erreur HTTP archive |

### Système de Preuves (Proof-Based Validation)

Le système utilise 3 types de preuves indépendantes :

1. **ORIGINAL_PAGE_EXISTS** : Preuve que la page originale existait (via archive)
2. **CANDIDATE_PAGE_EXISTS** : Preuve que la page candidate existe (vérification live)
3. **SAME_RESOURCE_CONFIRMED** : Preuve que les deux pages représentent la même ressource

Chaque preuve nécessite des validations multiples :
- Correspondance de domaine
- Similarité de chemin
- Correspondance de titre
- Correspondance de contenu
- Cohérence des redirections

Une réparation n'est confirmée que si **les 3 preuves sont validées**.

---

## Configuration

### Fichier de Configuration (`config/config.yaml`)

Le fichier de configuration réel est beaucoup plus complet que l'exemple simplifié :

```yaml
# Configuration principale (extrait)
dead_links_analyzer:
  confidence_threshold: 0.95
  enable_auto_repair: true
  max_checks_per_article: 50
  max_retries: 3
  prefer_redirect_over_archive: true
  timeout: 15

api_throttling:
  max_requests_per_minute: 10.0
  min_delay: 11.5
  min_delay_min: 8.0
  min_delay_max: 15.0
  random_delay: true
  max_requests_per_minute_min: 1
  max_requests_per_minute_max: 60

# Configuration supplémentaire
wikipedia:
  lang: fr
  family: wikipedia
  api_url: null
  user_agent: null
  timeout: 30.0

rate_limiting:
  min_edit_delay: 1.0
  max_edits_per_minute: 10
  max_requests_per_second: 2.0
  burst: 5

analysis:
  enabled_analyzers:
    - DeadLinkAnalyzer
  min_severity: all
  disabled_issue_types: []
  issue_overrides: {}
  parallel: false
  analyzer_timeout: 60.0

database:
  path: data/wikipedia_maintenance.db
  backup_enabled: true
  backup_interval_hours: 24
  max_backups: 7

safety:
  dry_run_default: true
  require_confirmation: true
  max_article_batch_size: 50
  max_edits_per_session: 100
  max_change_bytes: 50000

# Configuration des analyseurs supplémentaires
typography:
  check_nbsp: true
  check_ordinal_abbreviations: true
  check_percent_nbsp: false
  check_double_spaces: true
  # ... (plusieurs options)

references:
  check_bare_refs: true
  check_duplicate_refs: true
  check_uppercase_refs: true
  check_isbn_format: true
  use_wayback_api: false
  link_check_timeout: 5.0

https_verification:
  enabled: false
  timeout: 10.0
  ttl_available: 30
  ttl_unavailable: 7
  ttl_failed: 1
```

### Configuration Académique (`config/academic_domains.yaml`)

Liste des domaines académiques connus pour bloquer les bots avec HTTP 403 :

```yaml
academic_publisher_domains:
  - jstor.org
  - springer.com
  - wiley.com
  - sciencedirect.com
  - sagepub.com
  - taylorfrancis.com
  - cambridge.org
  - oup.com
  - nature.com
  - ...
```

Ces domaines sont classés comme `TEMPORARY_ERROR` (révision manuelle) plutôt que `DEAD`.

---

## Algorithme de Réparation

### Critères de Validation

Un redirect est validé uniquement si **3 preuves** concordent :

1. **Domain Match** : Même domaine ou sous-domaine
2. **Path Similarity** : Similarité ≥ 0.5 entre chemins
3. **Title Match** : Titres identiques (via archive si original mort)

### Fallback Multi-Archive

Si un redirect existe mais est rejeté (preuves insuffisantes), le système tente automatiquement une réparation via **multi-archives** avec fallback entre providers :

```python
def _attempt_archive_fallback(url, url_position, result, match):
    # 1. Vérification syntaxique
    if not _is_url_syntactically_valid(url):
        return None
    
    # 2. Recherche multi-archives
    archive_result = archive_provider.check_archive(url)
    
    # 3. Re-vérification original (éviter faux positifs)
    final_check = link_checker.check_link(url)
    if final_check.status != LinkStatus.DEAD:
        return None
    
    # 4. Vérification accessibilité archive avec retry
    retry_config = RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=8.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    )
    
    archive_check = retry_handler.execute_with_retry(
        lambda: link_checker.check_link(archive_url)
    )
    
    # 5. Fallback automatique entre providers si échec
    if archive_check.status != LinkStatus.HEALTHY:
        if archive_check.http_status_code in (503, 502, 429):
            # Service temporairement indisponible
            all_available_results = archive_provider.check_all_providers(url)
            other_providers = [r for r in all_available_results if r.provider != provider_name]
            
            for alt_result in other_providers:
                alt_check = retry_handler.execute_with_retry(
                    lambda: link_checker.check_link(alt_result.archive_url)
                )
                if alt_check.status == LinkStatus.HEALTHY:
                    # Utiliser le provider alternatif
                    archive_url = alt_result.archive_url
                    provider_name = alt_result.provider
                    archive_check = alt_check
                    break
    
    # 6. Détection contenu suspect (page 404 archivée)
    if _archive_content_looks_dead(archive_url):
        return None
    
    return RepairResult(
        decision=REPLACEMENT_CONFIRMED,
        replacement_url=archive_url,
        reason=f"Archive fallback: using {provider_name} from {archive_date}"
    )
```

### Providers d'Archives

Le système supporte plusieurs providers d'archives :

1. **Wayback Machine** (archive.org) - Provider principal
2. **CommonCrawl** - Archives web massives
3. **Arquivo.pt** - Archives portugaises
4. **Archive.today** - Archives instantanées

Le système effectue un **fallback automatique** entre providers si l'un échoue temporairement (503, 502, 429).

---

## Gestion du Rate Limiting

### Throttler Global

- **Limite** : 10 req/min (configurable via `max_requests_per_minute`)
- **Délai** : 11.5s (avec randomisation 8-15s via `min_delay_min/max_delay_max`)
- **Randomisation** : Activée par défaut (`random_delay: true`)
- **Exponential Backoff** : Activé automatiquement sur 429
- **Usage** : API Wikipédia, opérations générales

### Throttler Dédié (Liens)

- **Limite** : 30 req/min
- **Délai** : 2s
- **Isolation** : `load_from_config=False` (non écrasé par config.yaml)
- **Usage** : Vérification de liens, redirections, archives

### Optimisation Parallèle Avancée

```python
# time.sleep() HORS du verrou pour vrai parallélisme
def wait_if_needed(self):
    with self.lock:
        # Nettoyage des timestamps anciens
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < 60.0
        ]
        
        # Vérification rate limit
        effective_max_requests = max(
            self.max_requests_per_minute_min, 
            min(self.max_requests_per_minute, self.max_requests_per_minute_max)
        )
        
        # Calcul du délai avec randomisation
        if self.random_delay:
            effective_delay = random.uniform(
                self.min_delay_min, 
                self.min_delay_max
            )
        else:
            effective_delay = self.min_delay
        
        # Exponential backoff sur 429
        if self.consecutive_429s > 0:
            effective_delay = effective_delay * (2 ** min(self.consecutive_429s, 5))
        
        # Calcul du wait time
        wait_time = max(rate_wait, delay_wait)
        
        # Enregistrement immédiat du timestamp
        self.last_request_time = current_time
        self.request_timestamps.append(current_time)
    
    # Sleep HORS du lock pour permettre le parallélisme
    time.sleep(wait_time)
```

### Gestion des 429

Le système gère automatiquement les réponses 429 :

1. **Détection** : `report_429()` appelé sur réception de 429
2. **Backoff** : Exponential backoff automatique (2^n jusqu'à n=5)
3. **Reset** : `report_success()` reset le compteur de 429
4. **Logging** : Avertissements automatiques sur 429 consécutifs

---

## Headers HTTP Anti-Bot

Pour réduire les détections par anti-bot :

```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}
```

---

## Gestion des Erreurs

### Erreurs DNS/SSL

Les erreurs permanentes sont classées comme `DEAD` :

- `getaddrinfo failed` → DNS failure (domaine inexistant)
- `certificate has expired` → SSL expiré
- `certificate verify failed` → SSL invalide

### Erreurs Temporaires

Les erreurs temporaires sont classées comme `TEMPORARY_ERROR` :

- `timed out` → Timeout
- `ConnectionRefusedError` → Serveur inaccessible
- HTTP 5xx → Erreur serveur

### Cas Académiques 403

Les domaines académiques (whitelist) avec HTTP 403 sont classés comme `TEMPORARY_ERROR` pour éviter les faux positifs.

---

## Interface Utilisateur

### React Frontend (Architecture Moderne)

L'interface React moderne fournit :

1. **ReadyToPublish** : Gestion des articles prêts à publication avec validation
2. **SystemKillSwitch** : Contrôle du kill switch système avec monitoring
3. **AnalysisResults** : Affichage détaillé des résultats d'analyse avec diffs
4. **PublicationHistory** : Historique complet des publications avec filtres
5. **ArticlesToAnalyze** : Queue d'articles à analyser avec priorisation
6. **AnalyzedHistory** : Historique des analyses avec statistiques



---

## Orchestration et Automatisation

### Automation Orchestrator

L'orchestrateur d'automatisation (`automation_orchestrator.py`) gère :

- **Scheduler** : Planification automatique des tâches
- **Telegram Bot** : Notifications et monitoring
- **Kill Switch** : Arrêt d'urgence du système
- **Checklist** : Validation avant publication
- **Timing Manager** : Gestion du timing des opérations

### Scheduler

Le scheduler (`scheduler.py`) fournit :

- Planification basée sur le temps
- Gestion de l'état du scheduler (`scheduler_state.py`)
- Reprise après interruption
- Statistiques d'exécution

### Kill Switch Manager

Le gestionnaire de kill switch (`kill_switch_manager.py`) permet :

- Arrêt d'urgence immédiat
- Monitoring de l'état du système
- Interface UI pour contrôle
- Persistance de l'état

### Telegram Bot

Le bot Telegram (`telegram_bot.py`) fournit :

- Notifications en temps réel
- Commandes de contrôle à distance
- Rapports d'automatisation
- Alertes sur erreurs

## Base de Données

### Structure SQLite

Le projet utilise une base de données SQLite principale (`wikipedia_maintenance.db`) avec :

- **Tables multiples** : Articles, analyses, publications, issues
- **Migrations** : Scripts SQL pour mises à jour de schéma
- **Backups** : Sauvegardes automatiques
- **Indexation** : Optimisation des requêtes

### Scripts de Migration

Les scripts dans `scripts/` gèrent :

- `migrate_json_to_sqlite.py` : Migration de JSON vers SQLite
- `migrate_kill_switch_to_db.py` : Migration du kill switch
- `migrate_manual_review.py` : Migration de la révision manuelle
- Scripts d'audit et validation

### Trackers JSON

Les trackers JSON traditionnels sont maintenus pour compatibilité :

- `analyzed_articles.json` : Tracking des analyses
- `published_articles.json` : Tracking des publications
- `automation_state.json` : État de l'automatisation

## Déploiement

### Docker (Architecture Moderne)

```dockerfile
# Frontend React
FROM node:18-alpine as frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Backend FastAPI
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY backend/ ./backend
COPY src/ ./src
COPY config/ ./config
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (Architecture Moderne)

```yaml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - DATABASE_URL=sqlite:///data/wikipedia_maintenance.db
      - ENVIRONMENT=production
  
  frontend:
    build:
      context: .
      target: frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://backend:8000
```



### Installation Locale (Architecture Moderne)

```bash
# Cloner le dépôt
git clone https://github.com/yourusername/OviX.git
cd OviX

# Installer les dépendances Python
pip install -r requirements.txt

# Installer les dépendances Frontend
cd frontend
npm install
cd ..

# Configurer pywikibot
python -m pywikibot generate_user_files.py

# Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos credentials

# Lancer le backend FastAPI
uvicorn backend.api.main:app --reload --port 8000

# Lancer le frontend React (dans un autre terminal)
cd frontend
npm run dev
```



---

## Développement

### Structure du Code

- **Analyzers** : Logique métier de détection et réparation
- **Utils** : Services réutilisables (throttling, HTTP, validation)
- **UI** : Interface React (pages spécialisées, composants)
- **Orchestrator** : Coordination des tâches d'automatisation

### Tests

```bash
# Tests unitaires
pytest tests/

# Tests de compilation
python -m py_compile src/**/*.py

# Tests de performance
python -m pytest tests/performance/ --benchmark-only
```

### Logging

```python
logger.info(f"URL_CHECK | url={url} | http_status={status} | classification={classification}")
logger.warning(f"ARCHIVE_NOT_ACCESSIBLE | url={url} | archive_url={archive_url}")
logger.error(f"REPAIR_FAILED | url={url} | reason={reason}")
```

---

## Contribuer

### Guidelines

1. Respecter la structure existante des modules
2. Ajouter des tests pour toute nouvelle fonctionnalité
3. Documenter les changements dans le changelog
4. Utiliser le throttler dédié pour les appels HTTP externes
5. Maintenir la compatibilité avec Python 3.10+

### Pull Requests

- Forker le dépôt
- Créer une branche feature/`nom-de-la-fonctionnalité`
- Commiter avec des messages clairs
- Pusher et créer une Pull Request

---

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

## Contact

- **Auteur** : Sabrsl
- **Projet** : https://github.com/yourusername/OviX
- **Issues** : https://github.com/yourusername/OviX/issues
- **Documentation** : https://github.com/yourusername/OviX/wiki

---

## Changelog

### Version 3.0 (2026-08-20) - Architecture Moderne

- **Nouveau** : Frontend React avec pages modernes (ReadyToPublish, SystemKillSwitch, etc.)
- **Nouveau** : Backend FastAPI avec API RESTful complète
- **Nouveau** : Système multi-archives (Wayback, CommonCrawl, Arquivo.pt)
- **Nouveau** : Validation par preuves multiples (ORIGINAL_PAGE_EXISTS, CANDIDATE_PAGE_EXISTS, SAME_RESOURCE_CONFIRMED)
- **Nouveau** : Automation Orchestrator avec Scheduler et Telegram Bot
- **Nouveau** : Kill Switch Manager avec monitoring
- **Nouveau** : Base de données SQLite avec migrations
- **Nouveau** : Retry Handler avec exponential backoff
- **Nouveau** : Gemini Client pour analyse IA
- **Amélioré** : Rate limiting avec exponential backoff et randomisation avancée
- **Amélioré** : Fallback automatique entre providers d'archives
- **Amélioré** : Structure de configuration beaucoup plus complète
- **Amélioré** : Gestion de l'état d'automatisation persistante
- **Corrigé** : Cache validation pour éviter les réparations stale
- **Corrigé** : Vérification syntaxique des URLs avec validation percent-encoding

### Version 2.0 (2026-08-13)

- **Nouveau** : Détection parallèle avec 5 workers
- **Nouveau** : Throttler dédié pour les liens (30 req/min)
- **Amélioré** : Classification DNS/SSL comme DEAD
- **Amélioré** : Headers HTTP anti-bot
- **Corrigé** : Archive fallback après rejet de redirect
- **Corrigé** : Fallback archive pour titre dans content_verifier
- **Corrigé** : Initialisation session_state.site

### Version 1.0

- Version initiale avec détection séquentielle
- Réparation via redirections
- Interface Streamlit de base
