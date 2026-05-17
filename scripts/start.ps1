<#
.SYNOPSIS
    xtquant trading system startup script (Windows)

.DESCRIPTION
    Auto-check PostgreSQL, init database, start backend and frontend.

.PARAMETER Backend
    Start backend API server only

.PARAMETER Frontend
    Start frontend dev server only

.PARAMETER Trade
    Start Trade Engine only (requires QMT running)

.PARAMETER Full
    Start backend + frontend (same as default)

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 --Backend
    .\scripts\start.ps1 --Trade
#>

param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Trade,
    [switch]$Full
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OriginalDir = Get-Location
Set-Location $ProjectRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  xtquant Trading System" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

# ---- PostgreSQL ----
Write-Host "[1/3] PostgreSQL..." -ForegroundColor Yellow
$pgRunning = docker ps --filter "name=xtquant_postgres" --format "{{.Names}}" 2>$null
if (-not $pgRunning) {
    docker compose -f (Join-Path $ProjectRoot "docker\docker-compose.yml") up -d postgres 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Write-Host "  PostgreSQL started" -ForegroundColor Green
} else {
    Write-Host "  PostgreSQL running" -ForegroundColor Green
}

# ---- Database init ----
Write-Host "[2/3] Database..." -ForegroundColor Yellow
try {
    & $VenvPython (Join-Path $ProjectRoot "scripts\setup_db.py") 2>&1 | Out-Null
    Write-Host "  Database ready" -ForegroundColor Green
} catch {
    Write-Host "  Database init skipped" -ForegroundColor DarkYellow
}

# ---- Start services ----
if ($Trade) {
    Write-Host "[3/3] Trade Engine starting..." -ForegroundColor Yellow
    & $VenvPython -m backend.main --trade
    Set-Location $OriginalDir
    return
}

if ($Backend) {
    Write-Host "[3/3] Backend API: http://127.0.0.1:8000" -ForegroundColor Yellow
    Write-Host "  Docs: http://localhost:8000/docs" -ForegroundColor Gray
    & $VenvPython -m backend.main
    Set-Location $OriginalDir
    return
}

if ($Frontend) {
    Write-Host "[3/3] Frontend: http://localhost:5173" -ForegroundColor Yellow
    Set-Location (Join-Path $ProjectRoot "frontend")
    try {
        npm run dev
    } finally {
        Set-Location $OriginalDir
    }
    return
}

# Default / --Full: start backend + frontend together
Write-Host "[3/3] Starting backend + frontend..." -ForegroundColor Yellow
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Docs:     http://localhost:8000/docs" -ForegroundColor White
Write-Host ""

$backendProc = $null

try {
    # Start backend in background
    $backendProc = Start-Process -FilePath $VenvPython -ArgumentList "-m","backend.main" -NoNewWindow -PassThru
    Start-Sleep -Seconds 6

    # Start frontend in foreground
    Set-Location (Join-Path $ProjectRoot "frontend")
    npm run dev
} finally {
    # Restore original working directory
    Set-Location $OriginalDir

    # Graceful shutdown: request backend to stop via API, then kill if needed
    if ($backendProc) {
        Write-Host "Shutting down backend..." -ForegroundColor Yellow
        try {
            Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/shutdown" -Method POST -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
            Start-Sleep -Seconds 3
        } catch {
            # Shutdown endpoint may not exist yet
        }
        # Ensure process is gone
        if (-not $backendProc.HasExited) {
            Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
        }
        Write-Host "Backend stopped" -ForegroundColor Green
    }
}
