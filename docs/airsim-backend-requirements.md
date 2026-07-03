# AirSim 后端待补接口需求（视频流 + 手动控制）

> 本文档给 **airsim-service 的后端/Python 开发者（含 AI）** 阅读。
> 现有的「地图画路径 → 调接口 → 无人机飞行」闭环已跑通，本文列出前端**下一步需要**的两块能力：
> **① 摄像头视频流**、**② 手动遥控接口**，并给出 Python 侧实现建议与前后端协议约定。

---

## 0. 背景与现状

- 前端：Vue3 + OpenLayers，已实现地图规划航点并通过 `POST /flight/fly` 让 AirSim 无人机飞行。
- 后端：FastAPI（有 `/docs`、CORS `allow_origins=["*"]`），地址示例 `http://192.168.1.201:8888`。
- AirSim 场景为**城市**，飞行中会遇到建筑，需要：
  - **看到第一视角画面**（视频流）用于观察/避障；
  - **手动遥控**无人机以躲避障碍。

### 已有接口（无需改动，仅供参考）

| 接口 | 说明 |
|------|------|
| `POST /flight/fly` | 航点飞行，**同步阻塞**（飞完才返回） |
| `GET /flight/status` | 连接状态 + NED 位置 |
| `POST /flight/land` | 降落上锁 |

---

## 1. 摄像头视频流（优先做）

### 1.1 协议约定（前端已按此实现渲染）

- **传输**：WebSocket。
- **路径**：`WS /stream/camera`（与现有服务同一 host/port）。
- **帧格式**：**每帧一张 JPEG，以二进制帧发送**（`websocket.send_bytes(jpeg_bytes)`）。
  - 前端 `binaryType='blob'`，收到即渲染，无需额外封装/协议头。
  - 如需改用 base64 文本帧（`data:image/jpeg;base64,...`）也可，但**请提前告知前端**（带宽多约 33%）。
- **多机位（可选）**：用 query 参数区分，如 `WS /stream/camera?camera=front`（默认 `0`）。

### 1.2 推荐参数（延迟/带宽平衡）

- 分辨率：先 **640×360**
- 帧率：**15–20 fps**
- JPEG 质量：**55–65**
- 卡顿再往下调；画质不够再上调或后续升级 H.264/WebRTC。

### 1.3 Python 参考实现（FastAPI + OpenCV）

```python
import asyncio, cv2, numpy as np, airsim
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/stream/camera")
async def camera_stream(ws: WebSocket):
    await ws.accept()
    # 建议：视频流用独立的 AirSim client 连接，避免与阻塞的 /fly 抢同一 RPC
    client = airsim.MultirotorClient()
    camera = ws.query_params.get("camera", "0")
    try:
        while True:
            resp = client.simGetImages(
                [airsim.ImageRequest(camera, airsim.ImageType.Scene, False, False)]
            )[0]
            img = np.frombuffer(resp.image_data_uint8, dtype=np.uint8)
            img = img.reshape(resp.height, resp.width, 3)     # BGR
            img = cv2.resize(img, (640, 360))                 # 降分辨率降延迟
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ok:
                await ws.send_bytes(buf.tobytes())            # 二进制 JPEG 帧
            await asyncio.sleep(1 / 20)                        # ~20fps
    except WebSocketDisconnect:
        pass
```

### 1.4 注意事项

- **独立连接**：视频抓图建议用**单独的 AirSim client**，防止 `/fly` 阻塞期间视频被拖慢。
- **多客户端**：若多个页面看同一路视频，建议 **一个采集循环 + 广播**给多个 WS 连接，不要每个连接各开一路采集（AirSim 抓图有开销）。
- **断开处理**：捕获 `WebSocketDisconnect`，退出循环并释放资源。
- **心跳/保活**：前端会尝试重连；后端不要因空闲主动踢连接（或对 ping 帧回 pong）。

---

## 2. 手动遥控接口（其次做）

### 2.1 核心要求

- **必须非阻塞**：手动控制接口要**立即返回**（与阻塞式 `/fly` 不同），否则按钮点一下要等命令跑完，遥控会卡。
- 基于 AirSim 的 `moveByVelocityBodyFrameAsync` / `moveToPositionAsync` / `hoverAsync` 封装。

### 2.2 建议接口（二选一或都提供）

**A. 点动 / 步进（实现最简单，前端体验为"点一下走一步"）**

```
POST /flight/step   { "forward": 2, "right": 0, "up": 0, "yaw": 0 }
# 含义：机体系前进 2m（right 右移、up 上升、yaw 转角度，单位 m / 度）
```

**B. 速度控制（前端"按住持续移动、松开悬停"，体验更像遥控器）**

```
POST /flight/move   { "vx": 2, "vy": 0, "vz": 0, "yaw_rate": 0, "duration": 0.3 }
# 机体系速度(m/s)，前端按住时按固定间隔持续发帧
```

**通用：**

```
POST /flight/hover     # 悬停
POST /flight/stop      # 急停（可与 hover 合并）
```

返回体统一：`{ "status": "success" | "error", "message": "..." }`

### 2.3 Python 参考（机体系速度，非阻塞）

```python
@app.post("/flight/move")
def move(cmd: MoveCmd):
    # join=False 不阻塞，立即返回
    client.moveByVelocityBodyFrameAsync(
        cmd.vx, cmd.vy, cmd.vz, cmd.duration,
        yaw_mode=airsim.YawMode(is_rate=True, yaw_or_rate=cmd.yaw_rate),
    )
    return {"status": "success", "message": "ok"}
```

### 2.4 关于「路线飞行中途手动接管」（可选，较复杂）

- 目前 `/fly` **阻塞**，飞行期间无法插手。
- 若需要「自动飞路线 + 中途随时手动接管避障」，需把 `/fly` 改为**后台异步执行**（后台线程/任务跑飞行，接口立即返回一个任务 id，前端轮询状态；手动指令可随时打断）。
- 若只需「路线飞行」与「纯手动遥控」两个**独立模式**（不中途接管），则 `/fly` 无需改动。
- 请后端确认走哪种，前端据此配合。

---

## 3. 需要后端回复确认的点

1. **视频帧格式**：是否按「WS 二进制 JPEG 帧」实现？（默认按此）
2. **视频地址**：是否即 `ws://192.168.1.201:8888/stream/camera`？
3. **控制接口**：采用 步进 `/step` 还是 速度 `/move`（或都提供）？字段/单位是否按本文？
4. **中途接管**：是否需要把 `/fly` 改为异步以支持飞行中手动接管？

前端会按最终确认的协议对接。以上如有更好的实现，欢迎调整后同步字段约定即可。
