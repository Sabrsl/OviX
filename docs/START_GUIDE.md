# OVIX - Démarrage Rapide

## Commande Unique pour Démarrer Frontend + Backend

### Méthode PowerShell (Recommandée)
```powershell
# Démarrer l'API
Start-Process python -ArgumentList "backend/api/main_standalone.py" -NoNewWindow

# Attendre 2 secondes
Start-Sleep -Seconds 2

# Démarrer le frontend
Push-Location "frontend"
Start-Process npm -ArgumentList "run", "dev" -NoNewWindow
Pop-Location
```

### Méthode Batch
```cmd
start /B python backend/api/main_standalone.py
timeout /t 2 /nobreak >nul
cd frontend
start /B npm run dev
cd ..
```

## Accès

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8001
- **Documentation API**: http://localhost:8001/docs

## Arrêt

Pour arrêter OVIX, terminez les processus:
- `python.exe` (API)
- `node.exe` (Frontend)

## Pourquoi Push-Location/Pop-Location?

Les commandes npm doivent être exécutées dans le répertoire `frontend/`. 
- `Push-Location` change temporairement le répertoire de travail
- `Pop-Location` revient au répertoire original après exécution
- C'est plus propre que `cd && cd ..` dans PowerShell
