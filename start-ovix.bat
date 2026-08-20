@echo off
REM Script de démarrage OVIX - Lance le backend API et le frontend ensemble

echo Démarrage d'OVIX...
echo.

REM Arrêter les processus existants
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Démarrer l'API FastAPI
echo 🚀 Démarrage de l'API FastAPI...
start /B python backend/api/main_standalone.py
timeout /t 3 /nobreak >nul

REM Démarrer le frontend React
echo 🎨 Démarrage du frontend React...
cd frontend
start /B npm run dev
cd ..
timeout /t 3 /nobreak >nul

echo.
echo ✅ OVIX est maintenant en cours d'exécution!
echo.
echo 📍 Frontend: http://localhost:3000
echo 📍 API: http://localhost:8001
echo 📍 Documentation API: http://localhost:8001/docs
echo.
echo Appuyez sur Ctrl+C pour arrêter
echo.

REM Attendre que l'utilisateur appuie sur Ctrl+C
pause

REM Arrêter les processus
echo.
echo Arrêt d'OVIX...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
echo ✅ OVIX arrêté
