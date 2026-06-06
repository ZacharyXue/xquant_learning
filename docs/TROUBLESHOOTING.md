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

### 审计方法

逐行读取 `.venv` 中 xtquant SDK 源码并对比当前实现：
| SDK 文件 | 行数 | 作用 |
|----------|------|------|
| `xtconstant.py` | 196 | 常量定义（order_type, price_type, account_type, market_type, order_status） |
| `xttype.py` | 361 | 数据结构（StockAccount, XtOrder, XtTrade, XtPosition, XtOrderError 等） |
| `xttrader.py` | 1137 | 交易 SDK（XtQuantTrader, 连接/报单/撤单/回调） |
| `xtdata.py` | 1522 | 行情 SDK（subscribe, get_kline, xtdata.run 等） |

也参考了 `ai4trade/XtQuant` 和 `liqimore/quant-qmt-proxy` 的调用模式。

### 已验证的 SDK 常量（xtconstant.py）

| 常量 | 行号 | 值 | 说明 |
|------|------|-----|------|
| `STOCK_BUY` | 77 | 23 | 股票买入 |
| `STOCK_SELL` | 78 | 24 | 股票卖出 |
| `SECURITY_ACCOUNT` | 15 | 2 | 股票账户类型 |
| `LATEST_PRICE` | 117 | 5 | 最新价 |
| `FIX_PRICE` | 119 | 11 | 限价/指定价 |
| `SH_MARKET` | 140 | 0 | 上海市场 |
| `SZ_MARKET` | 142 | 1 | 深圳市场 |
| `ORDER_SUCCEEDED` | 165 | 56 | 已成 |
| `ORDER_JUNK` | 167 | 57 | 废单 |

### 已验证的 SDK 函数签名

**xttrader.py:**
| 函数 | 行号 | 签名 |
|------|------|------|
| `register_callback` | 340 | `(self, callback: XtQuantTraderCallback)` |
| `start` | 343 | `(self)` — init + start async_client, 创建线程池 |
| `connect` | 358 | `(self) -> int` — 返回 0 表示成功 |
| `subscribe` | 379 | `(self, account: StockAccount)` |
| `order_stock` | 429 | `(self, account, stock_code, order_type, order_volume, price_type, price, strategy_name='', order_remark='') -> int` — 返回 `order_id`（>0 成功，-1 失败） |

**xttype.py:**
| 类/函数 | 行号 | 签名 |
|---------|------|------|
| `StockAccount.__init__` | 22 | `(self, account_id: str, account_type: str = 'STOCK')` — **默认即股票账户** |

**xtdata.py:**
| 函数 | 行号 | 签名 |
|------|------|------|
| `subscribe_whole_quote` | 747 | `(code_list, callback=None) -> int` — 回调格式: `{stock_code: {...fields...}}` |
| `subscribe_quote` | 709 | `(stock_code, period='1d', start_time='', end_time='', count=0, callback=None) -> int` |
| `unsubscribe_quote` | 763 | `(seq: int)` |
| `run` | 772 | `()` — 阻塞线程接收行情回调，每 3s 检查连接 |
| `get_full_tick` | 684 | `(code_list) -> dict` |

---

### Bug #6: `order_type=0` — 下单类型参数错误

**严重程度：Critical**

**源码验证：** `xtconstant.py:77-78` 定义 `STOCK_BUY=23, STOCK_SELL=24`。`xttrader.py:429-459` 的 `order_stock` 直接传递 `order_type` 到 C++ 客户端，无默认值。传入 `0` 不是合法值。

**修复：**
```python
from xtquant.xtconstant import STOCK_BUY, STOCK_SELL
order_type = STOCK_BUY if side == "buy" else STOCK_SELL
```
**文件：** `trade/real_executor.py:93`

---

### Bug #7: 缺少 `xtdata.run()` — 行情回调不触发

**严重程度：Critical**

**源码验证：** `xtdata.py:772-781` — `run()` 的注释为 `阻塞线程接收行情回调`。内部循环 `time.sleep(3)` + 检查连接状态。`quant-qmt-proxy` 在守护线程中启动 `xtdata.run()`。

