# xtquant 股票量化交易系统

基于 **xtquant** (迅投量化交易平台) 的股票自动交易系统，包含策略执行、交易执行和回测功能。

## 系统架构

```
┌─────────────────────┐     gRPC      ┌─────────────────────┐
│  策略执行器          │ ────────────│  交易执行器          │
│  (strategy_executor)│              │  (trade_executor)    │
└─────────────────────┘              └─────────────────────┘
                         │
                         ▼
          ┌─────────────────────────────┐
          │  前端回测系统 (FastAPI)       │
          │  http://localhost:8000          │
          └─────────────────────────────┘
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动交易系统 (需要 QMT 运行)

```bash
# 终端1: 启动交易执行器 (服务端)
python -m src.trade_executor_grpc --config config/stock_config.yaml

# 终端2: 启动策略执行器 (客户端)
python -m src.strategy_executor_grpc --strategy bonus_stocks
```

### 启动回测前端

```bash
python frontend/backend.py
# 访问 http://localhost:8000
```

### 命令行回测

```bash
# 红利ETF定投策略
python -m src.backtest.backtest_engine -s bonus_stocks -d 3m
```

## 项目结构

```
├── config/                     # 配置文件
│   ├── stock_config.yaml       # 交易配置
│   └── bonus_stocks.json       # 策略参数
│
├── src/                       # 源代码
│   ├── trade/                 # 交易功能
│   │   ├── trader.py          # xtquant 封装
│   │   ├── grpc_trade_server.py
│   │   └── grpc_trade_client.py
│   │
│   ├── trade_grpc/            # gRPC 协议
│   │
│   ├── strategies/            # 交易策略
│   │   ├── bonus_stocks.py   # 红利ETF定投
│   │   ├── buy_on_dips.py    # 跌后买入
│   │   └── strategy_utils.py   # 工具函数
│   │
│   ├── backtest/              # 回测系统
│   │   ├── history_data.py
│   │   └── backtest_engine.py
│   │
│   ├── utils/                # 工具
│   │   ├── logger.py
│   │   └── config.py
│   │
│   ├── trade_db.py           # 交易记录数据库
│   │
│   ├── trade_executor_grpc.py
│   └── strategy_executor_grpc.py
│
├── frontend/                 # 前端回测系统
│   ├── backend.py            # FastAPI 后端
│   ├── static/               # 静态文件
│   └── data/                 # 回测结果数据
│
├── data/                     # 数据目录
│   └── trades.db             # 交易记录数据库
│
├── README.md                 # 本文件
├── CLAUDE.md                 # Claude Code 指导
└── requirements.txt          # 依赖
```

## 配置说明

### stock_config.yaml

```yaml
trading:
  max_position_per_stock: 10000
  initial_capital: 100000
  check_interval: 60

strategy:
  bonus_stocks:
    stocks: []
```

### bonus_stocks.json

```json
{
    "investment": {
        "days": ["周三"],
        "base_volume": 500,
        "lot_size": 100
    },
    "etfs": [
        {"code": "515650.SH", "name": "消费50ETF"},
        {"code": "513970.SH", "name": "恒生消费ETF"}
    ],
    "params": {
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "bias_threshold": 10
    }
}
```

## 交易策略

### bonus_stocks (红利ETF定投)

- **触发时间**: 每周三
- **指标**: RSI(14), 250日均线, 乖离率
- **买入逻辑**:
  - RSI > 70: 不买 (超买)
  - RSI < 30: +100份
  - 乖离率 > 10%: 不买
  - 乖离率 < -10%: +100份

### buy_on_dips (跌后买入) - 已禁用

当前只运行 `bonus_stocks` 策略。

## 回测系统

### 命令行回测

```bash
python -m src.backtest.backtest_engine -s bonus_stocks -d 3m
```

参数:
- `-s/--strategy`: 策略名称 (默认 buy_on_dips)
- `-d/--duration`: 回测时长 (1m/3m/6m/1y)
- `--stock`: 股票代码 (默认 515650.SH)

### 前端回测

```bash
python frontend/backend.py
# 访问 http://localhost:8000
```

功能:
- 选择策略和回测时长
- 查看收益曲线图表
- 查看交易记录
- 参数优化

## 交易记录

数据库: `data/trades.db`

```python
from src.trade_db import record_buy, query_trades

# 记录买入
record_buy(
    strategy="bonus_stocks",
    stock_code="515650.SH",
    volume=500,
    price=1.235,
    extra={"buy_reason": "RSI<30", "rsi": 25.5}
)

# 查询记录
trades = query_trades(strategy="bonus_stocks")
```

字段:
- trade_time: 交易时间
- stock_code/name: 品种
- volume: 数量
- price: 价格
- extra.buy_reason: 买入原因

## 注意事项

1. xtquant 需要 QMT 客户端运行
2. 虚拟环境: `.venv`
3. 交易时间: 9:30-14:55
4. 14:50 后自动取消未成交订单