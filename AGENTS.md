# AGENTS.md

本文档为 AI 编程助手在本项目中工作提供指导。

## 项目概述

基于 **xtquant** (迅投量化交易平台) 的股票自动交易系统，使用 **gRPC** 进行进程间通信，Web Dashboard 可视化。

> 详细架构规划见 [docs/PLAN.md](docs/PLAN.md)

## 平台约束

- **交易执行**: 仅 Windows（依赖 QMT/xtquant 客户端）
- **策略引擎**: 跨平台（macOS/Linux/Windows）
- **数据库**: PostgreSQL（Docker 部署）
- **Python**: 3.10+

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 PostgreSQL
docker compose -f docker/docker-compose.yml up -d

# 一键启动（Windows）
.\scripts\start.ps1

# 访问 Dashboard
# http://localhost:5173
```

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
│  │  - 策略调度        │  │  - 历史数据               │ │
│  │  - 信号生成        │  │  - 参数优化               │ │
│  │  - 风控检查        │  │  - 绩效指标               │ │
│  └──────────────────┘  └────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │  数据层 (SQLAlchemy + PostgreSQL)                 │ │
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

## 目录结构

```
backend/
├── api/              # FastAPI 服务 (Dashboard 后端)
│   ├── app.py         # 应用工厂 + 进程生命周期管理
│   ├── routes/        # 路由: dashboard/strategy/trade/backtest/settings
│   ├── websocket.py   # WebSocket 实时推送
│   └── models.py      # Pydantic 请求/响应模型
├── trade/            # 交易执行层
│   ├── base_executor.py  # TradeExecutor 抽象基类
│   ├── real_executor.py  # 真实交易 (xtquant)
│   ├── sim_executor.py   # 模拟交易 (虚拟账户)
│   ├── fees.py           # 费率/滑点计算
│   └── order_manager.py  # 订单状态跟踪
├── engine/           # 策略引擎 (跨平台)
│   ├── strategy_base.py     # 策略基类
│   ├── strategy_registry.py # 策略注册
│   ├── scheduler.py         # 策略调度 (交易日历)
│   ├── indicators.py        # 技术指标库
│   ├── risk_manager.py      # 风控 (仓位/资金/频率)
│   └── signal_bus.py        # 信号总线
├── backtest/         # 回测引擎
│   ├── engine.py          # 核心回测循环
│   ├── data_provider.py   # 数据源 (xtquant/akshare)
│   ├── metrics.py         # 绩效指标
│   ├── optimizer.py       # 网格搜索参数优化
│   └── reporter.py        # 回测报告生成
├── db/               # 数据持久层
│   ├── database.py        # SQLAlchemy engine + session
│   ├── models.py          # ORM 模型
│   ├── repository.py      # DAO 层
│   └── migrations/        # Alembic 迁移
├── grpc/             # gRPC 通信
│   ├── trade.proto        # 协议定义
│   ├── server.py          # 服务端 (Windows)
│   └── client.py          # 客户端 (跨平台)
├── core/             # 基础设施
│   ├── config.py          # 统一配置管理
│   ├── logging.py         # 日志
│   ├── trading_calendar.py # A股交易日历
│   └── exceptions.py      # 自定义异常
└── main.py           # 统一入口

frontend/            # React Dashboard
├── src/pages/       # Dashboard/Strategy/TradeHistory/Backtest/Settings
├── src/components/  # 通用组件
├── src/hooks/       # useWebSocket 等
└── src/api/         # API 调用层

config/
├── app.yaml         # 应用主配置
└── strategies/      # 策略配置文件

docker/
├── docker-compose.yml  # PostgreSQL + pgAdmin
└── init.sql            # 初始表结构

docs/                # 文档
└── PLAN.md          # 详细规划
```

## 命令

```bash
# 开发模式（前端热重载 + 后端热重载）
.\scripts\start.ps1

# 仅启动后端
python -m backend.main

# 仅启动 Trade Engine (Windows)
python -m backend.grpc.server

# 运行测试
pytest tests/ -v

# 数据库迁移
alembic upgrade head
```

## 配置

统一配置从 `config/app.yaml` 加载，策略配置在 `config/strategies/` 下。

```yaml
# config/app.yaml
app:
  host: 0.0.0.0
  port: 8000

database:
  url: postgresql+asyncpg://postgres:postgres@localhost:5432/xtquant

grpc:
  host: localhost
  port: 50051

trade:
  qmt_path: "YOUR_QMT_PATH"
  account_id: "YOUR_ACCOUNT_ID"
  mode: real  # real | sim

fee:
  commission_rate: 0.00025
  stamp_tax_rate: 0.001
  min_commission: 5.0

slippage:
  rate: 0.001
  mode: fixed_rate

trading_hours:
  start: "09:30"
  end: "14:55"
  cancel_unfilled_at: "14:50"
```

## 交易执行器统一接口

所有交易操作通过 `TradeExecutor` 抽象，策略引擎不感知底层：

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

## 策略开发规范

新增策略需继承 `StrategyBase`：

```python
class StrategyBase(ABC):
    """策略基类"""

    @abstractmethod
    async def on_quote(self, quote: Quote) -> Optional[Signal]:
        """行情回调，产生交易信号或 None"""
        ...

    @abstractmethod
    async def get_config_schema(self) -> dict:
        """返回策略可配置参数的 JSON Schema"""
        ...
```

## 费率计算

所有交易（真实和模拟）必须通过 `FeeCalculator` 计算费用：

- 佣金: 万 2.5，最低 5 元
- 印花税: 千 1（仅卖出）
- 过户费: 万 0.2
- 滑点: 千 1（按方向调整预期成交价）

## 代码规范

- 函数需有 docstring（Google 或 NumPy 风格）
- 变量/函数命名: PEP 8
- 类命名: PascalCase
- 异步优先: 网络 IO 使用 async/await
- 类型标注: 所有公开函数必须有完整类型标注
- 错误处理: 使用自定义异常类，禁止裸 `except`
- 日志: 使用 `core.logging` 统一日志器，不直接使用 `print`
- 配置: 不硬编码，必须从 `config/` 或数据库加载
- 测试: 关键路径必须覆盖

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + uvicorn |
| 数据库 ORM | SQLAlchemy 2.0 (async) + asyncpg |
| 迁移工具 | Alembic |
| gRPC | grpcio + protobuf |
| 交易 SDK | xtquant (QMT) |
| 行情备选 | akshare |
| 前端框架 | React 18 + TypeScript |
| UI 组件 | Ant Design 5 |
| 图表 | Recharts |
| 构建工具 | Vite 5 |
| 测试框架 | pytest + pytest-asyncio |
