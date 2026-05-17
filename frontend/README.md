# 前端回测系统

基于 React + Ant Design 的可视化回测系统，提供 Web 界面展示策略回测结果。

## 快速开始

### 安装依赖

```bash
# 安装 Python 依赖
pip install fastapi uvicorn pydantic

# 安装 Node.js 依赖
cd frontend
npm install
```

### 启动服务

#### 方式一: 一键启动 (推荐)

```bash
python frontend/start.py
```

#### 方式二: 分别启动

```bash
# 终端1: 启动后端
python frontend/backend.py

# 终端2: 启动前端
cd frontend
npm run dev
```

访问 http://localhost:5173

## 功能

- 前端直接触发回测 (无需手动运行脚本)
- 支持更长回测时长 (最长10年)
- 展示全面的回测指标:
  - 交易次数
  - 总投入 / 最终价值
  - 总收益率 / 年化收益率
  - 最大回撤
  - 波动率 / 夏普比率
  - 卡玛比率 / 胜率
- 收益曲线图表展示
- 买入记录表格
- 历史回测记录列表

## 技术栈

- **前端**: React 18 + Ant Design 5 + Vite + TypeScript
- **后端**: FastAPI (Python)
- **图表**: recharts

## 目录结构

```
frontend/
├── backend.py              # FastAPI 后端
├── start.py              # 启动脚本
├── package.json          # Node.js 项目配置
├── vite.config.ts       # Vite 配置
├── index.html         # 入口 HTML
├── src/
│   ├── main.tsx        # React 入口
│   ├── App.tsx         # 主应用组件
│   ├── api/           # API 调用
│   ├── components/      # React 组件
│   │   ├── BacktestForm/
│   │   ├── Results/
│   │   ├── Chart/
│   │   └── HistoryList/
│   └── types/          # TypeScript 类型
├── data/              # 回测数据
└── static/            # 静态文件
```

## API 接口

| 接口 | 说明 |
|------|------|
| GET / | 主页 |
| GET /api/strategies | 获取可用策略 |
| GET /api/durations | 获取回测时长选项 (扩展到10年) |
| GET /api/data/{strategy}/{stock} | 获取回测结果 |
| POST /api/backtest | 运行回测 |
| GET /api/list | 列出数据文件 |
| GET /api/history | 历史回测记录列表 |
| GET /api/param_optimization | 参数优化结果 |
| GET /api/config | 当前配置 |

## 回测时长选项

| ID | 说明 |
|----|------|
| 1m | 1个月 |
| 3m | 3个月 |
| 6m | 6个月 |
| 1y | 1年 |
| 2y | 2年 |
| 3y | 3年 |
| 5y | 5年 |
| 10y | 10年 |

## 回测指标说明

| 指标 | 说明 | 计算公式 |
|------|------|----------|
| 总收益率 | (最终价值 - 总投入) / 总投入 | (final_value - total_investment) / total_investment |
| 年化收益率 | 将总收益率换算为年化 | (1 + 总收益率) ^ (365/天数) - 1 |
| 最大回撤 | 历史最高点到最低点的跌幅 | max(历史最高点 - 最低点) / 历史最高点 |
| 波动率 | 价格变动幅度 | 价格标准差 / 平均价格 |
| 夏普比率 | 风险调整后收益 | (年化收益率 - 无风险利率) / 波动率 |
| 卡玛比率 | 单位回撤收益 | 年化收益率 / 最大回撤 |
| 胜率 | 盈利交易占比 | 盈利交易次数 / 总交易次数 |

## 数据文件

保存位置: `frontend/data/`

文件名格式: `{strategy}_{stock}.json`

示例:
- `bonus_stocks_515650.SH.json`
- `buy_on_dips_159545.SZ.json`

## 注意事项

1. 需要 **QMT 客户端运行** 才能获取真实历史数据
2. 如果 QMT 未运行，系统会使用模拟数据（仅供参考）
3. 回测结果保存在 `frontend/data/` 目录
