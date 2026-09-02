# Exemples d'application de corrections

Ce document montre ce qui se passe lors de l'application d'une correction de lien mort avec archive.

## Scénario 1: Template {{Lien web}} avec archive (mode par défaut)

### Wikicode avant correction
```wikicode
{{Lien web
 |titre=Article sur l'histoire
 |url=https://example-dead.com/article
 |site=example-dead.com
 |date=2020-05-15
}}
```

### Étapes du processus
1. **Détection**: Le lien `https://example-dead.com/article` est détecté comme mort (HTTP 404)
2. **Recherche d'archive**: Archive trouvée sur Internet Archive
3. **Validation**: Archive vérifiée et content match confirmé
4. **Génération de template**: Le `LienWebHelper` génère le wikicode corrigé
5. **Application**: Le template est remplacé dans l'article

### Wikicode après correction (mode par défaut, assume_wikipedia_patch_deployed=false)
```wikicode
{{Lien web
 |titre=Article sur l'histoire
 |url=https://example-dead.com/article
 |site=example-dead.com
 |date=2020-05-15
 |archive-url=https://web.archive.org/web/20230515120000/https://example-dead.com/article
 |archive-date=2023-05-15
 |brisé le=2024-08-23
}}
```

### Logs générés
```
ARCHIVE_FALLBACK | url=https://example-dead.com/article | reason=no_valid_redirect
ARCHIVE_VERIFICATION | url=https://example-dead.com/article | candidate=https://web.archive.org/web/20230515120000/https://example-dead.com/article
ARCHIVE_VERIFICATION | url=https://example-dead.com/article | original_archive=True | candidate_archive=True | original_title=Article sur l'histoire | candidate_title=Article sur l'histoire
REPAIR_DECISION | url=https://example-dead.com/article | decision=REPLACEMENT_CONFIRMED | reason=Archive fallback: using Internet Archive archive from 2023-05-15 (HTTP 200)
LIEN_WEB_TEMPLATE_REPAIR | url=https://example-dead.com/article | using_archive_template_format
GENERATED_ARCHIVE_TEMPLATE | original_url=https://example-dead.com/article | archive_url=https://web.archive.org/web/20230515120000/https://example-dead.com/article | archive_date=2023-05-15 | assume_patch_deployed=False | main_url=https://example-dead.com/article
LIEN_WEB_TEMPLATE_REPAIR_APPLIED | url=https://example-dead.com/article | archive_url=https://web.archive.org/web/20230515120000/https://example-dead.com/article
```

### Affichage sur Wikipedia (sans patch)
```
Article sur l'histoire, sur example-dead.com, 15 mai 2020 [archive du 15 mai 2023]
```

---

## Scénario 2: Template {{Lien web}} avec archive (mode patché)

### Wikicode avant correction
```wikicode
{{Lien web
 |titre=Article sur l'histoire
 |url=https://example-dead.com/article
 |site=example-dead.com
 |date=2020-05-15
}}
```

### Wikicode après correction (mode patché, assume_wikipedia_patch_deployed=true)
```wikicode
{{Lien web
 |titre=Article sur l'histoire
 |url=https://web.archive.org/web/20230515120000/https://example-dead.com/article
 |site=example-dead.com
 |date=2020-05-15
 |archive-url=https://web.archive.org/web/20230515120000/https://example-dead.com/article
 |archive-date=2023-05-15
 |brisé le=2024-08-23
}}
```

### Logs générés
```
ARCHIVE_FALLBACK | url=https://example-dead.com/article | reason=no_valid_redirect
ARCHIVE_VERIFICATION | url=https://example-dead.com/article | candidate=https://web.archive.org/web/20230515120000/https://example-dead.com/article
ARCHIVE_VERIFICATION | url=https://example-dead.com/article | original_archive=True | candidate_archive=True | original_title=Article sur l'histoire | candidate_title=Article sur l'histoire
REPAIR_DECISION | url=https://example-dead.com/article | decision=REPLACEMENT_CONFIRMED | reason=Archive fallback: using Internet Archive archive from 2023-05-15 (HTTP 200)
LIEN_WEB_TEMPLATE_REPAIR | url=https://example-dead.com/article | using_archive_template_format
GENERATED_ARCHIVE_TEMPLATE | original_url=https://example-dead.com/article | archive_url=https://web.archive.org/web/20230515120000/https://example-dead.com/article | archive_date=2023-05-15 | assume_patch_deployed=True | main_url=https://web.archive.org/web/20230515120000/https://example-dead.com/article
LIEN_WEB_TEMPLATE_REPAIR_APPLIED | url=https://example-dead.com/article | archive_url=https://web.archive.org/web/20230515120000/https://example-dead.com/article
```

