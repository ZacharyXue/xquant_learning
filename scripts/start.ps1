#!/usr/bin/env pwsh
<#
.SYNOPSIS
    xtquant trading system startup script (Windows)

.DESCRIPTION
    Auto-check PostgreSQL, init database, start backend and/or frontend.

.PARAMETER Trade
    Start Trade Engine only (requires QMT running)

.PARAMETER Full
    Start Dashboard + Trade Engine

.PARAMETER Backend
    Start backend API server only

.PARAMETER Frontend
    Start frontend dev server only

.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 --Backend
    .\scripts\start.ps1 --Full
#>

param(
    [switch]$Trade,
    [switch]$Full,
    [switch]$Backend,
    [switch]$Frontend
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  xtquant Trading System" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

# ---- PostgreSQL ----
Write-Host "[1/3] PostgreSQL..." -ForegroundColor Yellow
$pgRunning = docker ps --filter "name=xtquant_postgres" --format "{{.Names}}" 2>$null
if (-not $pgRunning) {
    docker compose -f "$ProjectRoot\docker\docker-compose.yml" up -d postgres 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    Write-Host "  PostgreSQL started" -ForegroundColor Green
} else {
    Write-Host "  PostgreSQL running" -ForegroundColor Green
}

# ---- Database init ----
Write-Host "[2/3] Database..." -ForegroundColor Yellow
try {
    & $VenvPython "$ProjectRoot\scripts\setup_db.py" 2>&1 | Out-Null
    Write-Host "  Database ready" -ForegroundColor Green
} catch {
    Write-Host "  Database init skipped" -ForegroundColor DarkYellow
}

# ---- Start services ----
if ($Trade) {
    Write-Host "[3/3] Trade Engine starting..." -ForegroundColor Yellow
    & $VenvPython -m backend.main --trade
} elseif ($Full) {
    Write-Host "[3/3] Full system starting..." -ForegroundColor Yellow
    & $VenvPython -m backend.main --full
} elseif ($Backend) {
    Write-Host "[3/3] Backend API: http://127.0.0.1:8000" -ForegroundColor Yellow
    Write-Host "  Docs: http://localhost:8000/docs" -ForegroundColor Gray
    & $VenvPython -m backend.main
} elseif ($Frontend) {
    Write-Host "[3/3] Frontend: http://localhost:5173" -ForegroundColor Yellow
    Set-Location "$ProjectRoot\frontend"
    npm run dev
} else {
    Write-Host "[3/3] Backend: http://127.0.0.1:8000" -ForegroundColor Yellow
    Write-Host "  Frontend: cd frontend; npm run dev" -ForegroundColor Gray
    Write-Host "  Docs: http://localhost:8000/docs" -ForegroundColor Gray
    & $VenvPython -m backend.main
}
