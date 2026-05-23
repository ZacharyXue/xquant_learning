# 开发计划

> 基于当前平台功能差距分析，规划 4 天开发任务。
> 最后更新: 2026-05-19

---

## 测试纪律

1. **API 优先测试**：优先使用 `Invoke-RestMethod` / `curl` 调用 API 接口验证功能，不启动无限等待的服务
2. **并行验证**：多个独立 API 测试应并行发起请求，缩短验证时间
3. **快速回收**：验证通过后立即 `Stop-Process` 杀死后端进程，继续后续流程
4. **先修后测**：先完成代码修改，再统一启动服务验证，避免反复重启

---

## Day 1: 回测引擎修复 + 数据可靠性

### 1.1 修复 sharpe_ratio 数值溢出
- **文件**: `backend/backtest/metrics.py`
- **问题**: 0 交易时 sharpe = `-4.6e+16`，DB `NUMERIC(10,4)` 溢出
- **方案**: `_calc_sharpe` 加边界保护 `max(-9999, min(9999, sharpe))`；`_empty_result` 确保返回合法值

### 1.2 修复持久化失败后状态卡 running
- **文件**: `backend/api/routes/backtest.py`
- **问题**: `_persist()` 异常处理只 log 不更新 status
- **方案**: except 块中 `run.status = "failed"`, `run.error_msg = str(e)`, `await db.commit()`

### 1.3 降低合成数据波动率
- **文件**: `backend/backtest/data_provider.py`
- **问题**: 随机游走波动过大，RSI 常出现极端值 0 或 100
- **方案**: ETF `daily_vol` 0.015→0.008，stock 0.025→0.018

### 1.4 前端回测表单优化
- **文件**: `frontend/src/pages/Backtest/index.tsx`
- **方案**: 股票代码默认 `510880.SH`；日期范围提示「建议 3 年以上」

### 1.5 回测结果 API 增强
- **文件**: `backend/api/routes/backtest.py`
- **方案**: `get_history` 返回 `error_msg` 字段；`get_result` 返回有效数据而非空对象

### 1.6 前端回测历史显示错误信息
- **文件**: `frontend/src/pages/Backtest/index.tsx`
- **方案**: 表格增加「错误」列，failed 时显示原因

**验收标准**:
```powershell
# 并行测试
$body = '{"strategy_name":"bonus_stocks","stock_code":"510880.SH","start_date":"20220101","end_date":"20241231","params":{}}'
$r1 = Invoke-RestMethod -Uri "http://localhost:8000/api/backtest/run" -Method Post -Body $body -ContentType "application/json"
# 等待回测完成
Start-Sleep -Seconds 8
$h = Invoke-RestMethod -Uri "http://localhost:8000/api/backtest/history?limit=3"
$r = Invoke-RestMethod -Uri "http://localhost:8000/api/backtest/result/$($h[0].id)"
# 验证: h[0].status in (completed|failed), r.total_trades >= 0
```

---

## Day 2: 回测可视化 + 参数优化 API

### 2.1 参数优化 API
- **文件**: `backend/api/routes/backtest.py`
- **方案**: 新增 `POST /api/backtest/optimize`，接收 `ParamOptimizeRequest`，调用 `GridOptimizer`，持久化 Top 10

### 2.2 回测结果详情页
- **文件**: 新建 `frontend/src/pages/Backtest/Result.tsx`
- **方案**: 权益曲线 LineChart + 买入标记 Scatter + 指标卡片（收益/回撤/夏普）

### 2.3 前端参数优化表单
- **文件**: `frontend/src/pages/Backtest/index.tsx`
- **方案**: 新增「参数优化」Tab/Modal，选择参数范围，提交优化

### 2.4 优化结果展示
- **文件**: `frontend/src/pages/Backtest/Result.tsx`
- **方案**: Top 10 参数组合表格，按夏普排序；点击查看详细回测结果

