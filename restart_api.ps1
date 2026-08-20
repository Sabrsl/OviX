# PowerShell script to restart the API server
Write-Host "Stopping any existing API server..."
Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -eq ""} | Stop-Process -Force

Write-Host "Starting API server..."
Start-Process python -ArgumentList "backend/api/main_standalone.py" -NoNewWindow

Write-Host "Waiting for server to start..."
Start-Sleep -Seconds 3

Write-Host "Testing health endpoint..."
try {
    $response = Invoke-WebRequest -Uri http://127.0.0.1:8001/api/health -UseBasicParsing
    Write-Host "Health check: $($response.StatusCode)"
} catch {
    Write-Host "Health check failed: $_"
}

Write-Host "Testing Wikipedia client endpoint..."
try {
    $response = Invoke-WebRequest -Uri http://127.0.0.1:8001/api/test-wikipedia-client -UseBasicParsing
    Write-Host "Wikipedia client test: $($response.StatusCode)"
    Write-Host "Response: $($response.Content)"
} catch {
    Write-Host "Wikipedia client test failed: $_"
}

Write-Host "Server is running on http://127.0.0.1:8001"
