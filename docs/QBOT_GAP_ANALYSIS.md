# Qbot 对比差距分析

> 对比项目: [Qbot](https://github.com/UFund-Me/Qbot) vs xtquant_learning
> 对比重点: 交易模块、回测模块、超参调优
> 最后更新: 2026-05-25

---

## 一、对比总览

| 维度 | xtquant_learning (当前) | Qbot | 差距等级 |
|------|------------------------|------|----------|
| 策略数量 | 1 个（红利ETF定投） | 30+ 经典 + AI 策略 | **P0** |
| 技术指标 | 7 个 | 50+ | **P0** |
| 回测粒度 | 仅日线 | 多周期 | **P0** |
| 回测范围 | 单标的 | 多标的组合 | **P0** |
| 超参优化 | 网格搜索串行/单指标 | 网格搜索 + 可视化对比 | **P0** |
| 回测基准 | 自身定投 | 可选用市场指数 | **P1** |
| 回测报告 | Markdown 纯文本 | quantstats 交互式图表 | **P1** |
| 选股/因子 | 无 | alpha-101/191 多因子 | **P1** |
| 策略模板 | 无参考实现 | 双均线/MACD/布林/海龟等 | **P1** |
| 数据源 | xtquant→akshare→合成 | 多源（JQData/Tushare/EM） | **P1** |
| 交易日历 | weekday 简单过滤 | 真实交易日历 JSON | **P2** |
| 通知系统 | 无 | 邮件/飞书/微信/弹窗 | **P2** |
| 策略版本管理 | 无 | 无（Qbot 也没有） | 差异化机会 |
| 费率/滑点模型 | 完整 | 基础 | ✅ 已领先 |
| 风控系统 | 完整（止损止盈/仓位/频率） | 基础 | ✅ 已领先 |
| gRPC 分离架构 | 完整 | 无 | ✅ 已领先 |
| Web Dashboard | 完整（React+AntD） | 基础 Web | ✅ 已领先 |
| 模拟交易 | 完整（虚拟账户+费率） | 依赖券商仿真 | ✅ 已领先 |

---

## 二、差距详细分析

### 2.1 策略库差距

**当前**: 仅 `BonusStocksStrategy`（RSI + 乖离率 + 开盘变化率 → ETF 定投）

**Qbot 策略池**:

| 类别 | 策略 | 优先级 |
|------|------|--------|
| 均线类 | 简单移动均线、双均线交叉、EMA | **P0** |
| MACD | MACD金叉死叉、MACD+KDJ组合 | **P0** |
| 布林带 | 布林线均值回归 | **P0** |
| 超买超卖 | KDJ、StochRSI、RSI背离 | **P0** |
| 趋势跟踪 | 海龟策略、DMI/ADX、SAR抛物线 | **P1** |
| 波动率 | ATR动态止损、波动率突破 | **P1** |
| 组合策略 | 多因子多策略整合 | **P1** |
| ML策略 | LightGBM/SVM/Random Forest | **P2** |
| DL策略 | LSTM/GRU/Transformer | **P2** |
| RL策略 | Q-Learning | **P2** |

### 2.2 技术指标库差距

**当前**:

| 指标 | 说明 |
|------|------|
| `calc_rsi` | 相对强弱指标 |
| `calc_ma` | 简单移动均线 |
| `calc_ema` | 指数移动均线 |
| `calc_bias` | 乖离率 |
| `calc_macd` | MACD |
| `calc_volatility` | 历史波动率 |
| `calc_open_change` | 开盘变化率 |

**Qbot 有而本项目缺失的核心指标**:

| 优先级 | 指标 | 说明 | 用途 |
|--------|------|------|------|
| **P0** | KDJ | 随机指标 | 超买超卖判断 |
| **P0** | BOLL | 布林带(上中下轨) | 波动区间/突破 |
| **P0** | CCI | 顺势指标 | 异常波动检测 |
| **P0** | StochRSI | 随机相对强弱 | RSI的增强版 |
| **P0** | ATR | 平均真实波幅 | 动态止损/仓位 |
| **P0** | OBV | 能量潮 | 量价背离 |
| **P1** | SAR | 抛物转向 | 趋势跟踪/止损 |
| **P1** | DMI/ADX | 趋向指标 | 趋势强度 |
| **P1** | PSY | 心理线 | 市场情绪 |
| **P1** | ARBR | 人气意愿指标 | 多空力量对比 |
| **P1** | BBI | 多空指标 | 多均线综合 |
| **P1** | ROC | 变动速率 | 动量指标 |
| **P2** | SKDJ | 慢速KDJ | 更平滑的KDJ |
| **P2** | EMV | 简易波动指标 | 量价关系 |
| **P2** | TRIX | 三重指数均线 | 长期趋势 |
| **P2** | DMA | 平均线差 | 均线关系 |
| **P2** | ENE | 轨道线 | 趋势+波动 |

### 2.3 回测引擎差距

| 特性 | 当前 | Qbot (backtrader) | 建议 |
|------|------|-------------------|------|
| **K线周期** | 仅 1d | 1m/5m/15m/30m/60m/1d/1w | 支持分钟级 |
| **回测范围** | 单标的 | 多标的组合 | 支持组合回测 |
| **基准对比** | 自身固定定投 | 可选用市场指数 | 添加沪深300/中证500 |
| **交易日历** | `weekday < 5` 简单过滤 | 真实交易日历 JSON | 使用真实日历 |
| **数据缓存** | 内存 dict | 文件缓存 | 可选持久化到 DB |
| **合成数据** | 有（三级回退） | 无（依赖数据源） | 可选保留或移除 |

### 2.4 超参优化差距

| 特性 | 当前 | 建议 |
|------|------|------|
| **搜索方法** | 网格搜索（Cartesian乘积） | + 随机搜索、贝叶斯优化(Optuna) |
| **执行方式** | 串行 | + 多线程/进程并行 |
| **优化目标** | 单指标（sharpe_ratio） | + 多指标、多目标Pareto |
| **验证方法** | 全量回测 | + Walk-Forward滚动验证 |
| **过拟合检测** | 无 | + 训练/验证集分割 |
| **敏感度分析** | 无 | + 参数扰动分析、交互效应 |
| **结果持久化** | Top 10 | + 全量结果 + 参数快照 |

**建议超参调优架构**:

```
优化方法
├── GridSearch        (全量网格，小参数空间)
├── RandomSearch      (随机采样，高维空间)
├── Optuna/TPE        (贝叶斯优化，推荐默认)
└── GeneticAlgorithm  (遗传算法，离散+连续混合)

验证模式
├── Simple            (全量回测)
├── Walk-Forward      (滚动窗口，如 3y训练+1y验证)
└── K-Fold            (交叉验证)

优化目标
├── sharpe_ratio      (夏普比率，风险调整收益)
├── calmar_ratio      (卡玛比率，收益/最大回撤)
├── return_rate       (总收益率)
├── max_drawdown      (最大回撤，最小化)
└── multi_objective   (Pareto前沿，多目标)

分析输出
├── 最优参数 Top N
├── 参数敏感度图 (单因素)
├── 参数交互热力图
├── Walk-Forward 稳定性评估
└── 过拟合检测报告
```

### 2.5 回测报告差距

| 当前 (Markdown) | Qbot (quantstats) | 建议新增 |
|-----------------|-------------------|----------|
| 绩效指标表 | 绩效指标仪表盘 | ✅ 已有，需增强 |
| 无 | 权益曲线(叠加benchmark) | **P0** |
| 无 | 月度收益热力图 | **P1** |
| 无 | 回撤期分析(水下曲线) | **P1** |
| 无 | 滚动夏普比率 | **P2** |
| 无 | 年度/季度收益分布 | **P2** |
| 无 | 交易分布（按时间/价格） | **P1** |
| 无 | HTML 交互式报告 | **P2** |

### 2.6 数据源差距

| 数据类型 | 当前 | Qbot | 建议 |
|----------|------|------|------|
| K线(日) | ✅ xtquant/akshare | ✅ | - |
| K线(分钟) | ❌ | ✅ | **P0** 支持 |
| 基本面(PE/PB) | ❌ | ✅ | **P1** |
| 财务数据 | ❌ | ✅ | **P2** |
| 行业分类 | ❌ | ✅ | **P2** |
| 因子数据 | ❌ | alpha-101/191 | **P2** |
| 交易日历 | weekday过滤 | JSON日历 | **P0** |

---

## 三、实施优先级

### P0 — 立即补足（回测指导意义最大）

| # | 任务 | 文件 | 工作量 |
|---|------|------|--------|
| 1 | 技术指标库扩展（KDJ/BOLL/CCI/StochRSI/ATR/OBV） | `backend/engine/indicators.py` | 2-3h |
| 2 | 并行网格搜索 + 多指标优化目标 | `backend/backtest/optimizer.py` | 2-3h |
| 3 | Optuna 贝叶斯优化器 | `backend/backtest/optuna_optimizer.py` (新) | 3-4h |
| 4 | Walk-Forward 验证 | `backend/backtest/walkforward.py` (新) | 3-4h |
| 5 | 回测多周期支持（1m/5m/30m/60m） | `backend/backtest/engine.py` | 3-4h |
| 6 | 真实交易日历 | `backend/core/trading_calendar.py` | 1h |
| 7 | 基准对比: 沪深300/中证500 | `backend/backtest/baseline.py` (新) | 1-2h |

### P1 — 策略开发体验增强

| # | 任务 | 文件 | 工作量 |
|---|------|------|--------|
| 8 | 双均线策略模板 | `src/strategies/sma_cross.py` (新) | 1-2h |
| 9 | MACD 策略模板 | `src/strategies/macd_strategy.py` (新) | 1-2h |
| 10 | 布林带策略模板 | `src/strategies/boll_strategy.py` (新) | 1-2h |
| 11 | 技术指标库扩展（SAR/DMI/ADX/PSY/ARBR/BBI/ROC） | `backend/engine/indicators.py` | 2-3h |
| 12 | 回测组合支持（多标的） | `backend/backtest/engine.py` | 3-4h |
| 13 | 收益热力图 + 回撤分析 | 前端/报告器 | 2-3h |
| 14 | 基本面数据（PE/PB 等） | `backend/backtest/fundamental.py` (新) | 2h |
| 15 | 参数敏感度分析 | `backend/backtest/sensitivity.py` (新) | 2-3h |

### P2 — 系统完整性完善

| # | 任务 | 文件 | 工作量 |
|---|------|------|--------|
| 16 | HTML 交互式回测报告 | `backend/backtest/reporter.py` | 3-4h |
| 17 | 通知系统（邮件/飞书） | `backend/core/notify.py` (新) | 2-3h |
| 18 | 多因子打分选股模型 | `backend/engine/factor_model.py` (新) | 4-6h |
| 19 | 策略版本管理（参数快照+对比） | DB + API + 前端 | 3-4h |
| 20 | 财务数据接入 | `backend/backtest/fundamental.py` | 2h |

---

## 四、改造原则

1. **不破坏现有架构**: 新增功能遵循现有分层设计（API → Engine → DB）
2. **策略向后兼容**: 现有 `StrategyBase` 接口不变，新增策略全部遵循 `on_quote(quote) → Signal` 契约
3. **QMT 优先**: 数据源始终保持 xtquant 优先，akshare 回退，合成数据仅用于开发/测试
4. **费率全程计算**: 所有回测/模拟/实盘交易维持现有 `FeeCalculator` 统一费率模型
5. **异步优先**: 新增代码遵循 async/await 模式，保持与现有架构一致

---

## 五、已完成（对比中的领先项）

以下能力本项目中已有、Qbot 不具备或较弱，无需额外开发：

- [x] **决策-执行分离 gRPC 架构** — 策略引擎跨平台 + QMT 交易端 Windows 专属
- [x] **完整的费率模型** — 佣金(万2.5/最低5元)+印花税(千1)+过户费(万0.2)+滑点(千1)
- [x] **模拟交易（SimTradeExecutor）** — 虚拟账户+实时行情撮合+完整费率，Qbot 依赖仿真平台
- [x] **风控系统** — 仓位上限/资金管理/下单频率/止损止盈
- [x] **Web Dashboard** — React+AntD+WebSocket 完整前端
- [x] **PostgreSQL 持久化** — 9 张 ORM 表+Alembic 迁移，Qbot 用 SQLite
- [x] **数据源三级回退** — xtquant→akshare→合成，跨平台可用
- [x] **策略参数 JSON Schema** — `get_config_schema()` 驱动前端表单渲染
- [x] **回测 API 异步执行** — `POST /run` 立即返回 `run_id`，线程池执行，轮询取结果