**验收标准**:
```powershell
# 优化请求
$body = '{"strategy_name":"bonus_stocks","stock_code":"510880.SH","start_date":"20240101","end_date":"20241231","param_grid":{"rsi_period":[7,14,21],"rsi_overbought":[65,70,75],"rsi_oversold":[25,30,35]}}'
$r = Invoke-RestMethod -Uri "http://localhost:8000/api/backtest/optimize" -Method Post -Body $body -ContentType "application/json"
# 验证: r.status = "accepted", r.total_combos = 27
```

---

## Day 3: 模拟交易完善 + 风控增强

### 3.1 动态切换执行器
- **文件**: `backend/trade/engine.py`
- **方案**: `initialize()` 中根据 `settings.trade.mode` 选择 `RealTradeExecutor` 或 `SimTradeExecutor`

### 3.2 止损/止盈风控
- **文件**: `backend/engine/risk_manager.py`
- **方案**: 新增 `stop_loss_pct`（默认 -5%）、`take_profit_pct`（默认 +15%）；check 时计算持仓盈亏比

### 3.3 风控配置 API + UI
- **文件**: `backend/api/routes/settings.py` + `frontend/src/pages/Settings/index.tsx`
- **方案**: 新增 `GET/PUT /api/settings/risk`，前端增加止损止盈输入框

### 3.4 模拟模式行情数据
- **文件**: `backend/trade/sim_executor.py`
- **方案**: `get_history_kline` 接入 `DataProvider`；`subscribe_quotes` 基于收盘价生成 tick

### 3.5 模拟/真实交易记录区分
- **文件**: 前端 Dashboard/TradeHistory
- **方案**: 按 `trade_mode` 筛选，增加 real/sim Tab

**验收标准**:
```powershell
# 切换到模拟模式
Invoke-RestMethod -Uri "http://localhost:8000/api/settings/trade-mode?mode=sim" -Method Put
# 验证风控配置
$r = Invoke-RestMethod -Uri "http://localhost:8000/api/settings/risk"
# 验证: r.stop_loss_pct = -0.05, r.take_profit_pct = 0.15
```

---

## Day 4: 策略管理增强 + 收尾

### 4.1 策略参数编辑 API + UI
- **文件**: `backend/api/routes/strategy.py` + `frontend/src/pages/Strategy/index.tsx`
- **方案**: 新增 `PUT /api/strategy/{name}/config`；前端 Modal 表单（基于 `get_config_schema()`）

### 4.2 Dashboard 活跃策略
- **文件**: `backend/api/routes/dashboard.py`
- **方案**: 从 `strategy_registry.get_active_instances()` 读取

### 4.3 前端 Dashboard 策略状态
- **文件**: `frontend/src/pages/Dashboard/index.tsx`
- **方案**: 增加「活跃策略」卡片区域

### 4.4 数据导出
- **文件**: `backend/api/routes/trade.py` + 前端
- **方案**: `GET /api/trade/export?format=csv`；前端加导出按钮

### 4.5 WebSocket 前端接入
- **文件**: `frontend/src/pages/Dashboard/index.tsx`
- **方案**: 用 `useWebSocket` hook 替代 HTTP 轮询

### 4.6 回测数据缓存
- **文件**: `backend/backtest/data_provider.py`
- **方案**: 增加 `_cache` dict，同代码+日期不重复 fetch

### 4.7 全量测试
- **文件**: `tests/`
- **方案**: 运行 `pytest tests/ -v` 确保通过

**验收标准**: 策略参数可编辑保存；Dashboard WebSocket 实时更新；交易记录可导出 CSV；回测数据有缓存；全量测试通过。

---

## 总时间估算

| 天 | 估计工时 | 核心风险 |
|----|---------|---------|
| Day 1 | 3-4h | 低 - 纯 bug 修复 |
| Day 2 | 4-5h | 中 - GridOptimizer 大数据量可能超时 |
| Day 3 | 3-4h | 中 - Engine 动态切换需仔细测试 |
| Day 4 | 3-4h | 低 - 功能增强为主 |
| **总计** | **13-17h** | |
