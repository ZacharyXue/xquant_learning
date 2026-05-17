"""Dashboard 总览面板 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_session
from backend.db.repository import get_latest_account, get_latest_positions, query_trades
from backend.api.models import DashboardData

router = APIRouter()


@router.get("", response_model=DashboardData)
async def get_dashboard(
    trade_mode: str = "real",
    db: AsyncSession = Depends(get_session),
):
    account = await get_latest_account(db, trade_mode)
    positions = await get_latest_positions(db, trade_mode)
    recent_trades = await query_trades(db, trade_mode=trade_mode, limit=10)

    return DashboardData(
        total_asset=float(account.total_asset) if account else 0.0,
        available_cash=float(account.available_cash) if account else 0.0,
        market_value=float(account.market_value) if account else 0.0,
        total_profit_loss=float(account.total_profit_loss) if account else 0.0,
        positions=[{
            "stock_code": p.stock_code,
            "stock_name": p.stock_name,
            "volume": p.volume,
            "avg_cost": float(p.avg_cost) if p.avg_cost else 0,
            "current_price": float(p.current_price) if p.current_price else 0,
            "market_value": float(p.market_value) if p.market_value else 0,
            "profit_loss": float(p.profit_loss) if p.profit_loss else 0,
        } for p in positions],
        recent_trades=[{
            "id": t.id,
            "strategy_name": t.strategy_name,
            "stock_code": t.stock_code,
            "side": t.side,
            "volume": t.volume,
            "status": t.status,
            "amount": float(t.amount) if t.amount else 0,
            "trade_time": t.trade_time.isoformat() if t.trade_time else "",
        } for t in recent_trades],
        active_strategies=[],
    )
