#!/usr/bin/env bash
#
# xtquant trading system startup script (WSL2 / Linux)
#
# Usage:
#   ./scripts/start.sh              # Start Dashboard API + Frontend
#   ./scripts/start.sh --backend    # Backend API only
#   ./scripts/start.sh --frontend   # Frontend dev server only
#   ./scripts/start.sh --trade      # Trade Engine only (requires QMT)
#   ./scripts/start.sh --full       # Dashboard + Trade Engine (requires QMT)
#   ./scripts/start.sh --db          # Start PostgreSQL only
#
# Environment variables:
#   XTQUANT_QMT_PATH     QMT userdata_mini path
#   XTQUANT_ACCOUNT_ID   Trading account ID
#   XTQUANT_QMT_SDK      xtquant SDK path (optional, auto-detected)
#
set -euo pipefail

# ── Constants ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/.venv"

# ── Python detection ───────────────────────────────────
detect_python() {
    # 1. WSL2: use Windows venv Python
    local win_python="$VENV_DIR/Scripts/python.exe"
    if [[ -f "$win_python" ]]; then
        echo "$win_python"
        return
    fi

    # 2. Linux venv
    local lin_python="$VENV_DIR/bin/python3"
    if [[ -f "$lin_python" ]]; then
        echo "$lin_python"
        return
    fi

    # 3. System python3
    if command -v python3 &>/dev/null; then
        echo "python3"
        return
    fi

    echo ""
}

# ── QMT path detection ─────────────────────────────────
detect_qmt_path() {
    # 1. Environment variable
    if [[ -n "${XTQUANT_QMT_PATH:-}" ]] && [[ -d "$XTQUANT_QMT_PATH" ]]; then
        echo "$XTQUANT_QMT_PATH"
        return
    fi

    # 2. Known locations (Windows + WSL)
    local candidates=(
        "D:\\国金证券QMT交易端\\userdata_mini"
        "/mnt/d/国金证券QMT交易端/userdata_mini"
        "D:\\国金QMT交易端\\userdata_mini"
        "/mnt/d/国金QMT交易端/userdata_mini"
    )
    for p in "${candidates[@]}"; do
        if [[ -d "$p" ]]; then
            echo "$p"
            return
        fi
    done

    echo ""
}

# ── Parse args ─────────────────────────────────────────
MODE="dashboard"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend)  MODE="backend" ;;
        --frontend) MODE="frontend" ;;
        --trade)    MODE="trade" ;;
        --full)     MODE="full" ;;
        --db)       MODE="db" ;;
        --help|-h)
            echo "Usage: $0 [--backend|--frontend|--trade|--full|--db]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

PYTHON="$(detect_python)"
if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python not found" >&2
    echo "  Expected: $VENV_DIR/Scripts/python.exe (Windows) or $VENV_DIR/bin/python3 (Linux)" >&2
    exit 1
fi
echo "Python: $PYTHON"

QMT_PATH=""
if [[ "$MODE" == "trade" || "$MODE" == "full" ]]; then
    QMT_PATH="$(detect_qmt_path)"
    if [[ -n "$QMT_PATH" ]]; then
        export XTQUANT_QMT_PATH="$QMT_PATH"
        echo "QMT Path: $QMT_PATH"
    else
        echo "WARNING: QMT not found. Trade Engine may fail." >&2
    fi

    # Check Windows QMT process via interop
    if command -v powershell.exe &>/dev/null; then
        qmt_running="$(powershell.exe -Command "Get-Process -Name XtItClient,XtMiniQmt -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name" 2>/dev/null || true)"
        if [[ -z "$qmt_running" ]]; then
            echo "WARNING: QMT client does not appear to be running" >&2
        else
            echo "QMT client detected: $qmt_running"
        fi
    fi
fi

# ── Color output ────────────────────────────────────────
green()  { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
cyan()   { echo -e "\033[36m$1\033[0m"; }

echo "========================================"
cyan "  xtquant Trading System (WSL/Linux)"
echo "========================================"

# ── PostgreSQL ─────────────────────────────────────────
yellow "[1/3] PostgreSQL..."
if command -v docker &>/dev/null; then
    if docker ps --filter "name=xtquant_postgres" --format "{{.Names}}" 2>/dev/null | grep -q xtquant_postgres; then
        green "  PostgreSQL running"
    else
        docker compose -f "$PROJECT_ROOT/docker/docker-compose.yml" up -d postgres 2>/dev/null || true
        sleep 5
        green "  PostgreSQL started"
    fi
else
    echo "  WARNING: Docker not found, skip PostgreSQL check" >&2
fi

# ── Database init ──────────────────────────────────────
yellow "[2/3] Database..."
"$PYTHON" "$PROJECT_ROOT/scripts/setup_db.py" 2>/dev/null && green "  Database ready" || echo "  Database init skipped"

# ── Start services ─────────────────────────────────────
case "$MODE" in
    db)
        green "PostgreSQL only mode"
        exit 0
        ;;

    trade)
        yellow "[3/3] Trade Engine starting..."
        exec "$PYTHON" -m backend.main --trade
        ;;

    backend)
        yellow "[3/3] Backend API: http://127.0.0.1:8000"
        echo "  Docs: http://localhost:8000/docs"
        exec "$PYTHON" -m backend.main
        ;;

    frontend)
        yellow "[3/3] Frontend: http://localhost:5173"
        if [[ -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
            cd "$PROJECT_ROOT/frontend" && exec npm run dev
        else
            echo "ERROR: node_modules not found. Run: cd frontend && npm install" >&2
            exit 1
        fi
        ;;

    full)
        yellow "[3/3] Dashboard + Trade Engine starting..."
        exec "$PYTHON" -m backend.main --full
        ;;

    dashboard)
        yellow "[3/3] Dashboard + Frontend starting..."
        echo "  Backend:  http://localhost:8000"
        echo "  Frontend: http://localhost:5173"
        echo "  Docs:     http://localhost:8000/docs"
        echo ""

        # Start backend in background
        "$PYTHON" -m backend.main &
        BACKEND_PID=$!
        sleep 3

        cleanup() {
            echo ""
            yellow "Shutting down..."
            kill "$BACKEND_PID" 2>/dev/null || true
            wait "$BACKEND_PID" 2>/dev/null || true
            green "Backend stopped"
        }
        trap cleanup EXIT INT TERM

        # Start frontend in foreground
        if [[ -d "$PROJECT_ROOT/frontend/node_modules" ]]; then
            cd "$PROJECT_ROOT/frontend" && npm run dev
        else
            echo "ERROR: node_modules not found. Run: cd frontend && npm install" >&2
            cleanup
            exit 1
        fi
        ;;
esac
