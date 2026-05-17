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
    Start Dashboard + Trade Engine + Frontend (requires QMT running)

.PARAMETER AccountId
    QMT trading account ID (required for --Trade and --Full)

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 --Backend
    .\scripts\start.ps1 --Full -AccountId "1234567890"
#>

param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Trade,
    [switch]$Full,
    [string]$AccountId = ""
)

# --Full implies backend with Trade Engine
$BackendArgs = "-m", "backend.main"
if ($Full -or $Trade) {
    $BackendArgs = "-m", "backend.main", "--full"
}
if ($Trade) {
    $BackendArgs = "-m", "backend.main", "--trade"
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OriginalDir = Get-Location
Set-Location $ProjectRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

# ---- QMT Environment ----
$qmtPath = "D:\国金证券QMT交易端\userdata_mini"
if (-not (Test-Path $qmtPath)) {
    Write-Host "WARNING: QMT not found at $qmtPath" -ForegroundColor Red
}
$env:XTQUANT_QMT_PATH = $qmtPath

if ($AccountId) {
    $env:XTQUANT_ACCOUNT_ID = $AccountId
} elseif (-not $env:XTQUANT_ACCOUNT_ID) {
    if ($Trade -or $Full) {
        Write-Host "WARNING: XTQUANT_ACCOUNT_ID not set. Trade Engine will fail." -ForegroundColor Yellow
        Write-Host "  Usage: .\scripts\start.ps1 --Full -AccountId 'your_account_id'" -ForegroundColor Gray
    }
}

# Check QMT client is running
$qmtRunning = Get-Process -Name "XtItClient","XtMiniQmt" -ErrorAction SilentlyContinue
if ($Trade -or $Full) {
    if (-not $qmtRunning) {
        Write-Host "ERROR: QMT client not running! Please start QMT and login first." -ForegroundColor Red
        Set-Location $OriginalDir
        return
    }
    Write-Host "QMT client detected" -ForegroundColor Green
}

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
    & $VenvPython @BackendArgs
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
$modeLabel = if ($Full) { "Dashboard + Trade Engine" } else { "Dashboard" }
Write-Host "[3/3] Starting $modeLabel + frontend..." -ForegroundColor Yellow
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Docs:     http://localhost:8000/docs" -ForegroundColor White
Write-Host ""

$backendProc = $null

try {
    # Start backend in background
    $backendProc = Start-Process -FilePath $VenvPython -ArgumentList $BackendArgs -NoNewWindow -PassThru
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
            Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/api/shutdown" -Method POST -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
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
