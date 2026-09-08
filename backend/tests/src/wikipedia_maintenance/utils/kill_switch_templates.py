"""
User-friendly templates for kill switch control via bot discussion page.

This provides practical, easy-to-use templates for emergency bot control.
"""

# Template de page de discussion du bot avec contrôle d'urgence
BOT_DISCUSSION_TEMPLATE = """
{{Page de maintenance de bot}}

== Informations sur le bot ==
* '''Nom du bot''' : {bot_name}
* '''Opérateur''' : [[User:{operator_name}|{operator_name}]]
* '''Objectif''' : Maintenance automatisée et corrections Wikipédia
* '''Statut d'approbation''' : [[Wikipedia:Requêtes de bot|En attente d'approbation]]

== Contrôle d'urgence ==

{{Bot control}}
{{! IMPORTANT : N'utilisez cette section que pour le contrôle d'urgence }}

=== Arrêt d'urgence ===
Pour arrêter immédiatement le bot en cas de problème, ajoutez ce marqueur ci-dessous :

{{! BOT-CONTROL: STOP }}

Le bot détectera ce marqueur et arrêtera toutes les opérations.
Après l'arrêt, vous pouvez retirer le marqueur pour permettre au bot de reprendre (si c'est sûr).

Statut actuel : {{! BOT-STATUS: {status} }}

=== Comment utiliser ===
1. Si le bot cause des problèmes, éditez cette page
2. Ajoutez `{{! BOT-CONTROL: STOP }}` n'importe où dans cette section
3. Enregistrez la page
4. Le bot détectera le marqueur lors du prochain cycle de vérification
5. Toutes les opérations seront bloquées

=== Redémarrer le bot ===
Pour permettre au bot de reprendre après un arrêt d'urgence :
1. Retirez le marqueur `{{! BOT-CONTROL: STOP }}`
2. Ajoutez le marqueur `{{! BOT-CONTROL: RESUME }}`
3. Enregistrez la page
4. Le bot détectera la commande de reprise
5. Surveillez attentivement le comportement du bot avant de permettre un fonctionnement complet

== Opérations récentes ==
Le tableau suivant montre les opérations récentes du bot :

{{! Cette section sera automatiquement mise à jour par le bot }}

== Feedback et problèmes ==
Les membres de la communauté peuvent signaler des problèmes ou fournir des feedback ici :
* Utilisez la section ci-dessous pour signaler des problèmes
* Incluez le titre de l'article et la description du problème
* L'opérateur du bot examinera tous les signalements

=== Signalements de problèmes ===
{{! Ajoutez de nouveaux signalements ci-dessous }}

== Contact ==
* '''Opérateur du bot''' : [[User talk:{operator_name}|Contacter l'opérateur]]
* '''Discussion du bot''' : [[{discussion_page}|Cette page]]
* '''Dépôt''' : {repository}

----
''Dernière mise à jour : {last_updated}'' 
""".strip()


# Version simplifiée pour le marqueur
EMERGENCY_STOP_MARKER = "{{! BOT-CONTROL: STOP }}"
EMERGENCY_RESUME_MARKER = "{{! BOT-CONTROL: RESUME }}"


# Template sécurisé avec tokens
SECURE_BOT_DISCUSSION_TEMPLATE = """
{{Page de maintenance de bot}}

== Informations sur le bot ==
* '''Nom du bot''' : {bot_name}
* '''Opérateur''' : [[User:{operator_name}|{operator_name}]]
* '''Objectif''' : Maintenance automatisée et corrections Wikipédia
* '''Statut d'approbation''' : [[Wikipedia:Requêtes de bot|En attente d'approbation]]

== Contrôle d'urgence sécurisé ==

{{Bot control}}
{{! IMPORTANT : Cette section utilise des tokens sécurisés pour un contrôle d'urgence }}

=== Arrêt d'urgence sécurisé ===
En cas de problème avec les modifications automatisées du bot, utilisez les liens sécurisés ci-dessous :

'''Statut actuel :''' {status}

{{! Lien sécurisé d'arrêt d'urgence (généré par l'opérateur) }}
*Pour générer un nouveau lien sécurisé, contactez l'opérateur du bot.*

Statut du lien d'arrêt : {stop_link_status}

Statut du lien de reprise : {resume_link_status}

Liens actuels :
* Arrêt : {stop_link_url}
* Reprise : {resume_link_url}

=== Comment utiliser ===
1. Si le bot cause des problèmes, cliquez sur le lien d'arrêt sécurisé
2. Le lien utilise un token à usage unique et expire après 24 heures
3. Le bot détectera l'arrêt immédiatement et bloquera toutes les opérations
4. Le lien sera consommé après utilisation (pour plus de sécurité)

=== Redémarrer le bot ===
Pour permettre au bot de reprendre après un arrêt d'urgence :
1. Utilisez le lien de reprise sécurisé
2. Le lien utilise un token à usage unique et expire après 24 heures
3. Le bot détectera la commande de reprise
4. Surveillez attentivement le comportement du bot avant de permettre un fonctionnement complet

=== Méthode alternative (en cas d'échec des liens) ===
Si les liens sécurisés ne fonctionnent pas, vous pouvez utiliser les marqueurs manuels :

Pour arrêter : Ajoutez `{{! BOT-CONTROL: STOP }}` n'importe où sur cette page
Pour reprendre : Ajoutez `{{! BOT-CONTROL: RESUME }}` sur cette page

== Opérations récentes ==
Le tableau suivant montre les opérations récentes du bot :

{{! Cette section sera automatiquement mise à jour par le bot }}

== Feedback et problèmes ==
Les membres de la communauté peuvent signaler des problèmes ou fournir des feedback ici :
* Utilisez la section ci-dessous pour signaler des problèmes
* Incluez le titre de l'article et la description du problème
* L'opérateur du bot examinera tous les signalements

=== Signalements de problèmes ===
{{! Ajoutez de nouveaux signalements ci-dessous }}

== Contact ==
* '''Opérateur du bot''' : [[User talk:{operator_name}|Contacter l'opérateur]]
* '''Discussion du bot''' : [[{discussion_page}|Cette page]]
* '''Dépôt''' : {repository}

----
''Dernière mise à jour : {last_updated}'' 
""".strip()


