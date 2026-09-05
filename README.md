# OviX - Bot Wikipedia Dead Linker

**Attention** - Outil en cours de développement. OviX n'est pas encore déployé en production.

OviX est un outil de maintenance Wikipédia conçu pour détecter, analyser et réparer les liens externes morts dans les articles. Le projet automatise les vérifications tout en maintenant une approche prudente : un lien n'est jamais remplacé sur la seule base d'une erreur HTTP. OviX recherche systématiquement des preuves permettant de confirmer qu'une nouvelle URL ou une version archivée correspond bien à la ressource originale.

## Fonctionnalités principales

- **Détection automatique** : Vérification parallèle des liens (jusqu'à 50 liens par article)
- **Classification intelligente** : Distinction entre erreurs permanentes et temporaires
- **Réparation multi-stratégie** : Redirections et services d'archivage multiples
- **Validation par preuves** : Système à trois preuves indépendantes
- **Mode Dry-Run** : Simulation sans publication pour relecture humaine
- **Orchestration automatisée** : Scheduler avec contrôle kill switch
- **Architecture moderne** : Frontend React + Backend FastAPI + SQLite

## Installation

### Prérequis
- Python 3.8+
- Node.js 16+ (pour le frontend)
- Compte Wikipédia

### Étapes

1. **Cloner le dépôt**
```bash
git clone https://github.com/Sabrsl/OviX.git
cd Sabrsl_dead_linker_Bot
```

2. **Installer les dépendances**
```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

3. **Configurer l'environnement**
```bash
cp .env.example .env
cp config/user-config.py.example config/user-config.py
cp config/passwords.py.example config/passwords.py
# Éditer les fichiers avec vos identifiants
```

## Démarrage

### Windows (recommandé)
```powershell
.\start-ovix.ps1
```

### Démarrage manuel
```bash
# Backend API
python scripts/start_api.py

# Frontend React (dans un autre terminal)
cd frontend && npm run dev

# Interface Streamlit (optionnel)
streamlit run app.py
```

## Configuration

La configuration principale se trouve dans `config/config.yaml`. Les paramètres clés :

- **Rate limiting** : 10 éditions/minute, 100 publications/jour
- **Délais** : 3-5 minutes entre publications
- **Sécurité** : Mode dry-run activé par défaut
- **Analyse** : Maximum 50 liens vérifiés par article

## Sécurité

- Mode Dry-Run activé par défaut
- Validation par trois preuves indépendantes
- Remplacement ciblé (pas de substitution globale)
- Kill switch avec monitoring et contrôle via page de discussion
- Limitation de taux avancée avec backoff exponentiel

## Documentation

La documentation détaillée est disponible dans le répertoire `docs/` pour l'installation, l'API, le déploiement et l'architecture technique.

## Contribution

Les contributions sont les bienvenues. Assurez-vous que le code suit les patterns existants, inclut des tests, met à jour la documentation et respecte les règles de sécurité.

## Licence

Ce projet est licencié selon les termes spécifiés dans le fichier LICENSE.
