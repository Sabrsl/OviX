# Test modification lang
$body = '{"section":"wikipedia","key":"lang","value":"de"}'
$response = Invoke-WebRequest -Uri 'http://localhost:8000/api/config/value' -Method PUT -Body $body -ContentType 'application/json' -UseBasicParsing
Write-Host "Modification lang vers 'de':"
$response.Content

# Vérification après modification
Start-Sleep -Seconds 1
$response = Invoke-WebRequest -Uri 'http://localhost:8000/api/config/' -Method GET -UseBasicParsing
$config = $response.Content | ConvertFrom-Json
Write-Host "`nLang après modification:"
$config.config.wikipedia.lang