### Affichage sur Wikipedia (avec patch)
```
Article sur l'histoire [archive du 15 mai 2023], sur example-dead.com via Internet Archive, 15 mai 2020
```

---

## Scénario 3: Template avec date 'brisé le' existante

### Wikicode avant correction
```wikicode
{{Lien web
 |titre=Rapport technique
 |url=https://old-site.com/report.pdf
 |brisé le=2023-06-15
}}
```

### Wikicode après correction
```wikicode
{{Lien web
 |titre=Rapport technique
 |url=https://old-site.com/report.pdf
 |site=old-site.com
 |brisé le=2023-06-15
 |archive-url=https://web.archive.org/web/20240101000000/https://old-site.com/report.pdf
 |archive-date=2024-01-01
}}
```

**Note**: La date `brisé le=2023-06-15` est **conservée** et non écrasée par la date de correction.

### Logs générés
```
GENERATED_ARCHIVE_TEMPLATE | original_url=https://old-site.com/report.pdf | archive_url=https://web.archive.org/web/20240101000000/https://old-site.com/report.pdf | archive_date=2024-01-01 | assume_patch_deployed=False | main_url=https://old-site.com/report.pdf
```

---

## Scénario 4: URL simple (hors template)

### Wikicode avant correction
```wikicode
Voir https://dead-link.com/page pour plus d'informations.
```

### Wikicode après correction
```wikicode
Voir https://web.archive.org/web/20240101000000/https://dead-link.com/page pour plus d'informations.
```

### Logs générés
```
ARCHIVE_FALLBACK | url=https://dead-link.com/page | reason=no_valid_redirect
REPAIR_DECISION | url=https://dead-link.com/page | decision=REPLACEMENT_CONFIRMED | reason=Archive fallback: using Internet Archive archive from 2024-01-01 (HTTP 200)
SIMPLE_URL_REPLACEMENT_APPLIED | url=https://dead-link.com/page | archive_url=https://web.archive.org/web/20240101000000/https://dead-link.com/page
```

---

## Scénario 5: Template avec tous les paramètres

### Wikicode avant correction
```wikicode
{{Lien web
 |langue=en
 |auteur=John Smith
 |titre=Climate Change Report
 |url=https://research.edu/climate-study
 |site=research.edu
 |éditeur=University Press
 |date=2021-03-10
 |isbn=978-0-123456-78-9
 |consulté le=2022-05-20
}}
```

### Wikicode après correction
```wikicode
{{Lien web
 |langue=en
 |auteur=John Smith
 |titre=Climate Change Report
 |url=https://research.edu/climate-study
 |site=research.edu
 |éditeur=University Press
 |date=2021-03-10
 |isbn=978-0-123456-78-9
 |consulté le=2022-05-20
 |archive-url=https://web.archive.org/web/20220310080000/https://research.edu/climate-study
 |archive-date=2022-03-10
 |brisé le=2024-08-23
}}
```

**Note**: Tous les paramètres originaux sont conservés dans l'ordre préféré.

---

## Scénario 6: Archive non disponible (rejet)

### Wikicode avant correction
```wikicode
{{Lien web
 |titre=Article
 |url=https://dead-link.com/article
}}
```

### Wikicode après correction
```wikicode
{{Lien web
 |titre=Article
 |url=https://dead-link.com/article
}}
```

**Résultat**: Aucune modification - l'archive n'a pas été trouvée ou validée.

### Logs générés
```
ARCHIVE_FALLBACK | url=https://dead-link.com/article | reason=no_valid_redirect
ARCHIVE_VERIFICATION | url=https://dead-link.com/article | candidate=None
REPAIR_REJECTED | url=https://dead-link.com/article | reason=No valid archive found
```

---

## Résumé du flux de correction

1. **Détection du lien mort** (HTTP 404/timeout)
2. **Tentative de redirect** → échec
3. **Fallback vers archive**:
   - Recherche d'archive sur Wayback/Wikiwix
   - Vérification de l'accessibilité (HTTP 200)
   - Content match avec l'original
   - Rejet si archive ressemble à une page 404
4. **Génération du wikicode**:
   - Détection si c'est un template {{Lien web}}
   - Préservation de tous les paramètres
   - Ajout de `archive-url`, `archive-date`, `brisé le`
   - Conservation de la date `brisé le` si existante
5. **Validation du diff minimal**
6. **Application de la correction**
7. **Logging détaillé** pour traçabilité
