"""Données et dictionnaires pour l'analyseur typographique."""

from typing import List, Dict

# ---------------------------------------------------------------------------
# Whitelist d'acronymes (à ne pas corriger)
# ---------------------------------------------------------------------------

ACRONYM_WHITELIST = {
    "NASA", "FBI", "CIA", "KGB", "OTAN", "UE", "ONU", "UNESCO", "OMS", "OMC",
    "FMI", "BCE", "BERD", "AIEA", "OIT", "FAO", "FIDA", "PNUD", "UNICEF",
    "HCR", "PAM", "OMM", "OACI", "OMI", "UIT", "UPU", "UNWTO",
    "SNCF", "RATP", "EDF", "GDF", "CAF", "Pôle emploi", "ANPE",
    "INSEE", "CNRS", "INSERM", "CEA", "CNES", "IRD", "CIRAD", "BRGM",
    "INRA", "INRIA", "IFREMER", "IRSTEA", "ANSES", "ANDRA",
    "OVNI", "SIDA", "ADN", "ARN", "PIB", "TVA", "RTT", "SMIC",
    "CDI", "CDD", "PME", "PMI", "ETI", "RATP", "TGV", "RER",
}

# ---------------------------------------------------------------------------
# Mois en français
# ---------------------------------------------------------------------------

FRENCH_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

# ---------------------------------------------------------------------------
# Abréviations de fin de phrase (à ne pas considérer comme erreurs)
# ---------------------------------------------------------------------------

SENTENCE_ABBREVIATIONS = {
    "M", "Mme", "Mlle", "Dr", "Pr", "Prof", "Me", "Maître",
    "S", "St", "Ste", "MM", "Mmes", "Mlles", "Drs", "Prs",
    "V", "Ve", "Vve", "Mgr", "Fr", "Sœur", "Sr",
    "Cie", "Sté", "SARL", "EURL", "SA", "SAS", "SASU",
    "Gouv", "Min", "Dépt", "Rég", "Comm", "Cant",
    "av", "ap", "av JC", "ap JC", "av J-C", "ap J-C",
}

# ---------------------------------------------------------------------------
# Règles lexicales (corrections de mots)
# ---------------------------------------------------------------------------

WORD_RULES: Dict[str, str] = {
    "etait": "était",
}