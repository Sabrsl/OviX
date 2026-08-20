-- ============================================================================
-- MIGRATION: pending → awaiting_decision
-- ============================================================================
-- Objectif: Résoudre l'ambiguïté du statut 'pending' dans analysis_results
-- 
-- Avant:
--   analysis_results.status='pending' signifie "analyse terminée, en attente de décision"
--   mais 'pending' est aussi utilisé pour "en attente d'analyse" dans d'autres tables
--
-- Après:
--   analysis_results.status='awaiting_decision' signifie clairement "en attente de décision"
-- ============================================================================

-- ============================================================================
-- ÉTAPE 1: BACKUP
-- ============================================================================
-- Créer une backup table avant la migration
CREATE TABLE IF NOT EXISTS analysis_results_backup_2026_08_17 AS 
SELECT * FROM analysis_results;

-- ============================================================================
-- ÉTAPE 2: MIGRATION DES DONNÉES
-- ============================================================================
-- Mettre à jour le statut 'pending' vers 'awaiting_decision'
UPDATE analysis_results 
SET status = 'awaiting_decision' 
WHERE status = 'pending';

-- Vérifier le nombre de lignes mises à jour
SELECT COUNT(*) as updated_rows 
FROM analysis_results 
WHERE status = 'awaiting_decision';

-- ============================================================================
-- ÉTAPE 3: VÉRIFICATION
-- ============================================================================
-- Vérifier les statuts après migration
SELECT status, COUNT(*) as count 
FROM analysis_results 
GROUP BY status;

-- Vérifier qu'il n'y a plus de 'pending' dans analysis_results
SELECT COUNT(*) as remaining_pending 
FROM analysis_results 
WHERE status = 'pending';

-- ============================================================================
-- ÉTAPE 4: ROLLBACK (EN CAS DE PROBLÈME)
-- ============================================================================
-- Si quelque chose ne va pas, restaurer depuis le backup:
-- DROP TABLE analysis_results;
-- CREATE TABLE analysis_results AS SELECT * FROM analysis_results_backup_2026_08_17;

-- ============================================================================
-- ÉTAPE 5: NETTOYAGE (APRES VALIDATION)
-- ============================================================================
-- Une fois la migration validée, supprimer le backup:
-- DROP TABLE analysis_results_backup_2026_08_17;
