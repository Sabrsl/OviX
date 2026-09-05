/**
 * AnalyzerBadges - Affiche les paramètres de configuration utilisés pour l'analyse
 * Design élégant et subtil pour la page de détail d'article
 */

interface AnalyzerBadgesProps {
  analysisConfig?: Record<string, any>
  className?: string
  typoCorrectionsCount?: number
}

export function AnalyzerBadges({ analysisConfig, className = '', typoCorrectionsCount }: AnalyzerBadgesProps) {
  if (!analysisConfig || Object.keys(analysisConfig).length === 0) {
    return null
  }

  const getConfigLabel = (key: string): string => {
    // Mapping des clés de configuration vers des labels français
    const labels: Record<string, string> = {
      'enable_dead_link_analyzer': 'Liens morts',
      'enable_case_normalization': 'Normalisation',
      'normalize_with_ai': 'Normalisation IA',
      'reference_enricher_analyzer': 'Enrichissement',
      'https_verification': 'HTTPS',
      'check_bare_refs': 'Références nues',
      'check_duplicate_refs': 'Références dupliquées',
      'check_uppercase_refs': 'Majuscules',
      'check_isbn_format': 'ISBN',
      'check_template_type': 'Type template',
      'check_broken_links': 'Liens brisés',
      'use_wayback_api': 'Wayback API',
      'same_domain_only': 'Même domaine',
      'require_archive_evidence': 'Preuve archive',
      'max_checks': 'Max vérifications',
      'max_candidates': 'Max candidats',
      'typo_corrections': 'Typo XML',
    }
    return labels[key] || key
  }

  const isAnalyzerKey = (key: string): boolean => {
    // Ne montrer que les analyseurs activés (ceux qui commencent par "enable_" ou sont des analyseurs principaux)
    const analyzerKeys = [
      'enable_dead_link_analyzer',
      'enable_case_normalization',
      'normalize_with_ai',
      'reference_enricher_analyzer',
      'https_verification',
      'check_bare_refs',
      'check_duplicate_refs',
      'check_uppercase_refs',
      'check_isbn_format',
      'check_template_type',
      'check_broken_links',
      'use_wayback_api',
    ]
    return analyzerKeys.includes(key)
  }

  const getConfigColor = (key: string, value: any): string => {
    // Couleur basée sur le type de configuration
    if (key.includes('enrich') || key.includes('reference')) {
      return 'bg-purple-500/10 text-purple-500 border-purple-500/20'
    }
    if (key.includes('https') || key.includes('http')) {
      return 'bg-blue-500/10 text-blue-500 border-blue-500/20'
    }
    if (key.includes('normalization') || key.includes('normalize')) {
      return 'bg-amber-500/10 text-amber-500 border-amber-500/20'
    }
    if (key.includes('dead') || key.includes('link')) {
      return 'bg-red-500/10 text-red-500 border-red-500/20'
    }
    return 'bg-neutral-500/10 text-neutral-400 border-neutral-500/20'
  }

  const getConfigDot = (key: string, value: any): string => {
    if (value === true || value === 'true') {
      return 'bg-emerald-500'
    }
    if (value === false || value === 'false') {
      return 'bg-neutral-500'
    }
    return 'bg-blue-500'
  }

  const formatValue = (value: any): string => {
    if (typeof value === 'boolean') {
      return value ? 'Activé' : 'Désactivé'
    }
    if (typeof value === 'number') {
      return value.toString()
    }
    return String(value)
  }

  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`}>
      {/* Afficher les corrections typo si présentes */}
      {typoCorrectionsCount !== undefined && typoCorrectionsCount !== null && typoCorrectionsCount > 0 && (
        <div
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-medium transition-colors bg-green-500/10 text-green-500 border-green-500/20"
          title={`Corrections typo (XML): ${typoCorrectionsCount}`}
        >
          <span className="h-1 w-1 rounded-full bg-emerald-500" />
          <span>Typo XML</span>
        </div>
      )}
      
      {Object.entries(analysisConfig).map(([key, value]) => {
        // N'afficher que les analyseurs activés pertinentes pour l'analyse
        if (!isAnalyzerKey(key)) {
          return null
        }
        
        // Gérer les valeurs booléennes et les chaînes "True"/"False" du backend
        const isDisabled = value === false || value === 'false' || value === null || value === undefined
        if (isDisabled) {
          return null
        }
        
        return (
          <div
            key={key}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-medium transition-colors ${getConfigColor(key, value)}`}
            title={`${getConfigLabel(key)}: ${formatValue(value)}`}
          >
            <span className={`h-1 w-1 rounded-full ${getConfigDot(key, value)}`} />
            <span>{getConfigLabel(key)}</span>
          </div>
        )
      })}
    </div>
  )
}
