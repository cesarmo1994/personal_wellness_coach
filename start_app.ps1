param(
  [string]$ApiKey = $env:OPENAI_API_KEY,
  [string]$Model = "gpt-5.2"
)

Set-Location -LiteralPath $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
  $ApiKey = Read-Host "Pegá tu OPENAI_API_KEY"
}

$env:OPENAI_API_KEY = $ApiKey
$env:OPENAI_MODEL = $Model

Write-Host ""
Write-Host "The Pichudo's App arrancando..." -ForegroundColor Green
Write-Host "Abrí esta dirección exacta:" -ForegroundColor Yellow
Write-Host "http://127.0.0.1:3000/" -ForegroundColor Cyan
Write-Host ""
Write-Host "No cierres esta ventana mientras estés usando la app." -ForegroundColor Yellow
Write-Host ""

python server.py
