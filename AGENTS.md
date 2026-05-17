# AGENTS.md

## 本文档目的

本文档是 **AI 编程助手（opencode）** 在本项目中的工作指南。它包含：

1. **本地环境信息** — Python 路径、虚拟环境、QMT 安装位置、数据库连接方式等，确保 AI 助手能直接执行命令和测试
2. **项目架构说明** — 模块划分、数据流、关键设计决策
3. **开发规范** — 代码风格、提交规则、测试要求
4. **常用命令** — 启动、测试、迁移等一键可执行的命令

> 关联文档：
> - [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 系统架构设计与实施计划
> - [docs/](docs/) — 后续设计文档存放目录

---

## 本地开发环境

以下为本机实际安装路径，AI 助手生成命令时直接使用这些路径，**不要用占位符替代**。

### Python 环境

| 项目 | 值 |
|------|-----|
| Python 版本 | 3.11.9 (64-bit) |
| Python 路径 | `F:\Codes\Python311-64\python.exe` |
| 虚拟环境 | `F:\Codes\xtquant_learning\.venv` |
| 虚拟环境 Python | `.venv\Scripts\python.exe` |
| 激活命令 | `.venv\Scripts\Activate.ps1` |

### QMT / xtquant

| 项目 | 值 |
|------|-----|
| QMT 安装路径 | `D:\国金证券QMT交易端` |
| xtquant SDK 路径 | `D:\国金证券QMT交易端\bin.x64\Lib\site-packages\xtquant` |
| xtquant .pth 文件 | `.venv\Lib\site-packages\xtquant.pth`（已配置 DLL 搜索路径） |
| 券商 | 国金证券 |
| 状态 | QMT 客户端运行中时可正常调用 xtdata / xttrader |

### 数据库

| 项目 | 值 |
|------|-----|
| 类型 | PostgreSQL 16 |
| 运行方式 | Docker Desktop (WSL2) |
| 容器名 | `xtquant_postgres` |
| 端口 | `5432` |
| 用户名/密码 | `postgres` / `postgres` |
| 数据库名 | `xtquant` |
| 数据目录 | `docker\pgdata\`（绑定挂载，删除镜像不丢数据） |
| 连接地址 | `postgresql+asyncpg://postgres:postgres@localhost:5432/xtquant` |

### Node.js / 前端

| 项目 | 值 |
|------|-----|
| Node.js | v22.14.0 |
| npm | 10.9.2 |
| 前端目录 | `frontend\` |
| 开发服务器 | `npm run dev`（端口 5173，API 代理到 8000） |
| 构建命令 | `npm run build`（tsc + vite build） |

### Docker

| 项目 | 值 |
|------|-----|
| 版本 | 29.4.3 |
| Compose 文件 | `docker\docker-compose.yml` |
| 数据卷 | `docker\pgdata\`（本地目录绑定挂载） |

---

## 项目概述

基于 **xtquant**（迅投量化交易平台）的股票自动交易系统。

核心特点：
- 交易与决策分离：策略引擎跨平台运行，通过 gRPC 连接 Windows 上的交易执行器
- 真实/模拟双模式：一键切换，统一接口，策略不感知底层
- 完整费率模型：佣金万2.5 + 印花税千1 + 过户费万0.2 + 滑点千1
- Web Dashboard：React + AntD 5 页面，实时数据推送

---

## 架构

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
│  │  数据层 (SQLAlchemy 2.0 async + PostgreSQL)       │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────────┘
                       │ gRPC (streaming)
┌──────────────────────▼───────────────────────────────┐
│           Trade Engine (仅 Windows)                   │
│  ┌────────────────────┐  ┌──────────────────────────┐ │
│  │  RealTradeExecutor  │  │  SimTradeExecutor        │ │
│  │  xtquant → QMT      │  │  虚拟账户 + 行情撮合      │ │
│  └────────────────────┘  └──────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │  行情中继 (xtquant subscribe → gRPC streaming)    │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 目录结构

```
xtquant_learning/
├── backend/
│   ├── api/              # FastAPI 服务 (Dashboard 后端)
│   │   ├── app.py         # 应用工厂 + 进程生命周期管理
│   │   ├── routes/        # 5 个路由模块: dashboard/strategy/trade/backtest/settings
│   │   ├── websocket.py   # WebSocket 实时推送
│   │   └── models.py      # Pydantic 请求/响应模型
│   ├── trade/            # 交易执行层
│   │   ├── base_executor.py  # TradeExecutor 抽象基类（10 个抽象方法）
│   │   ├── real_executor.py  # 真实交易（封装 xtquant，14:50 自动撤单）
│   │   ├── sim_executor.py   # 模拟交易（虚拟账户，按行情价成交）
│   │   ├── fees.py           # 费率计算（佣金/印花税/过户费/滑点）
│   │   └── order_manager.py  # 订单状态跟踪（pending→filled/cancelled）
│   ├── engine/           # 策略引擎（跨平台）
│   │   ├── strategy_base.py     # 策略基类（on_quote → Signal）
│   │   ├── strategy_registry.py # @register 装饰器自动注册
│   │   ├── bonus_stocks.py      # 红利ETF定投策略（RSI + MA乖离率）
│   │   ├── scheduler.py         # 策略调度器（交易日历 + cron）
│   │   ├── indicators.py        # 技术指标库（RSI/MA/MACD/波动率）
│   │   ├── risk_manager.py      # 风控（仓位/资金/频率上限）
│   │   └── signal_bus.py        # 信号总线（发布订阅 + 多策略合并）
│   ├── backtest/         # 回测引擎
│   │   ├── engine.py          # 核心事件驱动回测循环（含费率）
│   │   ├── data_provider.py   # 数据源（xtquant 主 / akshare 备，无 mock）
│   │   ├── metrics.py         # 绩效指标（夏普/回撤/卡玛/胜率/年化）
│   │   ├── optimizer.py       # 网格搜索参数优化
│   │   └── reporter.py        # Markdown 报告生成
│   ├── db/               # 数据持久层
│   │   ├── database.py        # SQLAlchemy 2.0 async engine + session
│   │   ├── models.py          # 8 张 ORM 模型表
│   │   ├── repository.py      # DAO 层（CRUD 封装）
│   │   └── migrations/        # Alembic 迁移（已部署到 PostgreSQL）
│   ├── grpc/             # gRPC 通信层
│   │   ├── trade.proto        # 协议定义（11 个 RPC + server streaming）
│   │   ├── trade_pb2.py       # 生成的 protobuf 消息
│   │   ├── trade_pb2_grpc.py  # 生成的 gRPC stub
│   │   ├── server.py          # gRPC 服务端（Windows，注入 TradeExecutor）
│   │   ├── client.py          # gRPC 客户端（跨平台异步客户端）
│   │   └── generate_grpc.py   # proto 代码生成脚本
│   ├── core/             # 基础设施
│   │   ├── config.py          # 统一配置管理（app.yaml + 环境变量）
│   │   ├── logging.py         # 结构化日志（按日滚动，控制台+文件）
│   │   ├── trading_calendar.py # A股交易日历（交易时段/定投日判断）
│   │   └── exceptions.py      # 自定义异常类（6 个层级）
│   └── main.py           # 统一入口（--trade / --full）
├── frontend/            # React Dashboard
│   └── src/
│       ├── pages/       # 5 个页面: Dashboard/Strategy/TradeHistory/Backtest/Settings
│       ├── hooks/       # useWebSocket（自动重连）
│       ├── api/         # 11 个 API 函数
│       └── types/       # TypeScript 类型定义
├── config/
│   ├── app.yaml         # 应用主配置（费率/滑点/交易时段/gRPC/数据库）
│   └── strategies/      # 策略配置文件目录
├── docker/
│   ├── docker-compose.yml  # PostgreSQL 16 + pgAdmin
│   ├── init.sql            # 8 张表 + 索引初始结构
│   └── pgdata/             # PostgreSQL 数据文件（绑定挂载，已 gitignore）
├── scripts/
│   ├── start.ps1            # Windows 一键启动（前端+后端+数据库检查）
│   └── setup_db.py          # 数据库初始化脚本
├── docs/                # 设计文档
│   └── ARCHITECTURE.md  # 系统架构设计文档
└── tests/               # 测试目录
```

---

## 常用命令

AI 助手执行以下命令时，**必须使用本机实际路径**，不要用 `python` 泛指：

### 启动服务

```powershell
# 1. 启动数据库（如未运行）
docker compose -f docker/docker-compose.yml up -d postgres

# 2. 启动后端 API 服务
.venv\Scripts\python.exe -m backend.main

# 3. 启动前端开发服务器（新终端）
cd frontend; npm run dev
# 前端访问: http://localhost:5173
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 开发命令

```powershell
# 运行 Python 脚本（务必使用 venv Python）
.venv\Scripts\python.exe -c "<code>"

# 安装依赖
.venv\Scripts\python.exe -m pip install <package>

# 重新生成 gRPC 代码（修改 trade.proto 后执行）
.venv\Scripts\python.exe -m grpc_tools.protoc --proto_path=backend/grpc --python_out=backend/grpc --grpc_python_out=backend/grpc backend/grpc/trade.proto
# 生成后需修复 import（将 trade_pb2_grpc.py 中的 "import trade_pb2" 改为 "from backend.grpc import trade_pb2"）

# 数据库迁移
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "描述"

# 运行测试
.venv\Scripts\python.exe -m pytest tests/ -v

# 前端构建检查
cd frontend; npm run build
```

### 数据库操作

```powershell
# 查看表结构
docker exec xtquant_postgres psql -U postgres -d xtquant -c "\dt"

# 进入 PostgreSQL shell
docker exec -it xtquant_postgres psql -U postgres -d xtquant

# 重启数据库
docker compose -f docker/docker-compose.yml restart postgres
```

---

## 代码规范

### 提交规则
- **每完成一个特性或修复，立即 commit**，commit message 使用 conventional commits 格式
- **不要自动 push**，由开发者手动 push
- 示例：`feat(phase3): trade execution layer` / `fix: frontend build TS errors`

### Python 代码风格
- 函数必须有 docstring（Google 风格，中文可接受）
- 变量/函数命名：PEP 8（snake_case）
- 类命名：PascalCase
- 异步优先：所有网络 IO 使用 async/await
- 类型标注：所有公开函数必须有完整类型标注
- 错误处理：使用 `backend.core.exceptions` 中的自定义异常，禁止裸 `except`
- 日志：统一使用 `from backend.core.logging import get_logger`，**禁止使用 print**
- 配置：不硬编码，必须从 `config/app.yaml` 或数据库加载
- 敏感信息：qmt_path / account_id 通过环境变量注入，不入库

### 策略开发规范

新增策略必须：
1. 继承 `StrategyBase`，实现 `on_quote(quote) -> Optional[Signal]`
2. 使用 `@register` 装饰器注册
3. 实现 `get_config_schema()` 返回 JSON Schema（供前端渲染配置表单）
4. 所有参数可配置，不硬编码

```python
@register
class MyStrategy(StrategyBase):
    name = "my_strategy"
    display_name = "我的策略"

    async def on_quote(self, quote: Quote) -> Optional[Signal]:
        # 计算指标 → 决策 → 返回 Signal 或 None
        ...

    def get_config_schema(self) -> dict:
        return {"type": "object", "properties": {...}}
```

---

## 交易执行器统一接口

策略引擎不感知底层是真实交易还是模拟交易，所有操作通过 `TradeExecutor` 抽象：

```python
class TradeExecutor(ABC):
    async def initialize(self, config: dict) -> bool: ...
    async def place_order(self, req: OrderRequest) -> OrderResult: ...
    async def cancel_order(self, order_id: str) -> CancelResult: ...
    async def get_account(self) -> AccountInfo: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_orders(self, status: str = None) -> list[Order]: ...
    async def get_trades(self) -> list[Trade]: ...
    async def subscribe_quotes(self, stock_codes: list[str]) -> AsyncIterator[Quote]: ...
    async def close(self) -> None: ...
```

实现类：
- **RealTradeExecutor** — 封装 xtquant，连接真实 QMT；14:50 自动撤单；导入失败时 `_XTQUANT_AVAILABLE=False`
- **SimTradeExecutor** — 虚拟账户 + 行情缓存撮合；完整费率计算；所有交易记录可查询

---

## 费率计算

所有交易（真实/模拟/回测）必须通过 `FeeCalculator` 计算：

| 费用项 | 费率 | 说明 |
|--------|------|------|
| 佣金 | 0.025%（万2.5） | 最低 5 元，可配置 |
| 印花税 | 0.1%（千1） | 仅卖出时收取 |
| 过户费 | 0.002%（万0.2） | 可配置 |
| 滑点 | 0.1%（千1） | 买入上浮、卖出下浮，可配置 |

`FeeCalculator.calc_slippage_price(price, side)` — 计算含滑点预期成交价
`FeeCalculator.calc_trade_cost(price, volume, side) -> TradeCost` — 返回费用明细

---

## 数据库表结构

8 张核心表（已通过 Alembic 部署到 PostgreSQL）：

| 表名 | 用途 |
|------|------|
| `strategies` | 策略定义与参数配置 |
| `strategy_signals` | 策略信号日志（含 RSI/MA/bias 等指标快照） |
| `trade_records` | 交易记录（含佣金/印花税/过户费/滑点明细） |
| `positions` | 持仓快照 |
| `account_snapshots` | 账户资金快照 |
| `backtest_runs` | 回测运行记录 |
| `backtest_results` | 回测绩效指标（夏普/回撤/卡玛/胜率） |
| `system_configs` | 系统配置 KV 存储 |

---

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI + uvicorn | 0.136.1 |
| 数据库 ORM | SQLAlchemy 2.0 (async) + asyncpg | 2.0.49 |
| 数据库迁移 | Alembic | 1.18.4 |
| gRPC | grpcio + protobuf | 1.80.0 |
| 交易 SDK | xtquant (QMT) | 250516.1.1 |
| 前端框架 | React + TypeScript | 18 |
| UI 组件 | Ant Design 5 | 5.15 |
| 图表 | Recharts | 3.8 |
| 构建工具 | Vite | 5.4 |
| 测试 | pytest + pytest-asyncio | 9.0 |