**修复：** 守护线程中启动 `xtdata.run()`，幂等设计。
**文件：** `trade/real_executor.py:85`（`_ensure_xtdata_runtime`）

---

### Bug #8: 缺少 `trader.register_callback()` — 无订单状态回调

**严重程度：Critical**

**源码验证：** `xttrader.py:340` — `register_callback` 在 `start()` 之前调用。回调接口见 `xttrader.py:24-103`（`XtQuantTraderCallback` 定义 9 个回调方法）。

**修复：** 实现 `_TraderCallback` 类并注册。连接序列：`register_callback` → `start` → `connect` → `subscribe`。
**文件：** `trade/real_executor.py:29-66, 75`

---

### Bug #9: ~~`StockAccount` 缺少 `account_type`~~ — **误报，单参数即可**

**源码验证：** `xttype.py:22` — `def __init__(self, account_id, account_type = 'STOCK')`，默认值 `'STOCK'` 即映射到 `SECURITY_ACCOUNT=2`。`StockAccount("8884731549")` 单参数调用完全正确。

**之前结论错误，已修正。**

---

### Bug #10: 下单缺少 `price_type` 参数

**严重程度：Important**

**源码验证：** `xttrader.py:429-434` — `order_stock` 的 `price_type` 参数无默认值，必须传入。`xtconstant.py:117-119` 定义 `LATEST_PRICE=5, FIX_PRICE=11`。

**修复：**
```python
price_type = FIX_PRICE if price > 0 else 5  # 5=LATEST_PRICE
```
**文件：** `trade/real_executor.py:99`

---

### Bug #11: `subscribe_whole_quote` 返回值未保存

**严重程度：Minor**

**源码验证：** `xtdata.py:747` — 返回 `int` 订阅序号。`xtdata.py:763` — `unsubscribe_quote(seq)` 需要此序号。

**修复：** 保存 `self._sub_seq`，`stop()` 中调用 `unsubscribe_quote`。
**文件：** `trade/quote_pump.py:35, 73-78`

---

### Bug #12: `subscribe_whole_quote` 回调数据格式错误

**严重程度：Critical**

**源码验证：** `xtdata.py:747-760` — `subscribe_whole_quote` 的 `callback` 接收 `{stock_code1: data_dict1, stock_code2: data_dict2, ...}` 格式的 dict，其中 key 为股票代码，value 为包含 `lastPrice/open/high/low/lastClose/volume/amount` 的 dict。

**错误代码：** `_on_tick` 中直接 `data.get("stockCode")`，把整个字典当成单股票行情，永远返回空字符串。

**修复：** 遍历 `datas.items()` 逐个处理每只股票的行情。
```python
def _on_tick(self, datas: dict):
    for code, data in datas.items():
        lp = data.get("lastPrice", 0)
        ...
```

**文件：** `trade/quote_pump.py:41`

---

### xtquant SDK 正确调用链（源码验证）

**行情订阅：**
```
xtdata.py:772 → xtdata.run()          # 守护线程中启动（阻塞循环，每3s检查连接）
xtdata.py:747 → subscribe_whole_quote([codes], callback)
              → 回调: {stock_code: {lastPrice, open, ...}}
              → 返回 seq → 保存
xtdata.py:763 → unsubscribe_quote(seq)
```

**交易下单：**
```
xttrader.py:109 → XtQuantTrader(qmt_path, session_id)
xttrader.py:340 → register_callback(callback)    # 必须在 start() 之前
xttrader.py:343 → start()
xttrader.py:358 → connect() == 0
xttrader.py:379 → subscribe(StockAccount(account_id))
               ↓
xttrader.py:429 → order_stock(account, code, STOCK_BUY|SELL, volume, FIX_PRICE|5, price, ...)
                → 返回 order_id (>0) 或 -1
               ↓
callback.on_stock_order(order)       # 状态更新
callback.on_stock_trade(trade)       # 成交回报
callback.on_order_error(error)       # 订单被拒
```

