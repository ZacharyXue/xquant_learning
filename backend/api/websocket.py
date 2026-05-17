"""
WebSocket 实时推送

推送行情数据、交易状态、策略信号等实时信息。
支持的事件类型:
  - state_sync: 账户/持仓定时同步
  - new_order: 新订单
  - order_update: 订单状态变更
  - trade: 成交记录
  - signal: 策略信号
"""

import asyncio
import json
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect
from backend.core.logging import get_logger

logger = get_logger("websocket")


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket) -> str:
        await ws.accept()
        client_id = f"{ws.client.host}:{ws.client.port}"
        self._connections[client_id] = ws
        logger.info(f"WebSocket connected: {client_id}")
        return client_id

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        logger.info(f"WebSocket disconnected: {client_id}")

    async def broadcast(self, message: dict) -> None:
        dead = []
        for client_id, ws in self._connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.disconnect(client_id)

    async def send_to(self, client_id: str, message: dict) -> None:
        ws = self._connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(client_id)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
    return manager


async def websocket_endpoint(ws: WebSocket):
    """WebSocket 端点"""
    client_id = await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            await manager.send_to(client_id, {"type": "echo", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)
