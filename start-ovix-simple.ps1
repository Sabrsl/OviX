# OVIX Simple Startup Script
# Starts both backend and frontend servers in separate terminal windows

$ErrorActionPreference = "Continue"

Write-Host "Starting OVIX Dead Linker Bot..." -ForegroundColor Green
Write-Host ""

# Kill existing processes on ports 8000, 3000 and 5173
Write-Host "Checking for existing processes..." -ForegroundColor Cyan

try {
    # Check port 8000
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($port8000) {
        Write-Host "Port 8000 is in use, stopping process..." -ForegroundColor Yellow
        $port8000.OwningProcess | ForEach-Object { 
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped process $_ on port 8000" -ForegroundColor Green
        }
    }

    # Check port 3000
    $port3000 = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
    if ($port3000) {
        Write-Host "Port 3000 is in use, stopping process..." -ForegroundColor Yellow
        $port3000.OwningProcess | ForEach-Object { 
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped process $_ on port 3000" -ForegroundColor Green
        }
    }

    # Check port 5173 (Vite default)
    $port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
    if ($port5173) {
        Write-Host "Port 5173 is in use, stopping process..." -ForegroundColor Yellow
        $port5173.OwningProcess | ForEach-Object { 
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped process $_ on port 5173" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "Warning: Could not check/stop existing processes: $_" -ForegroundColor Yellow
}

Start-Sleep -Seconds 2

# Get current directory
$currentDir = Get-Location
Write-Host "Current directory: $currentDir" -ForegroundColor Cyan

# Check if backend directory exists
$backendDir = "$currentDir\backend"
if (-not (Test-Path $backendDir)) {
    Write-Host "Error: Backend directory not found: $backendDir" -ForegroundColor Red
    exit 1
}

# Check if frontend directory exists
$frontendDir = "$currentDir\frontend"
if (-not (Test-Path $frontendDir)) {
    Write-Host "Error: Frontend directory not found: $frontendDir" -ForegroundColor Red
    exit 1
}

# Start Backend in new terminal window
Write-Host "Starting Backend (FastAPI) in new terminal..." -ForegroundColor Cyan
$backendCommand = "python -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000"
Write-Host "Backend command: $backendCommand" -ForegroundColor Gray

try {
    $backendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand -WindowStyle Normal -PassThru
    if ($backendProcess) {
        Write-Host "Backend terminal opened (PID: $($backendProcess.Id))" -ForegroundColor Green
    } else {
        Write-Host "Warning: Backend process may not have started properly" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error starting backend: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Wait for backend to start
Write-Host "Waiting for backend to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 3

# Start Frontend in new terminal window
Write-Host "Starting Frontend (React/Vite) in new terminal..." -ForegroundColor Cyan
$frontendCommand = "cd '$frontendDir'; npm run dev"
Write-Host "Frontend command: $frontendCommand" -ForegroundColor Gray

try {
    $frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand -WindowStyle Normal -PassThru
    if ($frontendProcess) {
        Write-Host "Frontend terminal opened (PID: $($frontendProcess.Id))" -ForegroundColor Green
    } else {
        Write-Host "Warning: Frontend process may not have started properly" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error starting frontend: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "OVIX Application Started Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor White
Write-Host "Backend:  http://0.0.0.0:8000" -ForegroundColor White
Write-Host "API Docs: http://0.0.0.0:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Two new terminal windows have been opened:" -ForegroundColor Yellow
Write-Host "- One for the Backend (FastAPI)" -ForegroundColor White
Write-Host "- One for the Frontend (React/Vite)" -ForegroundColor White
Write-Host ""
Write-Host "Close the terminal windows to stop the servers." -ForegroundColor Yellow
Write-Host ""