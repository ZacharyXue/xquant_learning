# Trade Engine 设计文档

## 一、概述

Trade Engine 是 xtquant 量化交易系统的**交易执行核心**，负责：

- 连接 QMT 客户端获取实时行情
- 将行情分发到策略引擎生成交易信号
- 信号经风控检查后下单执行
- 监听订单回执并持久化到数据库
- 定时同步账户/持仓到 Dashboard

### 部署模式

**集成模式**（当前）：Trade Engine 与 Dashboard API 运行在同一 Python 进程，通过 `asyncio.Queue` 和直接方法调用通信，不使用 gRPC。gRPC 保留给未来分布式部署。

### 策略范围

初期仅支持 **bonus_stocks**（红利ETF定投）。策略按周三定投日 + RSI/乖离率条件在交易时段内生成买入信号。

---

## 二、架构

```
┌─── TradeEngine (Orchestrator) ───────────────────────────┐
│                                                           │
│  ┌─ TradeEngine ──── 主状态机 (TimeManager 内嵌) ────┐  │
│  │  PRE_MARKET → TRADING → PAUSED → POST_CLOSE       │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─ QuotePump ───────────────────────────────────────┐  │
│  │  xtdata.subscribe_whole_quote()                    │  │
│  │    → callback (同步线程)                            │  │
│  │    → asyncio.run_coroutine_threadsafe()            │  │
│  │    → asyncio.Queue[tick]                           │  │
│  │    → 限速/去重 → Quote dataclass → dispatch()      │  │
│  └───────────────────────────────────────────────────┘  │
│                          │ Quote                          │
│  ┌─ StrategyRunner ──────▼───────────────────────────┐  │
│  │  遍历所有启用的策略                                  │  │
│  │  BonusStocksStrategy.on_quote(quote) → Signal?     │  │
│  │  发布到 SignalBus                                  │  │
│  └───────────────────────────────────────────────────┘  │
│                          │ Signal                         │
│  ┌─ SignalBus + Merger ─▼────────────────────────────┐  │
│  │  asyncio.Queue[Signal]                             │  │
│  │  SignalMerger.merge() → 合并同股票多策略信号       │  │
│  └───────────────────────────────────────────────────┘  │
│                          │ 合并后 Signal                  │
│  ┌─ OrderBroker ─────────▼───────────────────────────┐  │
│  │  RiskManager.check_buy/sell()                      │  │
│  │  FeeCalculator.calc_trade_cost()                   │  │
│  │  executor.place_order()                            │  │
│  │  DB: 插入 trade_records                            │  │
│  │  WebSocket: 推送新订单                              │  │
│  └───────────────────────────────────────────────────┘  │
│                          │ seq / order_id                 │
│  ┌─ OrderTracker ────────▼───────────────────────────┐  │
│  │  监听 xtquant 回调 (on_stock_order/on_stock_trade)  │  │
│  │  桥接到 asyncio 事件循环                             │  │
│  │  超时兜底: 5s 无回调 → 主动 query                   │  │
│  │  更新 DB trade_records / positions                  │  │
│  │  WebSocket: 推送订单状态变更                         │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─ StateSync ───────────────────────────────────────┐  │
│  │  每 10s: account_snapshot → DB                      │  │
│  │  每 10s: positions → DB                             │  │
│  │  WebSocket: 推送账户/持仓                           │  │
│  └───────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

---

## 三、交易时段状态机

A 股交易时间：9:15 集合竞价 → 9:30 连续竞价 → 11:30 午休 → 13:00 下午 → 15:00 收盘。

```
                    ┌──────────────┐
          启动 ───→ │ INITIALIZING │ → 连接 QMT，加载策略，订阅行情
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │  PRE_MARKET  │  8:50~9:25：同步持仓，更新开盘价
                    └──────┬───────┘
                           │ 9:25 竞价结束
                           ▼
                    ┌──────────────┐
             ┌─────→│   TRADING    │  9:30~11:30 / 13:00~14:55
             │      │              │  QuotePump + StrategyRunner + OrderBroker
             │      └──────┬───────┘
             │             │ 11:30
             │      ┌──────▼───────┐
             │      │    PAUSED    │  午休：行情继续，停止下单
             │      └──────┬───────┘
             │             │ 13:00
             └─────────────┘
                           │ 14:50
                           ▼
                    ┌──────────────┐
                    │  PRE_CLOSE   │  撤单，禁止新开仓
                    └──────┬───────┘
                           │ 15:00
                           ▼
                    ┌──────────────┐
                    │  POST_CLOSE  │  最终快照，日终报告
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │    CLOSED    │  等待次日 8:50
                    └──────────────┘
