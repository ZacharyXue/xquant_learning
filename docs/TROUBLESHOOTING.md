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
