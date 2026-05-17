"""
FastAPI 后端服务

为回测系统提供 REST API 接口，主要功能:
1. 运行回测: 接收参数，执行回测，返回结果
2. 获取策略列表: 返回支持的策略
3. 获取回测时长选项: 返回可选择的回测时长
4. 历史记录管理: 保存和查询历史回测结果

启动方式:
    python frontend/backend.py

API 接口文档:
    http://localhost:8000/docs (FastAPI 自动生成的Swagger文档)
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path，以便导入 src 模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ==================== 路径配置 ====================

# 当前文件目录
BASE_DIR = Path(__file__).parent
# 数据目录: frontend/data/
DATA_DIR = BASE_DIR / "data"
# 静态文件目录: frontend/static/
STATIC_DIR = BASE_DIR / "static"

# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="回测系统 API",
    description="提供回测引擎的 REST API 接口",
    version="1.0.0"
)


# ==================== 数据模型 ====================

class BacktestRequest(BaseModel):
    """
    回测请求模型

    Attributes:
        strategy: 策略名称，如 "bonus_stocks" 或 "buy_on_dips"
        stock_code: 股票代码，如 "515650.SH"
        duration: 回测时长，如 "1m", "3m", "6m", "1y", "2y" 等
    """
    strategy: str
    stock_code: str
    duration: str = "6m"


class BacktestResponse(BaseModel):
    """
    回测响应模型

    Attributes:
        success: 是否成功
        data: 回测结果数据，成功时返回
        error: 错误信息，失败时返回
    """
    success: bool = False
    data: dict = None
    error: str = None


# ==================== API 路由 ====================

@app.get("/")
async def index():
    """
    根路径，返回主页

    返回静态 HTML 页面 (旧版前端)
    """
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "请访问 /static/index.html"}


@app.get("/static/{filename}")
async def static_file(filename: str):
    """
    静态文件服务

    Args:
        filename: 文件名

    Returns:
        静态文件内容
    """
    file_path = STATIC_DIR / filename
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="文件不存在")


@app.get("/api/strategies")
async def get_strategies():
    """
    获取可用策略列表

    Returns:
        策略列表，包含 ID、名称、描述
    """
    return {
        "strategies": [
            {
                "id": "buy_on_dips",
                "name": "跌后买入",
                "description": "当股票价格下跌超过阈值时买入"
            },
            {
                "id": "bonus_stocks",
                "name": "红利ETF定投",
                "description": "每周定投，结合RSI和乖离率指标"
            },
        ]
    }


@app.get("/api/durations")
async def get_durations():
    """
    获取回测时长选项

    Returns:
        时长选项列表，支持 1个月 到 10年
    """
    return {
        "durations": [
            {"id": "1m", "name": "1个月"},
            {"id": "3m", "name": "3个月"},
            {"id": "6m", "name": "6个月"},
            {"id": "1y", "name": "1年"},
            {"id": "2y", "name": "2年"},
            {"id": "3y", "name": "3年"},
            {"id": "5y", "name": "5年"},
            {"id": "10y", "name": "10年"},
        ]
    }


@app.get("/api/data/{strategy}/{stock}")
async def get_backtest_data(strategy: str, stock: str):
    """
    获取指定策略和股票的回测结果数据

    Args:
        strategy: 策略名称
        stock: 股票代码

    Returns:
        回测结果 JSON 数据

    Raises:
        HTTPException: 数据文件不存在
    """
    # 尝试多个可能的文件路径
    possible_paths = [
        DATA_DIR / f"{strategy}_{stock}.json",
        BASE_DIR.parent / "frontend" / "data" / f"{strategy}_{stock}.json",
    ]

    for path in possible_paths:
        if path.exists():
            with open(path, encoding='utf-8') as f:
                return JSONResponse(json.load(f))

    # 尝试加载默认数据 (只有策略名)
    default_path = DATA_DIR / f"{strategy}.json"
    if default_path.exists():
        with open(default_path, encoding='utf-8') as f:
            return JSONResponse(json.load(f))

    raise HTTPException(status_code=404, detail="回测数据不存在，请先生成数据")


@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """
    运行回测

    接收回测参数，调用回测引擎执行回测，返回结果并保存到文件

    Args:
        request: 回测请求参数

    Returns:
        BacktestResponse: 包含成功状态和回测数据，或错误信息
    """
    try:
        # 导入回测引擎
        from src.backtest.backtest_engine import run_backtest as do_backtest

        # 执行回测
        result = do_backtest(
            strategy=request.strategy,
            stock_code=request.stock_code,
            duration=request.duration,
        )

        # 检查是否出错
        if "error" in result:
            return BacktestResponse(success=False, error=result["error"])

        # 保存数据到文件: frontend/data/{strategy}_{stock}.json
        output_path = DATA_DIR / f"{request.strategy}_{request.stock_code}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return BacktestResponse(success=True, data=result)

    except Exception as e:
        return BacktestResponse(success=False, error=str(e))


@app.get("/api/list")
async def list_data_files():
    """
    列出所有回测数据文件

    Returns:
        文件名列表
    """
    files = []
    for path in DATA_DIR.glob("*.json"):
        files.append(path.name)
    return {"files": files}


@app.get("/api/history")
async def get_history():
    """
    获取历史回测记录列表

    读取 frontend/data/ 目录下所有 JSON 文件，
    解析回测结果，生成历史记录列表

    Returns:
        历史记录列表，包含文件名、策略、股票、交易次数、收益率、创建时间
    """
    history = []

    # 遍历数据目录
    for path in DATA_DIR.glob("*.json"):
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)

            # 获取文件修改时间
            stat = os.stat(path)
            created_at = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            # 提取关键信息
            history.append({
                "filename": path.name,
                "strategy": data.get("strategy", ""),
                "stock_code": data.get("stock_code", ""),
                "total_trades": data.get("total_trades", 0),
                "return_rate": data.get("return_rate", 0),
                "created_at": created_at,
            })
        except Exception:
            # 跳过无效文件
            continue

    # 按时间倒序排列 (最新的在前)
    history.sort(key=lambda x: x["created_at"], reverse=True)
    return {"history": history}


@app.get("/api/param_optimization")
async def get_param_optimization():
    """
    获取参数优化结果

    Returns:
        参数优化数据 JSON

    Raises:
        HTTPException: 数据文件不存在
    """
    path = DATA_DIR / "param_optimization.json"
    if path.exists():
        with open(path, encoding='utf-8') as f:
            return JSONResponse(json.load(f))
    raise HTTPException(status_code=404, detail="参数优化数据不存在")


@app.get("/api/config")
async def get_config():
    """
    获取当前策略配置文件

    读取 config/bonus_stocks.json 配置文件

    Returns:
        配置文件 JSON

    Raises:
        HTTPException: 配置文件不存在
    """
    config_path = BASE_DIR.parent / "config" / "bonus_stocks.json"
    if config_path.exists():
        with open(config_path, encoding='utf-8') as f:
            return JSONResponse(json.load(f))
    raise HTTPException(status_code=404, detail="配置文件不存在")


# ==================== 启动入口 ====================

def main():
    """
    启动 FastAPI 服务

    使用 uvicorn 运行服务器:
    - 监听地址: 0.0.0.0 (所有网卡)
    - 端口: 8000
    - 自动重载: 关闭 (生产环境)

    启动后访问:
    - API: http://localhost:8000
    - 文档: http://localhost:8000/docs
    """
    import uvicorn

    # 确保数据目录存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=" * 50)
    print(f"回测系统 API 服务启动")
    print(f"=" * 50)
    print(f"API 地址: http://localhost:8000")
    print(f"API 文档: http://localhost:8000/docs")
    print(f"数据目录: {DATA_DIR}")
    print(f"=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
