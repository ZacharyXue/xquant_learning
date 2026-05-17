# xtquant 量化交易系统

基于 **xtquant**（迅投量化交易平台）的股票自动交易系统。交易与决策分离，Web Dashboard 可视化，支持真实/模拟双模式切换。

---

## 当前功能

| 模块 | 功能 | 状态 |
|------|------|------|
| 交易执行 | 真实交易 (xtquant/QMT) + 模拟交易 (虚拟账户) | ✅ |
| 费率模型 | 佣金万2.5 + 印花税千1 + 过户费万0.2 + 滑点千1 | ✅ |
| 策略引擎 | bonus_stocks 红利ETF定投 (RSI + MA乖离率 + 开盘跳空) | ✅ |
| 风控 | 仓位上限 / 资金管理 / 下单频率限制 | ✅ |
| 回测引擎 | xtquant 真实数据 + 网格搜索参数优化 + 绩效指标 | ✅ |
| 数据持久化 | PostgreSQL 16 (8 张表，含交易/持仓/信号/回测) | ✅ |
| Web Dashboard | 总览 / 策略管理 / 交易记录 / 回测中心 / 系统设置 | ✅ |
| gRPC 通信 | 11 个 RPC + 行情 streaming，跨平台策略引擎 | ✅ |

---

## 系统架构

```
┌──────────────────────────────────────────────────────┐
│              Web Dashboard (React + AntD)             │
│               :5173  ← Vite dev server                │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼───────────────────────────────┐
│           Backend API Server (FastAPI :8000)          │
│  ┌──────────────────┐  ┌────────────────────────────┐ │
│  │  策略引擎          │  │  回测引擎                  │ │
│  │  - 策略调度        │  │  - 历史数据(xtquant)      │ │
│  │  - 信号生成        │  │  - 参数优化(网格搜索)     │ │
│  │  - 风控检查        │  │  - 绩效指标(夏普/回撤)    │ │
│  └──────────────────┘  └────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │  数据层 (SQLAlchemy 2.0 + PostgreSQL)             │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────────┘
                       │ gRPC (streaming)
┌──────────────────────▼───────────────────────────────┐
│           Trade Engine (仅 Windows)                   │
│  ┌────────────────────┐  ┌──────────────────────────┐ │
│  │  RealTradeExecutor  │  │  SimTradeExecutor        │ │
│  │  xtquant → QMT      │  │  虚拟账户 + 行情撮合      │ │
│  └────────────────────┘  └──────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 启动方式

### 前置条件

- Python 3.11 (64-bit)
- Docker Desktop（运行 PostgreSQL）
- Node.js v22+（前端开发）
- QMT 客户端（仅真实交易需要，模拟交易不需要）

### 一键启动（Windows）

```powershell
# 在项目根目录执行
.\scripts\start.ps1
```

此脚本会：
1. 检查并启动 PostgreSQL（Docker）
2. 初始化数据库表结构
3. 启动 FastAPI 后端（端口 8000）
4. 启动前端开发服务器（端口 5173）

### 分步启动

```powershell
# 1. 启动 PostgreSQL
docker compose -f docker/docker-compose.yml up -d postgres

# 2. 启动后端（终端 1）
.venv\Scripts\python.exe -m backend.main

# 3. 启动前端（终端 2）
cd frontend
npm run dev
```

访问：
- Dashboard: http://localhost:5173
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health

### 仅启动 Trade Engine（Windows 真实交易）

```powershell
.venv\Scripts\python.exe -m backend.main --trade
```

### 完整启动（Dashboard + Trade Engine）

```powershell
.venv\Scripts\python.exe -m backend.main --full
```

---

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI + uvicorn | 0.136 |
| 数据库 ORM | SQLAlchemy 2.0 (async) + asyncpg | 2.0.49 |
| 迁移工具 | Alembic | 1.18 |
| gRPC | grpcio + protobuf | 1.80 |
| 交易 SDK | xtquant (QMT) | 250516 |
| 前端框架 | React + TypeScript | 18 |
| UI 组件 | Ant Design 5 | 5.15 |
| 图表 | Recharts | 3.8 |
| 构建工具 | Vite | 5.4 |

---

## 数据库

8 张核心表（PostgreSQL 16）：

| 表名 | 用途 |
|------|------|
| `strategies` | 策略定义与参数 |
| `strategy_signals` | 策略信号日志 |
| `trade_records` | 交易记录（含费率明细） |
| `positions` | 持仓快照 |
| `account_snapshots` | 账户资金快照 |
| `backtest_runs` | 回测运行记录 |
| `backtest_results` | 回测绩效指标 |
| `system_configs` | 系统配置 KV |

数据持久化到 `docker/pgdata/` 目录，删除 Docker 镜像不丢数据。

---

## 费率模型

所有交易（真实/模拟/回测）均计算完整费用：

| 费用项 | 费率 | 说明 |
|--------|------|------|
| 佣金 | 0.025%（万2.5） | 最低 5 元 |
| 印花税 | 0.1%（千1） | 仅卖出 |
| 过户费 | 0.002%（万0.2） | - |
| 滑点 | 0.1%（千1） | 买入上浮、卖出下浮 |

可在 Dashboard → 设置中实时调整。

---

## 模拟交易

无需 QMT 客户端即可完整验证策略逻辑：

1. Dashboard → 设置 → 切换为"模拟交易"
2. 策略引擎正常产生信号
3. SimTradeExecutor 按当前价成交，计算全部费用
4. 持仓/资金/交易记录全部写入数据库

---

## 相关文档

- [AGENTS.md](AGENTS.md) — AI 编程助手工作指南（环境信息、常用命令、开发规范）
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统架构设计与实施计划
