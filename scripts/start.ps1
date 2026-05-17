#!/usr/bin/env pwsh
<#
.SYNOPSIS
    xtquant 量化交易系统一键启动脚本 (Windows)

.DESCRIPTION
    自动检查并启动 PostgreSQL、初始化数据库、启动后端 API 和前端开发服务器。
    支持参数选择启动模式。

.PARAMETER Trade
    仅启动 Trade Engine (需要 QMT 运行)

.PARAMETER Full
    同时启动 Dashboard 和 Trade Engine

.PARAMETER Backend
    仅启动后端 API 服务

.PARAMETER Frontend
    仅启动前端开发服务器

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

# 项目根目录
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Python 虚拟环境
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  xtquant 量化交易系统" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ===== 检查 PostgreSQL =====
Write-Host "[1/4] 检查 PostgreSQL..." -ForegroundColor Yellow
$pgRunning = docker ps --filter "name=xtquant_postgres" --format "{{.Names}}" 2>$null
if (-not $pgRunning) {
    Write-Host "  启动 PostgreSQL..." -ForegroundColor Gray
    docker compose -f "$ProjectRoot\docker\docker-compose.yml" up -d postgres 2>&1 | Out-Null
    Write-Host "  等待 PostgreSQL 就绪..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
} else {
    Write-Host "  PostgreSQL 已运行" -ForegroundColor Green
}

# ===== 初始化数据库 =====
Write-Host "[2/4] 初始化数据库..." -ForegroundColor Yellow
try {
    & $VenvPython "$ProjectRoot\scripts\setup_db.py" 2>&1 | Out-Null
    Write-Host "  数据库就绪" -ForegroundColor Green
} catch {
    Write-Host "  数据库初始化跳过（可能已就绪）" -ForegroundColor DarkYellow
}

# ===== 选择启动模式 =====
if ($Trade) {
    Write-Host "[3/4] 启动 Trade Engine..." -ForegroundColor Yellow
    Write-Host ""
    & $VenvPython -m backend.main --trade
} elseif ($Full) {
    Write-Host "[3/4] 启动完整服务 (Dashboard + Trade Engine)..." -ForegroundColor Yellow
    Write-Host ""
    & $VenvPython -m backend.main --full
} elseif ($Backend) {
    Write-Host "[3/4] 启动后端 API 服务 (http://127.0.0.1:8000)..." -ForegroundColor Yellow
    Write-Host "  API 文档: http://localhost:8000/docs" -ForegroundColor Gray
    Write-Host ""
    & $VenvPython -m backend.main
} elseif ($Frontend) {
    Write-Host "[3/4] 跳过后端" -ForegroundColor Gray
    Write-Host "[4/4] 启动前端开发服务器 (http://localhost:5173)..." -ForegroundColor Yellow
    Write-Host ""
    Set-Location "$ProjectRoot\frontend"
    npm run dev
} else {
    # 默认：启动后端
    Write-Host "[3/4] 启动后端 API 服务 (http://127.0.0.1:8000)..." -ForegroundColor Yellow
    Write-Host "  API 文档: http://localhost:8000/docs" -ForegroundColor Gray

    # 后台启动后端
    $backendJob = Start-Job -Name "backend" -ScriptBlock {
        param($py, $root)
        Set-Location $root
        & $py -m backend.main
    } -ArgumentList $VenvPython, $ProjectRoot

    Write-Host "  后端启动中..." -ForegroundColor Gray
    Start-Sleep -Seconds 6

    Write-Host "[4/4] 启动前端开发服务器 (http://localhost:5173)..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  后端:  http://localhost:8000" -ForegroundColor White
    Write-Host "  前端:  http://localhost:5173" -ForegroundColor White
    Write-Host "  文档:  http://localhost:8000/docs" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""

    Set-Location "$ProjectRoot\frontend"
    npm run dev

    # 前端退出后，清理后端进程
    Write-Host "停止后端服务..." -ForegroundColor Yellow
    Stop-Job -Name "backend" -ErrorAction SilentlyContinue
    Remove-Job -Name "backend" -Force -ErrorAction SilentlyContinue
}