```

| 时间 | 状态 | 动作 |
|------|------|------|
| 8:50 | `PRE_MARKET` | 连接 QMT，`subscribe_whole_quote`，同步持仓 |
| 9:25 | `PRE_MARKET` | 竞价结果出炉，更新开盘价 |
| 9:30 | `TRADING` | 启动 QuotePump + StrategyRunner + OrderBroker |
| 11:30 | `PAUSED` | 暂停信号消费，行情保持 |
| 13:00 | `TRADING` | 恢复信号消费 |
| 14:50 | `PRE_CLOSE` | `cancel_unfilled()` 撤所有未成订单，禁止新开仓 |
| 15:00 | `POST_CLOSE` | 最终 account_snapshot，日终数据入库 |
| 次日 8:50 | `PRE_MARKET` | 重新进入交易日流程 |

### 交易日判断

```python
from backend.core.trading_calendar import is_trading_time, is_weekday

# 交易日 = 周一到周五（暂不考虑节假日）
# 交易时段 = (9:30~11:30) 或 (13:00~15:00)
```

---

## 四、行情管线 (QuotePump)

### 跨线程桥接

xtquant 的 `subscribe_whole_quote` 回调在**同步线程**中执行。使用 `asyncio.run_coroutine_threadsafe` 将 tick 推入 `asyncio.Queue`：

```
同步线程 (xtquant)                asyncio 事件循环 (主)
     │                                    │
     │  _on_quote(data)                    │
     │    → MarketDataTick                  │
     │    → run_coroutine_threadsafe(      │
     │        quote_queue.put(tick),        │
     │        loop)                         │
     │                              QuotePump._pump()
     │                                → await quote_queue.get()
     │                                → 限速 (每 tick 间隔 ≥ 100ms)
     │                                → 去重 (相同 stock_code + time)
     │                                → 构造 Quote dataclass
     │                                → StrategyRunner.dispatch(quote)
```

### 限速策略

- 每个 quote 处理间隔 ≥ 100ms（可配）
- 去重：相同 stock_code + 相同 time 的 tick 跳过
- 单只股票最大处理频率：10 次/秒

---

## 五、信号到订单链路 (OrderBroker)

```
QuotePump.dispatch(quote)
  → for strategy in active_strategies:
        signal = await strategy.on_quote(quote)
        if signal and signal.side != "skip":
            signal_bus.publish(signal)
  → 本 tick 生成的所有 Signal 收集完毕
  → SignalMerger.merge(signals)        # 合并同股票多策略信号
  → for merged_signal in merged:
        ├─ side == "buy":
        │    risk_manager.check_buy(stock, vol, price, pos, cash, asset)
        │    → (True, "OK"): 继续
        │    → (False, reason): 记录 strategy_signal(reason=reject), 跳过
        │    fee = fee_calculator.calc_trade_cost(price, vol, "buy")
        │    response = await executor.place_order(request)
        │    → DB: insert trade_records (status=pending)
        │    → OrderTracker: 注册监听 seq
        │    → WebSocket: push "new_order" event
        │
        └─ side == "sell":
             risk_manager.check_sell(stock, vol, positions)
             → 同上流程
```

### 下单参数

- `order_type`: `STOCK_BUY`(23) / `STOCK_SELL`(24)
- `price_type`: 有指定价 → `FIX_PRICE`(11)，否则 → `LATEST_PRICE`(5)
- `strategy_name`: 策略标识，写入 QMT 备注字段

---

## 六、订单回执处理 (OrderTracker)

xtquant 异步下单流程：

```
executor.place_order()
  → trader.order_stock_async(...)  → 返回 async_seq (int)
  → 注册到 OrderTracker.pending_orders[seq]

on_stock_order(order) 回调:
  → asyncio.run_coroutine_threadsafe(tracker.handle_order(order), loop)
  → 更新 trade_records (status, filled_volume, filled_price)
  → if status == FILLED:
       更新 positions (avg_cost, volume, profit_loss)
       del pending_orders[order_id]

