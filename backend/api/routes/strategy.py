"""策略管理 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_session
from backend.db.repository import get_strategies
from backend.api.models import StrategyInfo, StrategyToggle

router = APIRouter()


@router.get("", response_model=list[StrategyInfo])
async def list_strategies(db: AsyncSession = Depends(get_session)):
    strategies = await get_strategies(db)
    return [
        StrategyInfo(
            name=s.name,
            display_name=s.display_name,
            description=s.description or "",
            enabled=s.enabled,
            config=s.config or {},
        )
        for s in strategies
    ]


@router.post("/toggle")
async def toggle_strategy(body: StrategyToggle, db: AsyncSession = Depends(get_session)):
    return {"name": body.name, "enabled": body.enabled}


@router.get("/{name}/signals")
async def get_signals(name: str, limit: int = 50, db: AsyncSession = Depends(get_session)):
    return {"strategy": name, "signals": []}
