# Windows 一键启动脚本
# Usage: .\scripts\start.ps1
#        .\scripts\start.ps1 --trade   # 仅启动 Trade Engine
#        .\scripts\start.ps1 --full    # Dashboard + Trade Engine

param(
    [switch]$Trade,
    [switch]$Full
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot

# 激活虚拟环境
$VenvPath = Join-Path $ProjectRoot ".venv"
if (Test-Path $VenvPath) {
    & "$VenvPath\Scripts\Activate.ps1"
}

# 检查 PostgreSQL
$pgRunning = docker ps --filter "name=xtquant_postgres" --format "{{.Names}}"
if (-not $pgRunning) {
    Write-Host "Starting PostgreSQL..." -ForegroundColor Cyan
    docker compose -f "$ProjectRoot\docker\docker-compose.yml" up -d postgres
    Start-Sleep -Seconds 5
}

# 初始化数据库
Write-Host "Initializing database..." -ForegroundColor Cyan
python "$ProjectRoot\scripts\setup_db.py"

# 启动服务
if ($Trade) {
    Write-Host "Starting Trade Engine..." -ForegroundColor Green
    python -m backend.main --trade
} elseif ($Full) {
    Write-Host "Starting Full System..." -ForegroundColor Green
    python -m backend.main --full
} else {
    Write-Host "Starting Dashboard..." -ForegroundColor Green
    python -m backend.main
}
