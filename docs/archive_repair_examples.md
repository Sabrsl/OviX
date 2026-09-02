# Exemples de corrections avec archive

Ce document montre des exemples de corrections de liens morts utilisant des archives, avec le comportement du modèle {{Lien web}}.

## Modèles supportés

Le bot supporte les modèles de référence suivants:

- **{{Lien web}}** - Pour les liens web
- **{{article}}** - Pour les articles de périodiques
- **{{ouvrage}}** - Pour les ouvrages et livres
- **{{Lien brisé}}** - Pour les liens brisés

Tous les paramètres de chaque modèle sont supportés et conservés lors des réparations.

## Mode d'opération

Le bot supporte deux modes d'opération pour la réparation d'archive:

### Mode par défaut (assume_wikipedia_patch_deployed: false)

Ce mode est compatible avec les wikis où le patch Lua n'est pas déployé.

**Comportement:**
- L'URL originale reste le lien principal dans le template
- L'archive est disponible via le paramètre `archive-url`
- Le paramètre `brisé le` indique quand le lien est mort
- Le paramètre `archive-date` indique quand l'archive a été créée

### Mode patché (assume_wikipedia_patch_deployed: true)

Ce mode est utilisé quand le patch Lua est déployé sur le wiki.

**Comportement:**
- L'archive devient le lien principal dans le template (pour {{Lien web}} et {{Lien brisé}} uniquement)
- Le paramètre `url` contient l'URL de l'archive
- Le patch Lua détecte automatiquement le service d'archivage depuis l'URL

## Configuration

Pour changer le mode, modifiez `config/config.yaml`:

```yaml
dead_links_analyzer:
  assume_wikipedia_patch_deployed: false  # true si le patch est déployé
```

## Exemples de réparation

### Exemple 1: Template {{Lien web}}

**Avant:**
```wikicode
{{Lien web |titre=Article |url=https://dead-link.com |site=dead-link.com }}
```

**Après (mode par défaut):**
```wikicode
{{Lien web
 |titre=Article
 |url=https://dead-link.com
 |site=dead-link.com
 |archive-url=https://web.archive.org/web/20240101000000/https://dead-link.com
 |archive-date=2024-01-01
 |brisé le=2024-08-23
}}
```

### Exemple 2: Template {{article}}

**Avant:**
```wikicode
{{article|auteur=Park|titre=Test Article|url=http://www.osen.co.kr/article/G1111748424|périodique=OSEN|date=2022}}
```

**Après:**
```wikicode
{{article
 |auteur=Park
 |titre=Test Article
 |url=http://www.osen.co.kr/article/G1111748424
 |périodique=OSEN
 |date=2022
 |archive-url=https://web.archive.org/web/20231016105943/http://www.osen.co.kr/article/G1111748424
 |archive-date=2023-10-16
 |brisé le=2024-08-23
}}
```

### Exemple 3: Template {{ouvrage}}

**Avant:**
```wikicode
{{ouvrage|auteur=John Doe|titre=Test Book|éditeur=Publisher|lieu=Paris|date=2020|url=http://example.com}}
```

**Après:**
```wikicode
{{ouvrage
 |auteur=John Doe
 |titre=Test Book
 |éditeur=Publisher
 |lieu=Paris
 |date=2020
 |url=http://example.com
 |archive-url=https://web.archive.org/web/20240101000000/http://example.com
 |archive-date=2024-01-01
 |brisé le=2024-08-23
}}
```

### Exemple 4: Template {{Lien brisé}}

**Avant:**
```wikicode
{{Lien brisé |titre=Test |url=https://example.com |date=2023}}
```

**Après:**
```wikicode
{{Lien brisé
 |titre=Test
 |url=https://example.com
 |date=2023
 |archive-url=https://web.archive.org/web/20240101000000/https://example.com
 |archive-date=2024-01-01
 |brisé le=2024-08-23
}}
```

### Exemple 5: Template avec caractères spéciaux (coréen)

