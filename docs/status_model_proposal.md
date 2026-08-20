# PROPOSITION DE MODÈLE DE STATUTS OviX

## A. MODÈLE ACTUEL

### Table: articles_to_analyze
| Colonne | Valeurs | Signification | Utilisateurs |
|---------|---------|---------------|--------------|
| status | pending | Article en attente d'analyse | Queue, Automation |
| status | analyzing | Article en cours d'analyse | Queue, Automation |
| status | analyzed | Article analysé | Queue, Automation |
| status | error | Erreur lors de l'analyse | Queue, Automation |
| status | cancelled | Analyse annulée | Queue, Automation |

### Table: analysis_jobs
| Colonne | Valeurs | Signification | Utilisateurs |
|---------|---------|---------------|--------------|
| status | pending | Job en attente d'exécution | Analysis, Orchestrator |
| status | running | Job en cours d'exécution | Analysis, Orchestrator |
| status | completed | Job terminé avec succès | Analysis, Orchestrator |
| status | failed | Job échoué | Analysis, Orchestrator |
| status | cancelled | Job annulé | Analysis, Orchestrator |

### Table: analysis_results
| Colonne | Valeurs | Signification | Utilisateurs |
|---------|---------|---------------|--------------|
| status | pending | **AMBIGU** - Analyse terminée, en attente de décision utilisateur | History, Workflow, Manual Review |
| status | published | Article publié sur Wikipedia | History, Publication |
| status | rejected | Article rejeté | History, Workflow |
| status | ignored | Article ignoré | History, Workflow |
| status | error | Erreur lors de l'analyse | History, Workflow |

### Table: manual_review_decisions
| Colonne | Valeurs | Signification | Utilisateurs |
|---------|---------|---------------|--------------|
| status | pending | Review en attente | Manual Review |
| status | approved | URL approuvée | Manual Review |
| status | rejected | URL rejetée | Manual Review |

### Table: publication_jobs
| Colonne | Valeurs | Signification | Utilisateurs |
|---------|---------|---------------|--------------|
| status | pending | Publication en attente | Publication |
| status | running | Publication en cours | Publication |
| status | completed | Publication terminée | Publication |
| status | failed | Publication échouée | Publication |

## B. ANALYSE DE L'ARCHITECTURE ACTUELLE

### ✅ Ce qui fonctionne déjà correctement:

1. **Queue** → `articles_to_analyze.status` représente clairement l'état dans la queue
2. **Job execution** → `analysis_jobs.status` représente clairement l'état d'exécution
3. **Manual review** → `manual_review_decisions.status` représente clairement l'état de review
4. **Publication** → `publication_jobs.status` représente clairement l'état de publication

### ⚠️ Problème identifié:

**`analysis_results.status='pending'` est ambiguë**
- Signifie actuellement: "Analyse terminée, en attente de décision utilisateur"
- Mais le mot "pending" est aussi utilisé pour "en attente d'analyse" dans d'autres tables
- Crée une confusion dans le modèle métier

## C. MODÈLE PROPOSÉ

### Option 1: Utiliser l'architecture existante (RECOMMANDÉ - FAIBLE RISQUE)

L'architecture actuelle sépare déjà correctement les états par table:

```text
articles_to_analyze.status
→ État dans la queue (pending, analyzing, analyzed)

analysis_jobs.status  
→ État d'exécution du job (pending, running, completed, failed)

analysis_results.status
→ État du résultat de l'analyse (pending, published, rejected, ignored, error)

manual_review_decisions.status
→ État de la review (pending, approved, rejected)

publication_jobs.status
→ État de publication (pending, running, completed, failed)
```

**Solution**: Renommer uniquement `analysis_results.status='pending'` → `'awaiting_decision'`

### Option 2: Ajouter des colonnes séparées (PLUS ROBUSTE - RISQUE MOYEN)

Ajouter des colonnes explicites dans `analysis_results`:

```sql
ALTER TABLE analysis_results ADD COLUMN analysis_status TEXT;
ALTER TABLE analysis_results ADD COLUMN review_status TEXT;
ALTER TABLE analysis_results ADD COLUMN publication_status TEXT;
```

**Mapping**:
- `analysis_status`: 'completed' (toujours true si ligne existe)
- `review_status`: 'not_required', 'pending', 'approved', 'rejected', 'ignored'
- `publication_status`: 'not_published', 'published'

