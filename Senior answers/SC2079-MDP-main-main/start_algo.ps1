$ErrorActionPreference = "Stop"

$AlgoDir = "C:\github\SC2079-MDP-main\algo"

if (-not (Test-Path $AlgoDir)) {
    throw "Algo directory not found: $AlgoDir"
}

Write-Host "Starting algo backend (Flask)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList '-NoExit','-Command','python main.py' -WorkingDirectory $AlgoDir

Start-Sleep -Seconds 1

Write-Host "Starting algo frontend (Next.js)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList '-NoExit','-Command','npm run dev' -WorkingDirectory $AlgoDir

Start-Sleep -Seconds 2

Write-Host "Opening simulator in browser..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:3000"

Write-Host "Done. Backend and frontend windows launched." -ForegroundColor Green
