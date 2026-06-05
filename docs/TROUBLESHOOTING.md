# 故障复盘与修复日志

本文档记录项目重构及实盘调试过程中遇到的问题、根因和修复方案，便于后续排查。

---

## 一、架构精简 (2026-06-04)

### 背景

原有项目 ~100 文件，企业级架构（FastAPI + gRPC + React + PostgreSQL + 3 种优化器），但仅有 1 个策略、未验证实盘。

### 精简内容

| 删除 | 替代 |
|------|------|
| FastAPI + WebSocket + React SPA | CLI 脚本 |
| gRPC（11 个 RPC） | 不需要（单机运行） |
| PostgreSQL + Docker + Alembic | SQLite（stdlib sqlite3） |
| 3 种回测优化器 | 网格搜索（GridOptimizer） |
| WalkForward 验证 | 已移除 |
| 交易引擎状态机（7 状态） | 简化异步循环 |

### 保留的核心链路

```
QuotePump → Strategy.on_quote(quote) → Signal → Broker → Executor
```

### 最终结构：23 个源文件，60 个测试

```
engine/      strategy_base, strategy_registry, indicators
trade/       fees, quote_pump, sim_executor, real_executor, broker
backtest/    engine, data_provider, metrics, optimizer, baseline
db/          database, schema, queries
strategies/  bonus_stocks, test_trade
scripts/     manage, run_backtest, run_sim, run_real, show_trades
```

---

## 二、实盘交易调试 (2026-06-05 ~ 2026-06-06)

### 需求

买入 520990.SH × 400 股，现价成交，复用现有交易链路（QuotePump → Broker → RealExecutor），仅替换策略部分。

### 新增文件

| 文件 | 说明 |
|------|------|
| `strategies/test_trade.py` | 一次性买入策略，首次收到行情即下单，之后 `_executed=True` 不再重复 |
| `scripts/_trade.bat` | Windows 端一键启动脚本，含诊断输出 |

---

### Bug #1: YAML 反斜杠 → Unicode 转义

**现象：** 运行 `run_real.py` 时报 `yaml.scanner.ScannerError: expected escape sequence of 4 hexadecimal numbers, but found 's'`

**根因：** `config.yaml` 中：
```yaml
qmt_path: "D:\\国金证券QMT交易端\\userdata_mini"
```
YAML 将 `\\u` 先解为 `\u`，再触发 Unicode 转义解析，`\us` 不是合法 Unicode。

**修复：** 改用正斜杠，Python/Windows 均兼容：
```yaml
qmt_path: "D:/国金证券QMT交易端/userdata_mini"
```

**文件：** `config.yaml:7`

---

### Bug #2: Python 文件编码

**现象：** `UnicodeDecodeError: 'gbk' codec can't decode byte 0xaf`

**根因：** Windows Python 默认 GBK 编码，`config.yaml` 含中文字符（UTF-8），`open()` 未指定 `encoding="utf-8"`。

**修复：**
```python
with open(path, encoding="utf-8") as f:
```
**文件：** `scripts/run_real.py:39`

---

### Bug #3: xtquant 导入路径丢失

**现象：** `ModuleNotFoundError: No module named 'xtquant'`

**根因：** 虚拟环境 `.pth` 文件仅设置了 DLL 搜索路径：
```python
import os; os.environ.setdefault("PATH", r"D:\国金证券QMT交易端\bin.x64;...")
```
未将 xtquant 包目录加入 `sys.path`。架构精简时删除了原始的 `backend/core/xtquant_setup.py`。

**修复：**
1. 在 `run_real.py` 启动时主动注入路径：
```python
sys.path.insert(0, r"D:\国金证券QMT交易端\bin.x64\Lib\site-packages")
os.environ.setdefault("PATH", r"D:\国金证券QMT交易端\bin.x64;" + ...)
```
2. 修复 `.pth` 文件，添加包路径行：
```
D:\国金证券QMT交易端\bin.x64\Lib\site-packages
import os; os.environ.setdefault(...)
```

**文件：** `scripts/run_real.py:14-18`, `.venv/Lib/site-packages/xtquant.pth`

---

### Bug #4: QuotePump 用错 API — 关键 Bug

