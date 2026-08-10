# Guide Utilisateur - Arrêt d'Urgence du Bot

## Comment Arrêter le Bot en Cas de Problème

### Méthode la Plus Simple : Via Page de Discussion

Le bot dispose d'une page de discussion avec un système d'arrêt d'urgence intégré.

---

## Étape 1 : Accéder à la Page de Discussion

1. Allez sur la page de discussion du bot :
   - `https://fr.wikipedia.org/wiki/Discussion_utilisateur:SynsOperatorBot`

---

## Étape 2 : Éditer la Page

1. Cliquez sur le bouton **"Modifier"** en haut de la page
2. La page s'ouvrira en mode édition

---

## Étape 3 : Ajouter le Marqueur d'Arrêt

Dans la section **"Contrôle d'urgence"**, ajoutez cette ligne exacte :

```wikitext
{{! BOT-CONTROL: STOP }}
```

**IMPORTANT** :
- Copiez EXACTEMENT le texte ci-dessus
- Ne modifiez pas le format
- Les accolades `{{ }}` et le point d'exclamation `!` sont importants

---

## Étape 4 : Enregistrer

1. Cliquez sur **"Publier"**
2. La page sera enregistrée

---

## Ce Qui Se Passe Ensuite

Le bot vérifie régulièrement sa page de discussion. Lorsqu'il détecte le marqueur :

```
1. Détection du marqueur {{! BOT-CONTROL: STOP }}
2. Activation du kill switch central
3. Toutes les opérations sont bloquées
4. Le bot s'arrête complètement
```

**Délai** : Le bot détecte généralement l'arrêt dans les 5-10 minutes suivant l'enregistrement.

---

## Comment Redémarrer le Bot

Une fois le problème résolu :

### Étape 1 : Éditer la Page de Discussion

1. Retournez sur la page de discussion
2. Cliquez sur **"Modifier"**

### Étape 2 : Remplacer le Marqueur

Remplacez :
```wikitext
{{! BOT-CONTROL: STOP }}
```

Par :
```wikitext
{{! BOT-CONTROL: RESUME }}
```

### Étape 3 : Enregistrer

1. Cliquez sur **"Publier"**
2. Le bot détectera la commande de reprise

### Étape 4 : Surveiller

⚠️ **IMPORTANT** : Après avoir redémarré le bot, surveillez attentivement son comportement pendant quelques éditions avant de le laisser fonctionner normalement.

---

## Alternative : Commentaire HTML (Plus Technique)

Si le format MediaWiki ne fonctionne pas, vous pouvez utiliser :

```html
<!-- BOT-CONTROL: STOP -->
```

Ou pour reprendre :
```html
<!-- BOT-CONTROL: RESUME -->
```

---

## Pourquoi Ces Marqueurs Sont Sécurisés

✅ **Déterministes** : Format exact, pas d'interprétation
✅ **Pas de fausses positives** : Les commentaires normaux ne déclenchent rien
✅ **Faciles à supprimer** : Juste supprimer la ligne
✅ **Historique visible** : Les modifications sont tracées dans l'historique Wikipédia

---

## Exemples de Ce Qui NE Déclenche PAS l'Arrêt

Ces phrases NE déclencheront PAS l'arrêt du bot :

- "Il faudrait arrêter ce bot"
- "Le bot devrait s'arrêter"
- "Arrêtez le bot s'il vous plaît"
- "Stop the bot"

Seul le marqueur exact `{{! BOT-CONTROL: STOP }}` ou `<!-- BOT-CONTROL: STOP -->` fonctionne.

---

## En Cas d'Urgence Critique

Si le bot cause des dommages immédiats :

1. **D'ABORD** : Ajoutez le marqueur d'arrêt sur la page de discussion
2. **ENSUITE** : Contactez l'opérateur du bot
3. **SI POSSIBLE** : Désactivez le compte bot dans les préférences

Le marqueur de discussion est la méthode la plus rapide et la plus fiable.

---

## Questions Fréquentes

### Q: Combien de temps faut-il pour que le bot s'arrête ?
**R**: Généralement 5-10 minutes après l'enregistrement de la page.

### Q: Puis-je utiliser le marqueur ailleurs sur la page ?
**R**: Oui, le marqueur peut être placé n'importe où sur la page, mais la section "Contrôle d'urgence" est l'endroit prévu.

### Q: Que se passe-t-il si j'oublie de retirer le marqueur ?
**R**: Le bot restera arrêté indéfiniment. Vous devez retirer le marqueur et ajouter le marqueur RESUME pour le redémarrer.

### Q: Puis-je utiliser n'importe quel format de marqueur ?
**R**: Non, utilisez EXACTEMENT `{{! BOT-CONTROL: STOP }}` ou `<!-- BOT-CONTROL: STOP -->`. Tout autre format sera ignoré.

---

## Contact

En cas de problème grave, contactez l'opérateur du bot :
- **Page utilisateur** : [[User:Sysoperator]]
- **Page de discussion** : [[Discussion utilisateur:Sysoperator]]