# Script de démarrage OVIX - Lance le backend API et le frontend ensemble

Write-Host "Démarrage d'OVIX..." -ForegroundColor Green
Write-Host ""

# Vérifier si l'API est déjà en cours
$apiProcess = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq "" }
if ($apiProcess) {
    Write-Host "⚠️  Une instance Python existe déjà. Arrêt..." -ForegroundColor Yellow
    $apiProcess | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# Démarrer l'API FastAPI
Write-Host "🚀 Démarrage de l'API FastAPI..." -ForegroundColor Blue
$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "backend.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000" -PassThru -NoNewWindow
Start-Sleep -Seconds 3

# Vérifier si le frontend est déjà en cours
$frontendProcess = Get-Process -Name node -ErrorAction SilentlyContinue
if ($frontendProcess) {
    Write-Host "⚠️  Une instance Node existe déjà. Arrêt..." -ForegroundColor Yellow
    $frontendProcess | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# Démarrer le frontend React
Write-Host "🎨 Démarrage du frontend React..." -ForegroundColor Blue
Push-Location "frontend"
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -NoNewWindow
Pop-Location

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "✅ OVIX est maintenant en cours d'exécution!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "📍 API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📍 Documentation API: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Appuyez sur Ctrl+C pour arrêter" -ForegroundColor Yellow

# Attendre que l'utilisateur appuie sur Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "Arrêt d'OVIX..." -ForegroundColor Yellow
    
    # Arrêter les processus
    if ($apiProcess -and !$apiProcess.HasExited) {
        Write-Host "Arrêt de l'API..." -ForegroundColor Gray
        $apiProcess | Stop-Process -Force
    }
    
    if ($frontendProcess -and !$frontendProcess.HasExited) {
        Write-Host "Arrêt du frontend..." -ForegroundColor Gray
        $frontendProcess | Stop-Process -Force
    }
    
    Write-Host "✅ OVIX arrêté" -ForegroundColor Green
}
