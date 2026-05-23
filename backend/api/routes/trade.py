"""交易记录 API"""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_session
from backend.db.repository import query_trades, count_trades
from backend.api.models import TradeRecordOut, PaginatedTrades

router = APIRouter()


@router.get("", response_model=PaginatedTrades)
async def get_trades(
    strategy_name: str = None,
    stock_code: str = None,
    side: str = None,
    status: str = None,
    trade_mode: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * page_size
    items = await query_trades(
        db,
        strategy_name=strategy_name,
        stock_code=stock_code,
        side=side,
        status=status,
        trade_mode=trade_mode,
        limit=page_size,
        offset=offset,
    )
    total = await count_trades(db, strategy_name=strategy_name, trade_mode=trade_mode)

    return PaginatedTrades(
        items=[
            TradeRecordOut(
                id=t.id,
                strategy_name=t.strategy_name,
                stock_code=t.stock_code,
                side=t.side,
                volume=t.volume,
                order_price=float(t.order_price) if t.order_price else None,
                filled_price=float(t.filled_price) if t.filled_price else None,
                status=t.status,
                commission=float(t.commission) if t.commission else 0,
                stamp_tax=float(t.stamp_tax) if t.stamp_tax else 0,
                transfer_fee=float(t.transfer_fee) if t.transfer_fee else 0,
                slippage=float(t.slippage) if t.slippage else 0,
                amount=float(t.amount) if t.amount else None,
                trade_mode=t.trade_mode,
                trade_time=t.trade_time,
                created_at=t.created_at,
            )
            for t in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{trade_id}")
async def get_trade_detail(trade_id: int, db: AsyncSession = Depends(get_session)):
    items = await query_trades(db, limit=1)
    for t in items:
        if t.id == trade_id:
            return t
    return None


@router.get("/export/csv")
async def export_trades_csv(
    strategy_name: str = None,
    trade_mode: str = None,
    limit: int = Query(1000, le=5000),
    db: AsyncSession = Depends(get_session),
):
    items = await query_trades(db, strategy_name=strategy_name, trade_mode=trade_mode, limit=limit)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "strategy", "stock_code", "side", "volume", "price",
                      "status", "commission", "stamp_tax", "transfer_fee",
                      "slippage", "amount", "trade_mode", "trade_time"])
    for t in items:
        writer.writerow([
            t.id, t.strategy_name, t.stock_code, t.side, t.volume,
            float(t.filled_price or t.order_price or 0),
            t.status,
            float(t.commission or 0), float(t.stamp_tax or 0),
            float(t.transfer_fee or 0), float(t.slippage or 0),
            float(t.amount or 0), t.trade_mode,
            t.trade_time.isoformat() if t.trade_time else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )
