# Article Workflow - Cycle de Vie Complet par Article

## Vue d'ensemble

Le workflow article par article permet de suivre et gérer chaque article individuellement avec un cycle de vie visible et persistant. Chaque article conserve son propre état, ses résultats et son historique.

## Architecture

### Backend (Python)

**Structures existantes réutilisées:**
- `AnalyzedTracker` - Stocke les résultats d'analyse par article
- `PublishedTracker` - Suit les articles publiés
- `AutomationStateManager` - Gère l'état de traitement en cours
- `DatabaseManager` - Base de données SQLite pour l'historique

**Nouveaux endpoints API:**
- `GET /api/articles/{title}/status` - État actuel d'un article
- `GET /api/articles/history` - Historique des articles analysés
- `POST /api/articles/{title}/analyze` - Lancer une analyse
- `POST /api/articles/{title}/ignore` - Marquer comme ignoré

### Frontend (React)

**Composants créés:**
- `ArticleStatusCard` - Carte d'état avec progression visible
- `ArticleHistory` - Liste cliquable de l'historique
- `ArticleWorkflow` - Composant principal intégrant tout

**Page existante réutilisée:**
- `ArticleDetail` - Page de détail existante avec diff HTML, publication, navigation

**Route:**
- `/analysis/workflow` - Page principale du workflow

## Cycle de Vie d'un Article

### 1. État PENDING (○)
- Article en attente d'analyse
- Actions disponibles: "Start Analysis"

### 2. État ANALYZING (⏳)
- Analyse en cours avec **progression réelle depuis le backend**
- Polling automatique toutes les 3 secondes
- Barre de progression en temps réel (0-100%)
- Étape actuelle affichée (current_step)
- Temps écoulé affiché (elapsed_time)
- Statut des analyzers individuels (analyzers_status)
- **Pas de progression artificielle** - vient du backend/job/analyzers

### 3. État ANALYZED (✓)
- Analyse terminée avec résultats
- Nombre de problèmes détectés
- Résumé des corrections
- Actions disponibles: "View Details", "Re-analyze", "Publish", "Ignore"

### 4. État PUBLISHED (✓)
- Article publié sur Wikipedia
- Revision ID affiché
- Date de publication
- Actions disponibles: "View Details"

### 5. État REJECTED (✗)
- Article rejeté
- Actions disponibles: "View Details"

### 6. État IGNORED (⊘)
- Article ignoré (ne sera plus traité)
- Actions disponibles: "View Details"

### 7. État ERROR (✗)
- Erreur lors de l'analyse
- Actions disponibles: "Retry", "Ignore"

## Page de Détail d'Article

### Onglets disponibles:

**Information**
- Titre, Page ID, Revision ID
- Statut, Date d'analyse
- Mode, Nombre de caractères
- Nombre de modifications

**Analysis**
- Statut de l'analyse
- Nombre de problèmes détectés
- Résumé de l'analyse

**Corrections**
- Nombre de corrections proposées
- Résumé des modifications (edit summary)

**Diff**
- Contenu corrigé complet
- Diff avant/après (à implémenter avec API diff)

### Actions disponibles:
- **Re-analyze** - Relancer l'analyse
- **Ignore** - Marquer comme ignoré
- **Publish** - Publier sur Wikipedia
- **Retry** - Réessayer après erreur

## Historique

La page d'historique affiche:
- Liste chronologique des articles analysés
- Statut avec icône colorée
- Date d'analyse
- Nombre de modifications
- Revision ID si publié
- Clic sur un article → Page de détail

## Mise à jour en Temps Réel

### Polling automatique:
- Les articles en cours d'analyse (`analyzing`, `pending`) sont interrogés toutes les 3 secondes
- L'interface se met à jour automatiquement sans refresh manuel
- La progression s'affiche en temps réel

### Reprise après refresh:
- L'état de chaque article est restauré depuis le backend
- Les articles en cours d'analyse continuent d'être suivis
- L'historique reste accessible

## Utilisation

### Accéder au workflow:
1. Ouvrir le menu "Analysis"
2. Cliquer sur "Article Workflow"

### Lancer une analyse:
1. Cliquer sur "Start Analysis" sur un article en attente
2. L'article passe en état "Analyzing"
3. La progression s'affiche en temps réel
4. Une fois terminé, l'article passe en "Analyzed"

### Consulter les détails:
1. Cliquer sur "View Details" sur n'importe quel article
2. Naviguer entre les onglets (Info, Analysis, Corrections, Diff)
3. Consulter les résultats complets

### Historique:
1. La section "History" en bas de la page
2. Cliquer sur un article pour voir ses détails
3. Les articles restent consultables même après publication

## API Endpoints

### GET /api/articles/{title}/status
```json
{
  "title": "Article Title",
  "page_id": 12345,
  "revision_id": 67890,
  "status": "analyzing",
  "analysis_date": "2026-08-14T00:00:00",
  "changes_count": 12,
  "summary": "Réparation : lien mort remplacé par son archive valide",
  "corrected_content": "...",
  "character_count": 5000,
  "score": 0.95,
  "decision": "approved",
  "mode": "regex",
  "progress": 67.5,
  "current_step": "Analyse des liens morts...",
  "analyzers_status": {
    "HTTP Links": "completed",
    "Dead Links": "running",
    "Typography": "pending"
  },
  "elapsed_time_seconds": 32.5
}
```

### GET /api/articles/history?limit=50
```json
[
  {
    "title": "Article A",
    "page_id": 12345,
    "revision_id": 67890,
    "status": "published",
    "analysis_date": "2026-08-14T00:00:00",
    "changes_count": 12,
    "summary": "...",
    "published_date": "2026-08-14T01:00:00",
    "published_revision_id": 67890
  }
]
```

### POST /api/articles/{title}/analyze
```json
{
  "title": "Article Title",
  "mode": "regex"
}
```

### POST /api/articles/{title}/ignore
```json
{
  "success": true,
  "message": "Article 'Title' marked as ignored",
  "title": "Title",
  "status": "ignored"
}
```

## Statuts Disponibles

- `pending` - En attente d'analyse
- `analyzing` - Analyse en cours
- `analyzed` - Analyse terminée
- `published` - Publié sur Wikipedia
- `rejected` - Rejeté
- `ignored` - Ignoré (ne sera plus traité)
- `error` - Erreur lors de l'analyse

## Avantages du Workflow Article par Article

1. **Traçabilité complète** - Chaque article a son propre historique
2. **Progression visible** - L'utilisateur voit l'avancement en temps réel
3. **Pas de blocage global** - L'interface reste utilisable pendant les analyses
4. **Reprise après refresh** - L'état est restauré automatiquement
5. **Actions granulaires** - Chaque article peut être traité individuellement
6. **Historique cliquable** - Accès rapide aux détails de n'importe quel article

## Intégration avec le système existant

- Réutilise les trackers Python existants (AnalyzedTracker, PublishedTracker)
- Compatible avec le moteur d'analyse existant
- Intègre le système d'automation state
- Compatible avec la base de données SQLite existante
- Ne modifie pas le comportement fonctionnel de Streamlit

## Prochaines améliorations possibles

1. **Diff structuré** - Intégration avec l'API diff pour afficher les différences avant/après
2. **Logs par article** - Affichage des logs spécifiques à chaque article
3. **Filtres d'historique** - Filtrer par statut, date, nombre de modifications
4. **Actions groupées** - Sélectionner plusieurs articles et appliquer des actions
5. **WebSocket** - Remplacer le polling par des mises à jour en temps réel via WebSocket
6. **Export** - Exporter l'historique en CSV/JSON