**现象：** 模拟连接成功但始终未收到行情回调，策略从未触发。

**根因：** `trade/quote_pump.py` 中使用了错误的 xtquant 订阅 API：

```python
# 错误：count=1 表示只取一条历史数据后停止，不会持续推送
xtdata.subscribe_quote(code, period='1d', count=1, callback=self._on_tick)
```

- `subscribe_quote(period='1d')` 订阅的是**日线聚合数据**，不是实时 tick
- `count=1` 表示只取 1 条就停止，不是流式订阅
- 交易时段内不会触发回调

**正确用法：**
```python
# subscribe_whole_quote: 全行情流式推送，每个 tick 都回调
xtdata.subscribe_whole_quote(list(stock_codes), callback=self._on_tick)
```

**文件：** `trade/quote_pump.py:15`

---

### Bug #5: 缺少诊断输出

**现象：** cmd 窗口弹出后立即关闭，无法判断是连接失败、行情未到还是策略未触发。

**修复：** `run_real.py` 增加逐步骤诊断输出：
- 打印 QMT 路径和账户
- 验证 xtquant 可导入
- 连接成功/失败明确提示
- 前 3 笔行情打印详情
- 30 秒无行情时警告"Is the market open?"
- 失败时 `input("Press Enter to close...")` 保持窗口打开

**文件：** `scripts/run_real.py:43-130`

---

## 三、环境注意事项

### WSL2 → Windows 调用限制

1. 无法从 WSL2 直接 import xtquant（C 扩展 DLL 加载限制）
2. `cmd.exe /c start ""` 从 WSL2 调用时权限受限
3. 推荐：在 Windows 端双击 `_trade.bat` 或直接 cd 到目录执行

### xtquant SDK 配置

| 项 | 路径 |
|----|------|
| QMT 安装 | `D:\国金证券QMT交易端` |
| SDK 路径 | `D:\国金证券QMT交易端\bin.x64\Lib\site-packages` |
| DLL 路径 | `D:\国金证券QMT交易端\bin.x64` |
| 交易目录 | `D:\国金证券QMT交易端\userdata_mini` |
| 账号 | `8884731549` |

### 实盘交易检查清单

- [ ] QMT 客户端已打开并登录
- [ ] `config.yaml` 中 `qmt_path` 和 `account_id` 正确
- [ ] xtquant 可在 venv 中 import
- [ ] 策略已在 DB 注册且启用（`manage.py --list`）
- [ ] 交易时段（9:30-11:30, 13:00-14:57）
- [ ] 标的代码格式正确（`520990.SH`）
- [ ] 盘后执行 `show_trades.py --today` 核对

---

## 三、代码审计：对比 xtquant SDK 源码 (2026-06-06)

### 审计来源

- `ai4trade/XtQuant` — xtquant SDK 官方封装源码
- `liqimore/quant-qmt-proxy` — 成熟的生产级 QMT 代理项目

### Bug #6: `order_type=0` — 下单类型参数错误

**严重程度：Critical**

**现象：** `trader.order_stock(..., order_type=0)` 传入无效值。

**根因：** xtquant SDK 中 `order_type` 必须使用 `xtconstant` 定义的常量：
- `STOCK_BUY = 23`
- `STOCK_SELL = 24`

传入 `0` 不是合法值，订单会被 QMT 忽略或返回错误。

**修复：** `real_executor.py` 中：
```python
from xtquant.xtconstant import STOCK_BUY, STOCK_SELL
order_type = STOCK_BUY if side == "buy" else STOCK_SELL
```

**文件：** `trade/real_executor.py:95-96`

---

### Bug #7: 缺少 `xtdata.run()` — 行情回调不触发

**严重程度：Critical**

**现象：** `subscribe_whole_quote` 注册了回调但从未被执行。

**根因：** xtquant SDK 要求调用 `xtdata.run()` 启动事件循环（阻塞循环），这样才能驱动回调执行。`quant-qmt-proxy` 在守护线程中调用 `xtdata.run()`，`ai4trade/XtQuant` 也有同样的 `run()` 函数。

