"""回测中心 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_session
from backend.db.repository import get_backtest_runs
from backend.api.models import BacktestRequest, BacktestResultOut

router = APIRouter()


@router.post("/run")
async def run_backtest(body: BacktestRequest, db: AsyncSession = Depends(get_session)):
    return {
        "status": "accepted",
        "strategy": body.strategy_name,
        "stock_code": body.stock_code,
        "start_date": body.start_date,
        "end_date": body.end_date,
    }


@router.get("/history")
async def get_history(limit: int = 20, db: AsyncSession = Depends(get_session)):
    runs = await get_backtest_runs(db, limit)
    return [{
        "id": r.id,
        "strategy_name": r.strategy_name,
        "stock_code": r.stock_code,
        "start_date": r.start_date.isoformat() if r.start_date else "",
        "end_date": r.end_date.isoformat() if r.end_date else "",
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else "",
    } for r in runs]


@router.get("/result/{run_id}", response_model=BacktestResultOut)
async def get_result(run_id: int, db: AsyncSession = Depends(get_session)):
    return BacktestResultOut(run_id=run_id)
