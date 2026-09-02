"""
Token Generator CLI for secure Wikipedia talk page control.

This utility allows operators to generate secure one-time-use tokens
for emergency bot control via Wikipedia discussion pages.

Usage:
    python generate_wiki_tokens.py --operator "YourName" --generate-wiki
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from wikipedia_maintenance.utils.talk_page_tokens import (
        get_token_manager,
        TokenType,
        TokenStatus
    )
    from wikipedia_maintenance.utils.kill_switch_templates import (
        get_secure_discussion_page_template
    )
except ImportError as e:
    print(f"Erreur d'import : {e}")
    print("Assurez-vous que le module wikipedia_maintenance est disponible")
    sys.exit(1)


def generate_tokens(
    operator_name: str = "operator",
    base_url: str = "http://localhost:8000",
    expiry_hours: int = 24
) -> dict:
    """
    Generate secure tokens for both stop and resume actions.
    
    Args:
        operator_name: Name of the operator requesting tokens
        base_url: Base URL of the API
        expiry_hours: Token expiration time in hours
        
    Returns:
        Dictionary with token information
    """
    print(f"[SECURE] Generation of secure tokens for {operator_name}")
    print(f"[TIME] Expiration: {expiry_hours} hours")
    print("-" * 50)
    
    # Get token manager
    try:
        token_manager = get_token_manager(token_expiry_hours=expiry_hours)
    except Exception as e:
        print(f"[ERROR] Failed to initialize token manager: {e}")
        print("[INFO] Make sure the database is initialized first")
        raise
    
    # Generate stop token
    stop_token_id, stop_actual_token = token_manager.generate_token(
        token_type=TokenType.EMERGENCY_STOP,
        requested_by=operator_name,
        metadata={"purpose": "emergency_stop", "operator": operator_name}
    )
    
    # Generate resume token
    resume_token_id, resume_actual_token = token_manager.generate_token(
        token_type=TokenType.RESUME,
        requested_by=operator_name,
        metadata={"purpose": "resume", "operator": operator_name}
    )
    
    # Generate secure URLs
    stop_url = token_manager.generate_secure_url(
        stop_token_id, stop_actual_token, base_url
    )
    resume_url = token_manager.generate_secure_url(
        resume_token_id, resume_actual_token, base_url
    )
    
    results = {
        "stop": {
            "token_id": stop_token_id,
            "token": stop_actual_token,
            "url": stop_url,
            "type": "emergency_stop"
        },
        "resume": {
            "token_id": resume_token_id,
            "token": resume_actual_token,
            "url": resume_url,
            "type": "resume"
        },
        "operator": operator_name,
        "expiry_hours": expiry_hours,
        "base_url": base_url
    }
    
    return results


def display_token_info(token_info: dict, action: str) -> None:
    """
    Display token information in a user-friendly format.
    
    Args:
        token_info: Token information dictionary
        action: Action type (stop/resume)
    """
    print(f"\n[LINK] Secure link for {action.upper()}:")
    print("-" * 50)
    print(f"URL: {token_info['url']}")
    print(f"Token ID: {token_info['token_id']}")
    print(f"Token (secret): {token_info['token']}")
    print(f"Type: {token_info['type']}")
    print("\n[IMPORTANT] SECURITY NOTES:")
    print("- This link is one-time use only")
    print("- It expires after 24 hours")
    print("- Keep the token secret and secure")
    print("- Do not share this link publicly")


def generate_wiki_markup(
    bot_name: str = "OviXCore",
    operator_name: str = "operator",
    discussion_page: str = "Discussion utilisateur:OviXCore",
    repository: str = "https://github.com/yourusername/repo",
    token_info: dict = None
) -> str:
    """
    Generate Wikipedia markup for the discussion page with secure links.
    
    Args:
        bot_name: Name of the bot
        operator_name: Name of the operator
        discussion_page: Full title of the discussion page
        repository: Repository URL
        token_info: Token information from generate_tokens()
        
    Returns:
        Complete wikitext for the discussion page
    """
    if token_info:
        stop_link = f"[{token_info['stop']['url']} ARRETER OviX]"
        resume_link = f"[{token_info['resume']['url']} REPRIRE]"
        stop_status = "Actif (valide 24h)"
        resume_status = "Actif (valide 24h)"
    else:
        stop_link = "Non disponible - contactez l'opérateur"
        resume_link = "Non disponible - contactez l'opérateur"
        stop_status = "Non généré"
        resume_status = "Non généré"
    
    return get_secure_discussion_page_template(
        bot_name=bot_name,
        operator_name=operator_name,
        discussion_page=discussion_page,
        repository=repository,
        status="RUNNING",
        stop_link_url=stop_link,
        resume_link_url=resume_link,
        stop_link_status=stop_status,
        resume_link_status=resume_status
    )


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Générateur de tokens sécurisés pour le contrôle d'urgence OviX"
    )
    
    parser.add_argument(
        "--operator",
        default="operator",
        help="Nom de l'opérateur demandant les tokens"
    )
    
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="URL de base de l'API OviX"
    )
    
    parser.add_argument(
        "--expiry",
        type=int,
        default=24,
        help="Durée de validité des tokens en heures (défaut: 24)"
    )
    
    parser.add_argument(
        "--bot-name",
        default="OviXCore",
        help="Nom du bot"
    )
    
    parser.add_argument(
        "--wiki-page",
        default="Discussion utilisateur:OviXCore",
        help="Titre de la page de discussion Wikipédia"
    )
    
    parser.add_argument(
        "--repository",
        default="https://github.com/yourusername/repo",
        help="URL du dépôt du projet"
    )
    
    parser.add_argument(
        "--generate-wiki",
        action="store_true",
        help="Générer le markup Wikipédia complet"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier de sortie pour le markup Wikipédia"
    )
    
    args = parser.parse_args()
    
    # Generate tokens
    token_info = generate_tokens(
        operator_name=args.operator,
        base_url=args.base_url,
        expiry_hours=args.expiry
    )
    
    # Display token information
    display_token_info(token_info["stop"], "arrêt")
    display_token_info(token_info["resume"], "reprise")
    
    # Generate wiki markup if requested
    if args.generate_wiki:
        print("\n" + "=" * 50)
        print("[WIKI] Generated Wikipedia markup:")
        print("=" * 50)
        
        wiki_markup = generate_wiki_markup(
            bot_name=args.bot_name,
            operator_name=args.operator,
            discussion_page=args.wiki_page,
            repository=args.repository,
            token_info=token_info
        )
        
        print(wiki_markup)
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(wiki_markup)
            print(f"\n[SUCCESS] Markup saved to: {args.output}")
        
        print("\n[INSTRUCTIONS] Usage:")
        print("1. Copy this markup")
        print("2. Paste it on the bot's discussion page")
        print("3. The secure links will be active immediately")
        
        # Also save without emojis to avoid encoding issues
        clean_markup = wiki_markup.replace("🛑", "[STOP]").replace("▶️", "[RESUME]").replace("✅", "[OK]")
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(clean_markup)
            print(f"\n[SUCCESS] Clean markup saved to: {args.output}")
        else:
            print("\n[CLEAN MARKUP] (without special characters):")
            print(clean_markup)
    
    print("\n[SUCCESS] Operation completed successfully!")


if __name__ == "__main__":
    main()