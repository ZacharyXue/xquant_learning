# 项目重构规划

## 一、现状评估

### 已有的

| 模块 | 状态 | 说明 |
|------|------|------|
| gRPC 通信 | ✅ 可用 | proto 定义完整，server/client 均可工作 |
| Trader 封装 | ✅ 可用 | xtquant 下单/撤单/查持仓/资金完整 |
| bonus_stocks 策略 | ✅ 可用 | 红利ETF定投，RSI+MA乖离率+开盘变化率 |
| 日志系统 | ✅ 可用 | 按日滚动，控制台+文件双输出 |
| 前端框架 | ⚠️ 半成品 | React+AntD+FastAPI 架子在，但只做了回测展示 |
| 参数优化 | ⚠️ 能用 | 网格搜索回测参数，但依赖 mock 数据 |

### 核心缺陷

| 问题 | 严重程度 | 详情 |
|------|----------|------|
| 交易记录存储 | **高** | SQLite 单文件，无结构化 DB，无持久化保障 |
| 回测系统 | **高** | 依赖 mock 随机数据（MD5 seed），无真实数据源 |
| 启动方式 | **高** | 纯命令行 `python -m`，无可视化一键启动 |
| 可视化 | **高** | 前端仅展示回测结果，无实时交易/持仓/策略状态 |
| 费率/滑点 | **高** | 交易和回测中均未考虑佣金、印花税、滑点 |
| 交易与决策耦合 | 中 | 策略执行器直接调 gRPC buy/sell，未分离决策与执行 |
| 模拟交易 | 缺 | TradeExecutor 只能连真实 QMT，无模拟模式 |
| 配置分散 | 中 | yaml + json 多文件，无统一配置界面 |
| 测试覆盖 | 低 | 仅策略逻辑单测，无集成测试 |

---

## 二、目标架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Web Dashboard (浏览器)                     │
│               React + AntD, WebSocket 实时推送                │
└──────────────┬───────────────────────────────────────────────┘
               │ HTTP/WS
┌──────────────▼───────────────────────────────────────────────┐
│                Backend API Server (跨平台)                     │
│           FastAPI + SQLAlchemy + WebSocket                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  策略引擎 (Strategy Engine)                                │ │
│  │  - 策略注册与调度  - 信号生成  - 指标计算                   │ │
│  │  - 风控检查(仓位/资金)  - 费率计算                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  回测引擎 (Backtest Engine)                                │ │
│  │  - 真实数据源(xtquant/akshare)  - 参数遍历优化             │ │
│  │  - 绩效指标(夏普/回撤/胜率)                                │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  数据层 (Data Layer)                                       │ │
│  │  PostgreSQL: 交易记录/持仓/策略配置/回测结果/参数快照        │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────┬───────────────────────────────────────────────┘
               │ gRPC (可跨网络)
┌──────────────▼───────────────────────────────────────────────┐
│              Trade Engine (仅 Windows)                        │
│  ┌─────────────────────┐  ┌────────────────────────────────┐ │
│  │  真实交易 (Real)      │  │  模拟交易 (Sim)                 │ │
│  │  xtquant Trader     │  │  虚拟账户 + 实时行情撮合         │ │
│  │  佣金/印花税/滑点    │  │  佣金/印花税/滑点               │ │
│  └─────────────────────┘  └────────────────────────────────┘ │
│  通过 gRPC 接口统一暴露，策略引擎不感知底层是真实还是模拟        │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  行情中继 (Market Data Relay)                             │ │
│  │  xtquant subscribe → gRPC streaming → 策略引擎            │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **交易与决策分离**: 策略引擎在任意平台运行，通过 gRPC 连接 Windows 交易端
2. **执行器抽象**: `TradeExecutor` 统一接口，`RealTradeExecutor` 和 `SimTradeExecutor` 可互换
3. **费率全程计算**: 每笔交易（真实/模拟/回测）都计算佣金+印花税+过户费+滑点
4. **数据真实化**: 移除所有 mock 数据，回测使用 xtquant 或 akshare 真实历史数据
5. **一键启动**: Dashboard 后端管理子进程生命周期

---

## 三、模块设计

### 3.1 交易执行器抽象