**修复：** 在 `quote_pump.py` 和 `real_executor.py` 中添加 `ensure_xtdata_runtime()`，在守护线程中启动 `xtdata.run()`：
```python
threading.Thread(target=xtdata.run, daemon=True).start()
```
幂等设计——整个进程只启动一次。

**文件：** `trade/quote_pump.py:18-26`, `trade/real_executor.py:19-26`

---

### Bug #8: 缺少 `trader.register_callback()` — 无订单状态回调

**严重程度：Critical**

**现象：** 下单后无法获知订单是否成交、拒绝或部分成交。

**根因：** `XtQuantTrader` 要求在 `start()` 之前调用 `register_callback(callback_instance)` 注册回调处理器。回调负责接收：
- `on_stock_order` — 订单状态更新
- `on_stock_trade` — 成交回报
- `on_order_error` — 订单被拒
- `on_cancel_error` — 撤单被拒

两个参考项目均实现了完整的回调桥接。

**修复：** 新增 `_TraderCallback` 类，在 `initialize()` 中按正确顺序调用：
```
1. register_callback(callback)
2. start()
3. connect()
4. subscribe(account)
```

**文件：** `trade/real_executor.py:29-66`

---

### Bug #9: `StockAccount` 缺少 `account_type` 参数

**严重程度：Important**

**现象：** 账户订阅可能不完整。

**根因：** `StockAccount(account_id, account_type)` 需要两个参数，`account_type` 从 `xtconstant` 获取：
- `ACCOUNT_TYPE_STOCK = 2` — 股票账户

**修复：**
```python
from xtquant.xtconstant import ACCOUNT_TYPE_STOCK
StockAccount(account_id, ACCOUNT_TYPE_STOCK)
```

**文件：** `trade/real_executor.py:89`

---

### Bug #10: 下单缺少 `price_type` 参数

**严重程度：Important**

**现象：** `order_stock()` 缺少 `price_type` 参数（限价/市价/最新价等）。

**根因：** xtquant SDK `order_stock()` 需要 `price_type` 参数指定价格类型：
- `FIX_PRICE = 11` — 限价单
- `LATEST_PRICE = 5` — 最新价（近似市价）
- `MARKET_SH_CONVERT_5_CANCEL = 42` — 上海最优五档即时成交剩余撤销

**修复：**
```python
from xtquant.xtconstant import FIX_PRICE
price_type = FIX_PRICE if price > 0 else 5
```

**文件：** `trade/real_executor.py:99`

---

### Bug #11: `subscribe_whole_quote` 返回值未保存

**严重程度：Minor**

**现象：** 无法取消订阅，资源泄漏。

**根因：** `subscribe_whole_quote` 返回 `seq` 序列号，需要保存以便后续调用 `unsubscribe_quote(seq)`。

**修复：** `quote_pump.py` 保存 `self._sub_seq`，在 `stop()` 中调用 `xtdata.unsubscribe_quote(self._sub_seq)`。

**文件：** `trade/quote_pump.py:81-87`

---

### xtquant SDK 正确调用链总结

**行情订阅：**
```
ensure_xtdata_runtime()          # 守护线程中启动 xtdata.run()
  ↓
xtdata.subscribe_whole_quote([codes], callback=on_tick)
  → 返回 seq → 保存用于 unsubscribe
  ↓
on_tick(data)  ← C++ 线程回调 (每个 tick)
  ↓
stop() → xtdata.unsubscribe_quote(seq)
```

**交易下单：**
```
trader = XtQuantTrader(qmt_path, session_id)
trader.register_callback(callback)    # 必须在 start() 之前
trader.start()
trader.connect() == 0                # 返回 0 表示成功
trader.subscribe(StockAccount(id, ACCOUNT_TYPE_STOCK))
  ↓
trader.order_stock(
    account, stock_code,
    order_type=STOCK_BUY|STOCK_SELL,  # 23 or 24
    order_volume=shares,
    price_type=FIX_PRICE|5,           # 11 or 5
    price=price,
    strategy_name="...",
    order_remark="..."
) → 返回 order_id (>0) 或 -1 (失败)
  ↓
callback.on_stock_order(order)       # 状态更新
callback.on_stock_trade(trade)       # 成交回报
callback.on_order_error(error)       # 订单被拒
```

