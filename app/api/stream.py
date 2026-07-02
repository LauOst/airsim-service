import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/camera")
async def camera_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({
                "type": "frame",
                "data": "",
                "message": "开发模式，未连接 AirSim"
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("客户端断开连接")