```python
class TradeExecutor(ABC):
    """交易执行器统一接口，真实/模拟均实现此接口"""

    @abstractmethod
    async def initialize(self, config: dict) -> bool: ...

    @abstractmethod
    async def place_order(self, req: OrderRequest) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> CancelResult: ...

    @abstractmethod
    async def get_account(self) -> AccountInfo: ...

    @abstractmethod
    async def get_positions(self) -> list[Position]: ...

    @abstractmethod
    async def get_orders(self, status: str = None) -> list[Order]: ...

    @abstractmethod
    async def get_trades(self) -> list[Trade]: ...

    @abstractmethod
    async def subscribe_quotes(self, stock_codes: list[str]) -> AsyncIterator[Quote]: ...

    @abstractmethod
    async def close(self) -> None: ...
```

- **RealTradeExecutor**: 封装 xtquant，调用真实 QMT 下单
- **SimTradeExecutor**: 维护虚拟账户，按实时行情当前价成交，计算费率

### 3.2 费率与滑点模型

```python
@dataclass
class FeeConfig:
    commission_rate: float = 0.00025   # 佣金万2.5 (可配)
    stamp_tax_rate: float = 0.001      # 印花税千1 (仅卖出)
    transfer_fee_rate: float = 0.00002 # 过户费万0.2 (可配)
    min_commission: float = 5.0        # 最低佣金5元 (可配)

@dataclass
class SlippageConfig:
    rate: float = 0.001               # 滑点千1 (可配)
    mode: str = "fixed_rate"           # "fixed_rate" | "spread_based"

class FeeCalculator:
    def calc_trade_cost(self, price, volume, side) -> TradeCost:
        """计算单笔交易费用(佣金/印花税/过户费/总成本)"""
    def calc_slippage_price(self, price, side) -> float:
        """计算含滑点的预期成交价"""
    def calc_net_pnl(self, buy_cost, sell_cost) -> float:
        """计算扣除所有费用后的净损益"""
```

### 3.3 行情中继 (gRPC Streaming)

增强 gRPC 协议，新增双向流：

```protobuf
service TradeService {
    rpc PlaceOrder(OrderRequest) returns (OrderResponse);
    rpc CancelOrder(CancelRequest) returns (CancelResponse);
    rpc GetAccount(AccountRequest) returns (AccountResponse);
    rpc GetPositions(PositionsRequest) returns (PositionsResponse);
    rpc GetOrders(OrdersRequest) returns (OrdersResponse);
    rpc GetTrades(TradesRequest) returns (TradesResponse);
    rpc SubscribeMarketData(MarketDataRequest) returns (stream MarketDataTick);
    rpc Ping(PingRequest) returns (PingResponse);
}
```

Windows 端从 xtquant 订阅行情 → 通过 gRPC stream 推送给策略引擎。

### 3.4 PostgreSQL 数据模型

```
strategies          - 策略定义与配置
strategy_params     - 策略参数版本管理
trade_records       - 所有交易记录(真实+模拟)
positions           - 持仓快照
account_snapshots   - 账户资金快照
strategy_signals    - 策略信号日志
backtest_runs       - 回测运行记录
backtest_results    - 回测绩效指标
backtest_trades     - 回测交易明细
param_optimizations - 参数优化结果
market_data_cache   - 行情数据缓存
system_configs      - 系统配置(kv)
```

使用 SQLAlchemy 2.0 (async) + asyncpg + Alembic。

### 3.5 Web Dashboard 页面

| 页面 | 内容 |
|------|------|
| **总览面板** | 实时账户总资产/持仓/当日盈亏、策略运行状态、最近交易 |
| **策略管理** | 策略启停、参数调整、策略日志流、信号详情、一键启动/停止 |
| **交易记录** | 历史交易列表(筛选/排序/分页)、每笔含费率和滑点明细、导出 |
| **回测中心** | 策略选择+参数表单+一键运行、结果图表(权益曲线/回撤/指标)、参数优化对比 |
| **系统设置** | 费率配置、滑点配置、交易时段、模拟/真实切换 |

### 3.6 回测引擎重构