on_stock_trade(trade) 回调:
  → 记录成交明细到 trade_records
```

### 超时兜底

xtquant 回调可能丢失（网络/进程异常），需要主动轮询：

```
OrderTracker._timeout_loop() (每 5s 检查):
  for seq in pending_orders:
      if 距离下单 > 5s 且未收到任何回调:
          orders = executor.get_orders()  # 主动查询全部订单
          对比 pending_orders 中的状态
          更新变更的订单
```

### 订单状态映射

| xtconstant 常量 | 值 | 含义 |
|-----------------|-----|------|
| ORDER_UNREPORTED | 48 | 未报 |
| ORDER_WAIT_REPORTING | 49 | 待报 |
| ORDER_REPORTED | 50 | 已报 |
| ORDER_REPORTED_CANCEL | 51 | 已报待撤 |
| ORDER_PART_SUCC | 52 | 部成 |
| ORDER_SUCCEEDED | 53 | 已成 |
| ORDER_JUNK | 54 | 废单 |
| ORDER_PART_CANCEL | 55 | 部撤 |
| ORDER_CANCELED | 56 | 已撤 |
| ORDER_PART_CANCEL | 57 | 部撤 |

---

## 七、状态同步 (StateSync)

在 `TRADING` 和 `PRE_CLOSE` 状态下，每 10 秒执行：

```python
async def _sync_state(self):
    # 1. 账户快照
    account = await executor.get_account()
    db.execute(insert(AccountSnapshot(...)))

    # 2. 持仓快照
    positions = await executor.get_positions()
    for p in positions:
        db.execute(upsert(Position, ...))

    # 3. WebSocket 推送
    ws.broadcast({
        "type": "state_sync",
        "account": {...},
        "positions": [...]
    })
```

---

## 八、优雅关闭

### 关闭触发途径

1. **SIGINT** (Ctrl+C)
2. **POST /api/shutdown** (start.ps1 中 npm 退出后调用)
3. **QMT 断连** → `on_disconnected()` 回调 → 触发关闭

### 关闭流程

```
shutdown_event.set()
  → TradeEngine.close()
      → OrderBroker: 停止消费新信号
      → QuotePump: unsubscribe_whole_quote
      → StateSync: 最后一次同步
      → Redis/DB: 写入最终快照
      → executor.close()
  → Dashboard: uvicorn.should_exit = True
  → asyncio: 等待所有 task 完成
  → loop.close()
```

---

## 九、文件清单

| 文件 | 职责 | 类型 |
|------|------|------|
| `backend/trade/engine.py` | `TradeEngine` 主类，生命周期 + 状态机 | 新建 |
| `backend/trade/quote_pump.py` | `QuotePump`，行情订阅 + 限速去重 + 分发 | 新建 |
| `backend/trade/order_broker.py` | `OrderBroker`，信号→风控→下单 | 新建 |
| `backend/trade/order_tracker.py` | `OrderTracker`，回执监听 + 超时兜底 | 新建 |
| `backend/trade/state_sync.py` | `StateSync`，定时同步 DB + WS 推送 | 新建 |
| `backend/main.py` | 接入 TradeEngine | 修改 |
| `backend/core/shutdown.py` | `ShutdownManager`，全局关闭信号 | 新建 |
| `backend/api/websocket.py` | 增加 trade 事件广播 | 修改 |
| `scripts/start.ps1` | 优雅退出 + 目录恢复 | 修改 |

---

## 十、策略引擎交互

### on_quote 调用时机

策略的 `on_quote(quote)` 在每个行情节拍被调用一次。策略内部自行判断是否应该生成信号：

```python
class BonusStocksStrategy(StrategyBase):
    async def on_quote(self, quote: Quote) -> Optional[Signal]:
        now = datetime.now()
        if not is_trading_time(now):
            return None       # 非交易时段
        if not is_investment_day(now, ["Wednesday"]):
            return None       # 非定投日

        # 更新价格历史 + 计算指标
        indicators = self._calc_indicators(...)
        volume = self._decide_volume(indicators)

        if volume > 0:
            return Signal(side="buy", volume=volume, ...)
        return None
```

### 防重复下单

策略每 tick 只发出一次判断，订单由 OrderBroker 处理。同一策略同一天内同一股票不会重复下单（策略内部用 `_last_trade_date` 控制）。
