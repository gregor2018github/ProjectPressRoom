#Requires -Version 5.1
<#
.SYNOPSIS
    Build the Pressroom frontend and start the server.
.DESCRIPTION
    1. Builds the React frontend (npm run build).
    2. Opens http://127.0.0.1:8000 in the default browser once the server is ready.
    3. Starts the FastAPI server (blocks — press Ctrl-C to stop).
.PARAMETER SkipBuild
    Skip the frontend build step (use the last build in frontend/dist/).
#>
param(
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pressroom = "$root\backend\.venv\Scripts\pressroom.exe"
$frontend  = "$root\frontend"

# Sanity checks
if (-not (Test-Path $pressroom)) {
    Write-Host "ERROR: pressroom not found at $pressroom" -ForegroundColor Red
    Write-Host "Run:  cd backend; python -m venv .venv; .\.venv\Scripts\pip install -e '.[dev]'" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path "$frontend\package.json")) {
    Write-Host "ERROR: frontend/package.json not found." -ForegroundColor Red
    exit 1
}

# 1. Build frontend
if ($SkipBuild) {
    Write-Host "Skipping frontend build (-SkipBuild)." -ForegroundColor DarkGray
} else {
    Write-Host ""
    Write-Host "Building frontend..." -ForegroundColor Cyan
    Set-Location $frontend
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Frontend build failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "Frontend build complete." -ForegroundColor Green
}

# 2. Open browser after a short delay (server needs ~2s to start)
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    '-NoProfile', '-Command',
    "Start-Sleep 2; Start-Process 'http://127.0.0.1:8000'"
)

# 3. Start server (blocking — Ctrl-C to stop)
Write-Host ""
Write-Host "Starting Pressroom at http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl-C to stop." -ForegroundColor DarkGray
Write-Host ""
Set-Location "$root\backend"
& $pressroom serve
