# IMPACT FRONTEND: pending → awaiting_decision

## FICHIERS À MODIFIER

### 1. frontend/src/api/types.ts
**Ligne 116**: ArticleHistoryItem.status
```typescript
status: 'pending' | 'analyzing' | 'analyzed' | 'published' | 'rejected' | 'ignored' | 'error'
```
**Modification**: Ajouter 'awaiting_decision'
```typescript
status: 'pending' | 'awaiting_decision' | 'analyzing' | 'analyzed' | 'published' | 'rejected' | 'ignored' | 'error'
```

### 2. frontend/src/components/ArticleHistory.tsx
**Ligne 52**: validStatuses
```typescript
const validStatuses = ['published', 'pending', 'rejected', 'ignored', 'error', 'analyzing', 'analyzed']
```
**Modification**: Ajouter 'awaiting_decision'
```typescript
const validStatuses = ['published', 'awaiting_decision', 'rejected', 'ignored', 'error', 'analyzing', 'analyzed']
```

**Ligne 57**: Default fallback
```typescript
return 'pending'
```
**Modification**: Garder 'pending' pour compatibilité avec d'autres contextes (queue, jobs)

**Ligne 73-74**: getStatusIcon
```typescript
case 'pending':
  return '○'
```
**Modification**: Ajouter cas pour 'awaiting_decision'
```typescript
case 'awaiting_decision':
  return '○'
case 'pending':
  return '○'  // Garder pour articles_to_analyze
```

**Ligne 94-95**: getStatusColor
```typescript
case 'pending':
  return '#f59e0b'
```
**Modification**: Ajouter cas pour 'awaiting_decision'
```typescript
case 'awaiting_decision':
  return '#f59e0b'
case 'pending':
  return '#6b7280'  // Couleur différente pour queue
```

**Ligne 115-116**: getStatusText
```typescript
case 'pending':
  return 'En attente'
```
**Modification**: Ajouter cas pour 'awaiting_decision'
```typescript
case 'awaiting_decision':
  return 'En attente de décision'
case 'pending':
  return 'En attente d\'analyse'  // Pour articles_to_analyze
```

### 3. frontend/src/components/ArticleStatusCard.tsx
**Ligne 33**: Polling condition
```typescript
if (status?.status === 'analyzing' || status?.status === 'pending') {
```
**Modification**: Ajouter 'awaiting_decision' au polling (si nécessaire)
```typescript
if (status?.status === 'analyzing' || status?.status === 'pending' || status?.status === 'awaiting_decision') {
```

**Ligne 69-70**: getStatusIcon
```typescript
case 'pending':
  return '○'
```
**Modification**: Ajouter cas pour 'awaiting_decision'
```typescript
case 'awaiting_decision':
  return '○'
case 'pending':
  return '○'
```

**Ligne 90-91**: getStatusColor
```typescript
case 'pending':
  return '#f59e0b'
```
**Modification**: Ajouter cas pour 'awaiting_decision'
```typescript
case 'awaiting_decision':
  return '#f59e0b'
case 'pending':
  return '#f59e0b'
```

**Ligne 111-112**: getStatusText
```typescript
case 'pending':
  return 'Pending'
```
**Modification**: Ajouter cas pour 'awaiting_decision'
```typescript
case 'awaiting_decision':
  return 'Awaiting Decision'
case 'pending':
  return 'Pending'
```

**Ligne 144, 157, 165**: Default fallback
```typescript
status?.status || 'pending'
```
**Modification**: Garder 'pending' pour compatibilité

**Ligne 359**: Bouton reanalyze
```typescript
{status?.status === 'pending' && (
```
**Modification**: Ajouter 'awaiting_decision'
```typescript
{(status?.status === 'pending' || status?.status === 'awaiting_decision') && (
```

### 4. frontend/src/pages/AnalyzedHistory.tsx
**Ligne 52**: STATUS_META (si présent)
```typescript
pending: { label: 'En attente', color: '#f59e0b' }
```
**Modification**: Ajouter 'awaiting_decision'
```typescript
awaiting_decision: { label: 'En attente de décision', color: '#f59e0b' }
pending: { label: 'En attente', color: '#6b7280' }  // Pour queue
```

### 5. frontend/src/api/stats.api.ts
**Ligne 12**: ArticleStats.pending
**Ligne 21**: AnalysisStats.pending
**Ligne 41**: PublicationStats.pending
**Ligne 61**: QueueStats.pending

**Note**: Ces champs représentent des compteurs, pas des statuts d'articles individuels. Ils ne doivent PAS être modifiés car:
- ArticleStats.pending compte les articles avec status='pending' (qui deviendra 'awaiting_decision')
- AnalysisStats.pending compte les jobs avec status='pending' (inchangé)
- PublicationStats.pending compte les publications avec status='pending' (inchangé)
- QueueStats.pending compte les articles avec status='pending' (inchangé)

**Action**: Mettre à jour la logique de comptage dans le backend pour ArticleStats.pending

### 6. backend/api/routes/articles.py
**Ligne 452**: Création de analysis_results
```python
status="pending",  # Awaiting decision (publish/ignore/reject)
```
**Modification**: Changer en
```python
status="awaiting_decision",  # Awaiting decision (publish/ignore/reject)
```

### 7. backend/api/routes/history.py
**Ligne 174**: Filtre published
```python
WHERE status = 'published'
```
**Pas de modification**: Filtre spécifique, pas impacté

**Ligne 260**: Filtre analyzed
```python
WHERE status = 'pending'
```
**Modification**: Changer en
```python
WHERE status = 'awaiting_decision'
```

### 8. backend/stats/repository.py
**Ligne 43**: Compteur pending
```python
COUNT(analysis_results WHERE status='pending')
```
**Modification**: Changer en
```python
COUNT(analysis_results WHERE status='awaiting_decision')
```

## ORDRE DES MODIFICATIONS

1. **Backend d'abord**:
   - Modifier backend/api/routes/articles.py (création analysis_results)
   - Modifier backend/api/routes/history.py (filtre analyzed)
   - Modifier backend/stats/repository.py (compteur)
   - Exécuter la migration SQL

2. **Frontend ensuite**:
   - Modifier frontend/src/api/types.ts
   - Modifier frontend/src/components/ArticleHistory.tsx
   - Modifier frontend/src/components/ArticleStatusCard.tsx
   - Modifier frontend/src/pages/AnalyzedHistory.tsx

3. **Tests**:
   - Vérifier que les articles avec 'awaiting_decision' s'affichent correctement
   - Vérifier que les compteurs de stats sont corrects
   - Vérifier que les filtres fonctionnent

## COMPATIBILITÉ ARRIÈRE

- Garder 'pending' dans les types pour articles_to_analyze, analysis_jobs, etc.
- Ajouter 'awaiting_decision' comme nouveau statut spécifique à analysis_results
- Les anciennes données seront migrées automatiquement par le SQL