- **数据源**: 优先 xtquant 本地数据，跨平台时回退 akshare，彻底移除 random mock 数据
- **交互**: 前端表单 → API → 后台异步执行 → WebSocket 推送进度 → 结果图表渲染
- **参数调整**: 前端表单控件绑定策略参数，支持单次回测 / 网格遍历
- **绩效指标**: 收益率 / 年化收益 / 最大回撤 / 夏普比率 / 卡玛比率 / 胜率 / 盈亏比

---

## 四、实施阶段

### Phase 1: 基础设施 (地基)

- [ ] `docker/docker-compose.yml` + `init.sql`，部署 PostgreSQL
- [ ] 新目录结构创建
- [ ] SQLAlchemy ORM 模型 + Alembic 迁移配置
- [ ] 统一配置系统 `config/app.yaml` → `backend/core/config.py`
- [ ] FastAPI 基础框架 + WebSocket 基础设施
- [ ] 日志系统升级 `backend/core/logging.py`

### Phase 2: gRPC 协议重写

- [ ] 新 `trade.proto`（9个 RPC + server streaming）
- [ ] gRPC 服务端 `backend/grpc/server.py`（骨架，不含业务逻辑）
- [ ] gRPC 客户端 `backend/grpc/client.py`（含重连/心跳/超时）
- [ ] protobuf 代码生成脚本

### Phase 3: 交易执行层

- [ ] `TradeExecutor` 抽象基类
- [ ] `RealTradeExecutor`（封装 xtquant，复用现有 Trader 逻辑）
- [ ] `SimTradeExecutor`（虚拟账户 + 行情撮合 + 费率计算）
- [ ] `FeeCalculator` + `SlippageCalculator`
- [ ] `OrderManager`（订单状态跟踪、回调处理）
- [ ] gRPC 服务端注入 TradeExecutor 实现

### Phase 4: 策略引擎

- [ ] `StrategyBase` 策略基类
- [ ] `StrategyRegistry` 策略注册中心
- [ ] `StrategyScheduler`（交易日历 + cron 调度）
- [ ] 技术指标库 `backend/engine/indicators.py`
- [ ] `RiskManager`（仓位上限 / 资金管理 / 频率限制）
- [ ] `SignalBus` 信号总线
- [ ] bonus_stocks 策略迁移到新架构

### Phase 5: Dashboard 前端

- [ ] 总览面板页面（资产/持仓/策略状态卡）
- [ ] 策略管理页面（启停/参数/日志流）
- [ ] 交易记录页面（列表/筛选/详情/导出）
- [ ] 回测中心页面（表单/图表/对比）
- [ ] 系统设置页面（费率/滑点/切换模式）
- [ ] WebSocket 实时数据 Hook
- [ ] 一键启动/停止控制

### Phase 6: 回测重构 + 测试

- [ ] `DataProvider`（xtquant 主 / akshare 备）
- [ ] `BacktestEngine`（事件驱动回测循环）
- [ ] `MetricsCalculator`（绩效指标全套）
- [ ] `GridOptimizer`（网格搜索参数优化）
- [ ] 移除所有 mock 数据生成代码
- [ ] 集成测试 + 端到端测试

---

## 五、关键决策记录

| 决策项 | 结论 | 理由 |
|--------|------|------|
| 前端形态 | Web Dashboard | 已有 React+FastAPI 架子，浏览器即用 |
| 数据库 | PostgreSQL (Docker on Windows) | 持久化 + 复杂查询 + 数据结构化 |
| 模拟交易粒度 | 简化模拟 | 实时行情当前价成交 + 费率，满足策略验证需求 |
| gRPC 协议 | 完全重写 | 现有协议过于简单，需新增 streaming + 账户查询 |
| 代码策略 | 推倒重建 | 现有架构耦合度高，无法简单修补 |
| 启动方式 | 统一启动 | Dashboard 管理子进程生命周期 |
| 回测数据 | xtquant 主，akshare 备 | QMT 可用时用 xtquant，跨平台用 akshare |
| 参数优化 | 网格搜索 | 简单可靠，结果全面，便于前端可视化 |
| 跨平台 | 策略引擎独立，gRPC 连交易端 | 最大化灵活性 |
| MVP 范围 | 5页面全做，功能从简 | 先跑通完整链路 |