def get_discussion_page_template(
    bot_name: str,
    operator_name: str,
    discussion_page: str,
    repository: str,
    status: str = "RUNNING"
) -> str:
    """
    Generate the complete discussion page template.
    
    Args:
        bot_name: Name of the bot
        operator_name: Name of the operator
        discussion_page: Full title of the discussion page
        repository: Repository URL
        status: Current bot status
        
    Returns:
        Complete wikitext for the discussion page
    """
    from datetime import datetime
    
    return BOT_DISCUSSION_TEMPLATE.format(
        bot_name=bot_name,
        operator_name=operator_name,
        discussion_page=discussion_page,
        repository=repository,
        status=status,
        last_updated=datetime.now().strftime("%d %B %Y %H:%M")
    )


def get_emergency_stop_instructions() -> str:
    """
    Get user-friendly instructions for emergency stop.
    
    Returns:
        Plain text instructions
    """
    return """
INSTRUCTIONS D'ARRÊT D'URGENCE DU BOT

Si le bot cause des problèmes, suivez ces étapes :

1. Allez sur la page de discussion du bot
2. Cliquez sur "Modifier" ou "Edit"
3. Ajoutez cette ligne exacte dans la section "Contrôle d'urgence" :
   {{! BOT-CONTROL: STOP }}
4. Enregistrez la page
5. Le bot détectera ce marqueur et s'arrêtera dans le prochain cycle de vérification

IMPORTANT :
- Utilisez le format de marqueur EXACT indiqué ci-dessus
- Ne modifiez pas le texte du marqueur
- Le bot vérifie régulièrement sa page de discussion
- Après l'arrêt, investigate le problème avant de reprendre

POUR REDÉMARRER :
1. Retirez le marqueur {{! BOT-CONTROL: STOP }}
2. Ajoutez le marqueur {{! BOT-CONTROL: RESUME }}
3. Enregistrez la page
4. Surveillez attentivement le comportement du bot
""".strip()


def get_secure_discussion_page_template(
    bot_name: str,
    operator_name: str,
    discussion_page: str,
    repository: str,
    status: str = "RUNNING",
    stop_link_url: str = "Non disponible - contactez l'opérateur",
    resume_link_url: str = "Non disponible - contactez l'opérateur",
    stop_link_status: str = "Non généré",
    resume_link_status: str = "Non généré"
) -> str:
    """
    Generate the secure discussion page template with token-based links.
    
    Args:
        bot_name: Name of the bot
        operator_name: Name of the operator
        discussion_page: Full title of the discussion page
        repository: Repository URL
        status: Current bot status
        stop_link_url: Secure URL for emergency stop
        resume_link_url: Secure URL for resume
        stop_link_status: Status of stop link (active/expired/used)
        resume_link_status: Status of resume link (active/expired/used)
        
    Returns:
        Complete wikitext for the discussion page
    """
    from datetime import datetime
    
    return SECURE_BOT_DISCUSSION_TEMPLATE.format(
        bot_name=bot_name,
        operator_name=operator_name,
        discussion_page=discussion_page,
        repository=repository,
        status=status,
        stop_link_url=stop_link_url,
        resume_link_url=resume_link_url,
        stop_link_status=stop_link_status,
        resume_link_status=resume_link_status,
        last_updated=datetime.now().strftime("%d %B %Y %H:%M")
    )