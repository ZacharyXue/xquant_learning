# xtquant 量化交易系统

基于 **xtquant**（迅投量化交易平台）的股票自动交易系统。交易与决策分离，Web Dashboard 可视化，支持真实/模拟双模式切换。

> 详细架构设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，开发规范见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)。

---

## 功能概览

| 模块 | 功能 |
|------|------|
| 交易执行 | 真实交易 (xtquant/QMT) + 模拟交易 (虚拟账户)，动态切换，完整费率模型 |
| 策略引擎 | bonus_stocks 红利ETF定投 (RSI + MA乖离率 + 开盘跳空)，`@register` 装饰器注册 |
| 风控 | 仓位上限 / 资金管理 / 止盈止损 / 下单频率限制 |
| 回测引擎 | xtquant 真实数据 + 网格/随机/Optuna 优化 + 滚动前进验证 + DCA 基准对比 |
| 数据持久化 | PostgreSQL 16，8 张核心表（含交易/持仓/信号/回测/配置） |
| Web Dashboard | 总览 / 策略管理 / 交易记录 / 回测中心 / 系统设置 |
| gRPC 通信 | 11 个 RPC + 行情 streaming，跨平台策略引擎 |

---

## 快速启动

### 前置条件

- Python 3.11 (64-bit) + Docker Desktop（PostgreSQL）+ Node.js v22+（前端）
- QMT 客户端（仅真实交易需要）

### 一键启动（Windows）

```powershell
.\scripts\start.ps1          # Dashboard（后端 + 前端）
.\scripts\start.ps1 --Full   # Dashboard + Trade Engine（需 QMT）
```

WSL2 一键启动：
```bash
./scripts/start.sh
```

### 分步启动

```powershell
# 1. 启动 PostgreSQL
docker compose -f docker/docker-compose.yml up -d postgres

# 2. 启动后端
.venv\Scripts\python.exe -m backend.main

# 3. 启动前端
cd frontend && npm run dev
```

访问 Dashboard: `http://localhost:5173` | API 文档: `http://localhost:8000/docs`

---

## 费率模型

所有交易（真实/模拟/回测）均计算完整费用：佣金万2.5 + 印花税千1（仅卖出）+ 过户费万0.2 + 滑点千1。可在 Dashboard → 设置中实时调整。

---

## 数据持久化

8 张核心表（PostgreSQL 16），数据存储在 `docker/pgdata/`，删除 Docker 镜像不丢失。

> 完整表结构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Alembic |
| 交易 SDK | xtquant (QMT) |
| gRPC | grpcio + protobuf |
| 前端 | React 18 + TypeScript + Ant Design 5 + Recharts + Vite |
| 数据库 | PostgreSQL 16 + asyncpg |
| 测试 | pytest + pytest-asyncio |

---

## 文档

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统架构、数据库表结构、设计决策
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — 开发规范、测试纪律、策略开发指南
- [docs/trade_engine.md](docs/trade_engine.md) — 交易引擎架构设计
- [AGENTS.md](AGENTS.md) — AI 编程助手工作指南
