"""Public realtime intelligence channel."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.events import websocket_hub

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/intelligence")
async def intelligence_socket(websocket: WebSocket) -> None:
    await websocket_hub.connect(websocket)
    await websocket.send_json({
        "type": "connection.ready", "schema_version": "1.0",
        "server_time": datetime.now(timezone.utc).isoformat(),
    })
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=25)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "cursor": message.get("cursor")})
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "heartbeat", "server_time": datetime.now(timezone.utc).isoformat(),
                })
    except (WebSocketDisconnect, RuntimeError):
        await websocket_hub.disconnect(websocket)
