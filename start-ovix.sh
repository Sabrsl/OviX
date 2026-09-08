#!/bin/bash

# Script de démarrage OVIX - Lance le backend API et le frontend ensemble

echo "Démarrage d'OVIX..."
echo ""

# Vérifier si l'API est déjà en cours
if pgrep -f "uvicorn backend.api.main:app" > /dev/null; then
    echo "⚠️  Une instance uvicorn existe déjà. Arrêt..."
    pkill -f "uvicorn backend.api.main:app"
    sleep 2
fi

# Démarrer l'API FastAPI
echo "🚀 Démarrage de l'API FastAPI..."
python -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!
sleep 3

# Vérifier si le frontend est déjà en cours
if pgrep -f "vite" > /dev/null; then
    echo "⚠️  Une instance Vite existe déjà. Arrêt..."
    pkill -f "vite"
    sleep 2
fi

# Démarrer le frontend React
echo "🎨 Démarrage du frontend React..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
sleep 3

echo ""
echo "✅ OVIX est maintenant en cours d'exécution!"
echo ""
echo "📍 Frontend: http://localhost:3000"
echo "📍 API: http://localhost:8000"
echo "📍 Documentation API: http://localhost:8000/docs"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter"

# Fonction de nettoyage
cleanup() {
    echo ""
    echo "Arrêt d'OVIX..."
    
    # Arrêter les processus
    if kill $API_PID 2>/dev/null; then
        echo "Arrêt de l'API..."
    fi
    
    if kill $FRONTEND_PID 2>/dev/null; then
        echo "Arrêt du frontend..."
    fi
    
    # Nettoyage supplémentaire
    pkill -f "uvicorn backend.api.main:app" 2>/dev/null
    pkill -f "vite" 2>/dev/null
    
    echo "✅ OVIX arrêté"
    exit 0
}

# Capturer SIGINT et SIGTERM
trap cleanup SIGINT SIGTERM

# Attendre que l'utilisateur appuie sur Ctrl+C
while true; do
    sleep 1
done