### Option 3: Utiliser une table de workflow séparée (PLUS PROPRE - RISQUE ÉLEVÉ)

Créer une nouvelle table `article_workflow`:

```sql
CREATE TABLE article_workflow (
    article_title TEXT PRIMARY KEY,
    analysis_status TEXT,  -- pending, analyzing, completed, failed
    review_status TEXT,     -- not_required, pending, approved, rejected, ignored
    publication_status TEXT, -- not_published, pending, publishing, published, failed
    updated_at TIMESTAMP
);
```

## D. RECOMMANDATION

### 🟢 OPTION 1 RECOMMANDÉE (FAIBLE RISQUE)

**Pourquoi**:
- L'architecture actuelle sépare déjà correctement les états par table
- Un seul changement: renommer `analysis_results.status='pending'` → `'awaiting_decision'`
- Aucune migration de données complexe
- Aucun changement de schéma
- Compatible avec tout le code existant

**Migration**:
```sql
UPDATE analysis_results SET status = 'awaiting_decision' WHERE status = 'pending';
```

**Impact frontend**:
- Mettre à jour les libellés UI:
  - "Pending" → "En attente de décision"
  - Garder les autres statuts inchangés
- Mettre à jour les filtres si nécessaire

**Impact backend**:
- Mettre à jour les endpoints pour accepter `'awaiting_decision'`
- Mettre à jour les filtres SQL
- Mettre à jour Statistics

### 🟡 OPTION 2 ALTERNATIVE (SI OPTION 1 INSUFFISANTE)

**Pourquoi**:
- Plus explicite et robuste
- Sépare clairement les trois domaines
- Plus évolutif pour l'avenir

**Migration**:
```sql
-- Ajouter les colonnes
ALTER TABLE analysis_results ADD COLUMN analysis_status TEXT DEFAULT 'completed';
ALTER TABLE analysis_results ADD COLUMN review_status TEXT;
ALTER TABLE analysis_results ADD COLUMN publication_status TEXT;

-- Migrer les données existantes
UPDATE analysis_results SET 
    analysis_status = 'completed',
    review_status = CASE 
        WHEN status = 'pending' THEN 'pending'
        WHEN status = 'rejected' THEN 'rejected'
        WHEN status = 'ignored' THEN 'ignored'
        WHEN status = 'published' THEN 'approved'
        WHEN status = 'error' THEN 'error'
        ELSE 'not_required'
    END,
    publication_status = CASE 
        WHEN status = 'published' THEN 'published'
        ELSE 'not_published'
    END;

-- Garder l'ancienne colonne pour compatibilité (optionnel)
-- ALTER TABLE analysis_results RENAME COLUMN status TO status_legacy;
```

## E. MODÈLE CIBLE FINAL (OPTION 1)

### Table: analysis_results (après migration)
| Colonne | Valeurs | Signification |
|---------|---------|---------------|
| status | awaiting_decision | Analyse terminée, en attente de décision utilisateur |
| status | published | Article publié sur Wikipedia |
| status | rejected | Article rejeté |
| status | ignored | Article ignoré |
| status | error | Erreur lors de l'analyse |

### Libellés UI correspondants
| Backend status | Libellé UI |
|----------------|------------|
| awaiting_decision | "En attente de décision" |
| published | "Publié" |
| rejected | "Rejeté" |
| ignored | "Ignoré" |
| error | "Erreur" |

## F. VALIDATION

### Avantages de l'Option 1:
- ✅ Résout l'ambiguïté principale
- ✅ Faible risque de régression
- ✅ Migration simple (un UPDATE)
- ✅ Compatible avec l'architecture existante
- ✅ Pas besoin de modifier le schéma

### Inconvénients:
- ⚠️ Ne sépare pas explicitement analysis/review/publication dans la même table
- ⚠️ Dépend de la séparation par table pour la clarté sémantique

### Avantages de l'Option 2:
- ✅ Sépare explicitement les trois domaines
- ✅ Plus robuste et évolutif
- ✅ Plus clair sémantiquement

### Inconvénients:
- ⚠️ Migration plus complexe
- ⚠️ Plus de changements dans le code
- ⚠️ Risque plus élevé de régression

## G. PROCHAINE ÉTAPE

Recommandation: **Commencer par l'Option 1**

Si l'Option 1 résout suffisamment l'ambiguïté, s'arrêter là.
Si une séparation plus explicite est nécessaire, passer à l'Option 2.
