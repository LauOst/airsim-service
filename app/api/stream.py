import asyncio
import io
import logging

import airsim
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image

from app.core.airsim_client import create_client

logger = logging.getLogger(__name__)

router = APIRouter()

# 视频流参数（清晰度/延迟/带宽平衡，卡顿可下调分辨率或质量）
# 注意：清晰度上限取决于 AirSim settings.json 里相机的采集分辨率，
# 若源分辨率低于此处，放大只会更模糊，需先调高 settings.json 的 CaptureSettings。
STREAM_WIDTH = 1280
STREAM_HEIGHT = 720
STREAM_FPS = 20
STREAM_JPEG_QUALITY = 80


def _capture_jpeg(client, camera: str) -> bytes | None:
    """从 AirSim 抓一帧未压缩画面并编码成 JPEG（阻塞操作，需放线程执行）。"""
    resp = client.simGetImages(
        [airsim.ImageRequest(camera, airsim.ImageType.Scene, False, False)]
    )[0]
    if not resp.image_data_uint8:
        return None
    img = np.frombuffer(resp.image_data_uint8, dtype=np.uint8)
    img = img.reshape(resp.height, resp.width, 3)  # BGR
    img = img[:, :, ::-1]  # BGR -> RGB
    pil = Image.fromarray(img)
    # 仅在源分辨率大于目标时下采样（用高质量 LANCZOS）；源比目标小则保持原样，避免放大变糊
    if resp.width > STREAM_WIDTH or resp.height > STREAM_HEIGHT:
        pil = pil.resize((STREAM_WIDTH, STREAM_HEIGHT), Image.LANCZOS)
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=STREAM_JPEG_QUALITY)
    return buf.getvalue()


@router.websocket("/camera")
async def camera_stream(websocket: WebSocket):
    await websocket.accept()
    camera = websocket.query_params.get("camera", "0")
    # 视频流使用独立 AirSim 连接，避免与飞行指令抢占同一 RPC
    try:
        client = await asyncio.to_thread(create_client)
    except Exception as e:
        logger.exception("视频流连接 AirSim 失败")
        await websocket.close(code=1011, reason=str(e))
        return

    interval = 1 / STREAM_FPS
    try:
        while True:
            frame = await asyncio.to_thread(_capture_jpeg, client, camera)
            if frame:
                await websocket.send_bytes(frame)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        logger.info("视频流客户端断开连接")
    except Exception:
        logger.exception("视频流异常终止")