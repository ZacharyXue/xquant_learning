"""系统设置 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.database import get_session
from backend.db.repository import get_system_config, set_system_config
from backend.api.models import FeeSettingsUpdate, SlippageSettingsUpdate

router = APIRouter()


@router.get("/fee")
async def get_fee_config():
    return {
        "commission_rate": settings.fee.commission_rate,
        "stamp_tax_rate": settings.fee.stamp_tax_rate,
        "transfer_fee_rate": settings.fee.transfer_fee_rate,
        "min_commission": settings.fee.min_commission,
    }


@router.put("/fee")
async def update_fee_config(body: FeeSettingsUpdate, db: AsyncSession = Depends(get_session)):
    updates = body.model_dump(exclude_none=True)
    await set_system_config(db, "fee", updates, "费率配置")
    return {"status": "ok", "updated": updates}


@router.get("/slippage")
async def get_slippage_config():
    return {
        "rate": settings.slippage.rate,
        "mode": settings.slippage.mode,
    }


@router.put("/slippage")
async def update_slippage_config(body: SlippageSettingsUpdate, db: AsyncSession = Depends(get_session)):
    updates = body.model_dump(exclude_none=True)
    await set_system_config(db, "slippage", updates, "滑点配置")
    return {"status": "ok", "updated": updates}


@router.get("/trading-hours")
async def get_trading_hours():
    return {
        "start": settings.trading_hours.start,
        "end": settings.trading_hours.end,
        "cancel_unfilled_at": settings.trading_hours.cancel_unfilled_at,
    }


@router.get("/trade-mode")
async def get_trade_mode():
    return {"mode": settings.trade.mode}


@router.put("/trade-mode")
async def set_trade_mode(mode: str = "real", db: AsyncSession = Depends(get_session)):
    await set_system_config(db, "trade_mode", {"mode": mode}, "交易模式")
    return {"status": "ok", "mode": mode}
