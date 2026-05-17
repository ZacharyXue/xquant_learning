# AGENTS.md

## 本文档目的

本文档是 **AI 编程助手（opencode）** 在本项目中的工作指南。包含本地环境路径、常用命令和代码规范——这些是每次对话都必须加载的核心信息。

> 架构设计、数据库表结构、费率模型等详细内容见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。
> 项目概述和功能列表见 [README.md](README.md)。

---

## 本地开发环境

AI 助手生成命令时**必须使用以下实际路径**，禁止用占位符。

### Python 环境

| 项目 | 值 |
|------|-----|
| Python 版本 | 3.11.9 (64-bit) |
| Python 路径 | `F:\Codes\Python311-64\python.exe` |
| 虚拟环境 | `F:\Codes\xtquant_learning\.venv` |
| 虚拟环境 Python | `.venv\Scripts\python.exe` |
| 激活命令 | `.venv\Scripts\Activate.ps1` |

### QMT / xtquant

| 项目 | 值 |
|------|-----|
| QMT 安装路径 | `D:\国金证券QMT交易端` |
| xtquant SDK 路径 | `D:\国金证券QMT交易端\bin.x64\Lib\site-packages\xtquant` |
| xtquant .pth 文件 | `.venv\Lib\site-packages\xtquant.pth`（已配置 DLL 搜索路径） |
| 券商 | 国金证券 |
| 状态 | QMT 客户端运行中时可正常调用 xtdata / xttrader |

### 数据库

| 项目 | 值 |
|------|-----|
| 类型 | PostgreSQL 16 |
| 运行方式 | Docker Desktop (WSL2) |
| 容器名 | `xtquant_postgres` |
| 端口 | `5432` |
| 用户名/密码 | `postgres` / `postgres` |
| 数据库名 | `xtquant` |
| 数据目录 | `docker\pgdata\`（绑定挂载，删除镜像不丢数据） |
| 连接地址 | `postgresql+asyncpg://postgres:postgres@localhost:5432/xtquant` |

### Node.js / 前端

| 项目 | 值 |
|------|-----|
| Node.js | v22.14.0 |
| npm | 10.9.2 |
| 前端目录 | `frontend\` |
| 开发服务器 | `npm run dev`（端口 5173，API 代理到 8000） |
| 构建命令 | `npm run build`（tsc + vite build） |

---

## 常用命令

### 启动服务

```powershell
# 一键启动（Windows，自动检查 DB + 启动后端 + 启动前端）
.\scripts\start.ps1

# 仅启动后端
.\scripts\start.ps1 --Backend

# 仅启动前端
.\scripts\start.ps1 --Frontend

# 完整启动（Dashboard + Trade Engine，需要 QMT）
.\scripts\start.ps1 --Full

# 启动数据库（如未运行）
docker compose -f docker/docker-compose.yml up -d postgres

# 访问 Dashboard: http://localhost:5173
# API 文档: http://localhost:8000/docs
```

### 开发命令

```powershell
# 运行 Python 脚本（务必使用 venv Python）
.venv\Scripts\python.exe -c "<code>"

# 安装依赖
.venv\Scripts\python.exe -m pip install <package>

# 重新生成 gRPC 代码（修改 trade.proto 后执行）
.venv\Scripts\python.exe -m grpc_tools.protoc --proto_path=backend/grpc --python_out=backend/grpc --grpc_python_out=backend/grpc backend/grpc/trade.proto
# 生成后需修复 import：将 trade_pb2_grpc.py 中的 "import trade_pb2" 改为 "from backend.grpc import trade_pb2"

# 数据库迁移
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "描述"

# 运行测试
.venv\Scripts\python.exe -m pytest tests/ -v

# 前端构建检查
cd frontend; npm run build
```

### 数据库操作

```powershell
# 查看表结构
docker exec xtquant_postgres psql -U postgres -d xtquant -c "\dt"

# 进入 PostgreSQL shell
docker exec -it xtquant_postgres psql -U postgres -d xtquant

# 重启数据库
docker compose -f docker/docker-compose.yml restart postgres
```

---

## 代码规范

### 提交规则
- **每完成一个特性或修复，立即 commit**，使用 conventional commits 格式
- **禁止自动 push**，由开发者手动推送
- 示例：`feat(phase3): trade execution layer` / `fix: frontend build TS errors`

### Python 代码风格
- 函数必须有 docstring（Google 风格，中文可接受）
- 变量/函数: snake_case / 类: PascalCase / 异步优先 / 完整类型标注
- 错误处理: 使用 `backend.core.exceptions` 中的自定义异常，禁止裸 `except`
- 日志: 统一使用 `from backend.core.logging import get_logger`，禁止 `print`
- 配置: 不硬编码，从 `config/app.yaml` 或数据库加载
- 敏感信息: qmt_path / account_id 通过环境变量注入，不入库

### 策略开发规范
新增策略必须：
1. 继承 `StrategyBase`，实现 `async def on_quote(quote) -> Optional[Signal]`
2. 使用 `@register` 装饰器注册
3. 实现 `get_config_schema()` 返回 JSON Schema（供前端渲染配置表单）
4. 所有参数可配置，不硬编码

```python
@register
class MyStrategy(StrategyBase):
    name = "my_strategy"
    display_name = "我的策略"

    async def on_quote(self, quote: Quote) -> Optional[Signal]:
        ...

    def get_config_schema(self) -> dict:
        return {"type": "object", "properties": {...}}
```

---

## 技术栈摘要

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| 迁移 | Alembic |
| gRPC | grpcio + protobuf |
| 交易 SDK | xtquant (QMT) |
| 前端 | React 18 + TypeScript + Ant Design 5 + Recharts |
| 测试 | pytest + pytest-asyncio |

> 详细架构、数据模型、费率定义等参见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