**Avant:**
```wikicode
{{article|langue=ko|auteur=Park|prénom=Moon Jae|titre='분강나루'서 건져낸 백정 恨|url=http://www.sisapress.com/journal/articlePrint/108966|série=sisapress.com|date=8 août 1991}}
```

**Après:**
```wikicode
{{article
 |langue=ko
 |auteur=Park
 |prénom=Moon Jae
 |titre='분강나루'서 건져낸 백정 恨
 |url=http://www.sisapress.com/journal/articlePrint/108966
 |série=sisapress.com
 |date=8 août 1991
 |archive-url=https://web.archive.org/web/20240101000000/http://www.sisapress.com/journal/articlePrint/108966
 |archive-date=2024-01-01
 |brisé le=2024-08-23
}}
```

### Exemple 6: URL simple (hors template)

**Avant:**
```wikicode
Voir https://dead-link.com/page pour plus d'informations.
```

**Après (remplacement simple):**
```wikicode
Voir https://web.archive.org/web/20240101000000/https://dead-link.com/page pour plus d'informations.
```

**Comportement**: Pour les URLs simples (hors template de référence), seul l'URL est remplacée par l'archive.

---

## Préservation des paramètres

### Date 'brisé le' existante

Si le template contient déjà une date `brisé le`, elle est conservée:

**Avant:**
```wikicode
{{Lien web |titre=Article |url=https://dead-link.com |brisé le=2023-06-15 }}
```

**Après:**
```wikicode
{{Lien web
 |titre=Article
 |url=https://dead-link.com
 |site=dead-link.com
 |brisé le=2023-06-15  # Date conservée
 |archive-url=https://web.archive.org/web/20240101000000/https://dead-link.com
 |archive-date=2024-01-01
}}
```

### Tous les paramètres conservés

Tous les paramètres originaux sont conservés dans l'ordre préféré du modèle. Aucun paramètre n'est perdu lors de la réparation.

---

## Résumé du comportement

### Cas {{Lien web}} (avec archive validée)
- ✅ `url` devient l'URL d'archive (si patch déployé) ou reste l'URL originale (mode par défaut)
- ✅ `archive-url` contient l'URL d'archive
- ✅ `archive-date` contient la date de l'archive
- ✅ `brisé le` contient la date de correction (ou date existante conservée)
- ✅ `site` est conservé ou extrait de l'URL originale
- ✅ Tous les autres paramètres sont conservés

### Cas {{article}} (avec archive validée)
- ✅ `url` reste l'URL originale (archive comme lien secondaire)
- ✅ `archive-url` contient l'URL d'archive
- ✅ `archive-date` contient la date de l'archive
- ✅ `brisé le` contient la date de correction
- ✅ Tous les autres paramètres sont conservés

### Cas {{ouvrage}} (avec archive validée)
- ✅ `url` reste l'URL originale (archive comme lien secondaire)
- ✅ `archive-url` contient l'URL d'archive
- ✅ `archive-date` contient la date de l'archive
- ✅ `brisé le` contient la date de correction
- ✅ Tous les autres paramètres sont conservés

### Cas {{Lien brisé}} (avec archive validée)
- ✅ `url` devient l'URL d'archive (si patch déployé) ou reste l'URL originale (mode par défaut)
- ✅ `archive-url` contient l'URL d'archive
- ✅ `archive-date` contient la date de l'archive
- ✅ `brisé le` contient la date de correction
- ✅ Tous les autres paramètres sont conservés

### Cas URL simple (hors template)
- ✅ L'URL est remplacée par l'URL d'archive
- ✅ Pas de modification du texte environnant

### Règles de sécurité
- ✅ Lien original doit être réellement mort
- ✅ Archive doit être accessible (HTTP 200)
- ✅ Archive doit correspondre au même contenu
- ✅ Archive rejetée si contenu ressemble à une page 404
- ✅ Diff minimal validé avant application
