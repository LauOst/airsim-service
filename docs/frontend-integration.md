# AirSim Service 前端对接说明（Vue3 + OpenLayers）

> 本文档给前端项目的 AI/开发者阅读，用于对接 `airsim-service` 后端接口，实现「地图画路径 → 调接口 → 无人机飞行」的闭环。
> 后端已完成并验证可用，前端只需按本文档对接即可。

---

## 1. 服务信息

- **后端地址（baseURL）**：`http://<工作站IP>:8888`（本机开发为 `http://localhost:8888`）
- **协议**：REST + JSON；摄像头为 WebSocket
- **CORS**：后端已全开放（`allow_origins=["*"]`），前端可直接跨域调用，无需代理
- **坐标系**：接口使用 **WGS-84 经纬度**（标准 GPS 经纬度）

---

## 2. 接口清单

### 2.1 执行飞行 `POST /flight/fly`

前端画完路径后调用，无人机按航点顺序飞行。

**请求体：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `waypoints` | array | 是 | - | 航点列表，按数组顺序飞行 |
| `waypoints[].lat` | number | 是 | - | 纬度（WGS-84） |
| `waypoints[].lng` | number | 是 | - | 经度（WGS-84） |
| `altitude` | number | 否 | 80 | 飞行高度（米），城市场景需高于最高建筑，避免撞楼 |
| `speed` | number | 否 | 5 | 飞行速度（m/s） |

**请求示例：**

```json
{
  "waypoints": [
    {"lat": 47.6410, "lng": -122.1400},
    {"lat": 47.6415, "lng": -122.1405},
    {"lat": 47.6415, "lng": -122.1395}
  ],
  "altitude": 80,
  "speed": 5
}
```

**成功响应：**

```json
{
  "status": "success",
  "message": "飞行完成",
  "path": [{"x": 0, "y": 0, "z": -80}, {"x": 55.6, "y": -37.8, "z": -80}]
}
```

**失败响应：**

```json
{ "status": "error", "message": "错误原因", "path": [...] }
```

> `path` 是后端把经纬度换算成的 AirSim NED 坐标（米），仅供调试参考，前端一般用不到。

> ⚠️ **该接口是同步阻塞的**：无人机飞完才返回，可能耗时几十秒。前端 axios `timeout` 必须设大（建议 120000ms），否则会先超时，但无人机实际仍在飞。

### 2.2 查询状态 `GET /flight/status`

```json
{
  "connected": true,
  "position": {"x": 0, "y": 0, "z": -80},
  "landed": 0
}
```

- `connected`：是否连上 AirSim
- `position`：NED 坐标（米），**不是经纬度**
- `landed`：0=飞行中，1=已落地
- 连接失败时返回 `{ "connected": false, "error": "..." }`

### 2.3 降落 `POST /flight/land`

无参数。调用后无人机降落并上锁。当前流程中 `/fly` 结尾是**悬停**，需要落地时再单独调此接口。

```json
{ "status": "success", "message": "已降落" }
```

### 2.4 摄像头视频流 `WS /stream/camera`（WS 二进制 JPEG，临时方案）

> 说明：视频**长期规划走 WebRTC**，但当前先用 WS-JPEG 临时方案跑通。以后接真实摄像头时会切换到 WebRTC，届时前端播放器需调整。

- **传输**：WebSocket，地址 `ws://<工作站IP>:8888/stream/camera`
- **帧格式**：**每帧一张 JPEG，二进制帧**（`websocket.send_bytes`）。前端 `binaryType='blob'`，收到即渲染到 `<img>`/canvas，无协议头。
- **多机位**：query 参数 `?camera=<名称>`，默认 `0`。
- **当前参数**：640×360，约 20fps，JPEG 质量 60（后端常量，可调）。
- **连接失败**：后端若连不上 AirSim，会以关闭码 `1011` 关闭连接，前端可提示并重连。

**前端参考渲染：**

```js
const ws = new WebSocket('ws://192.168.1.201:8888/stream/camera?camera=0')
ws.binaryType = 'blob'
ws.onmessage = (e) => {
  const url = URL.createObjectURL(e.data)
  imgEl.onload = () => URL.revokeObjectURL(url)
  imgEl.src = url // imgEl 为页面上的 <img>
}
ws.onclose = () => { /* 可重连 */ }
```

### 2.5 手动控制（独立模式，非阻塞）

> 当前为「独立模式」：**自动飞路线 `/fly`** 与 **手动遥控** 是两个独立流程，飞行途中不接管。后期再做中途接管（需把 `/fly` 改异步）。

手动流程：先 `POST /flight/takeoff` 起飞 → 用 `/flight/move` 控制 → `/flight/hover` 或 `/flight/stop` 停住 → `/flight/land` 降落。

| 接口 | 说明 |
|------|------|
| `POST /flight/takeoff` | 起飞（含解锁），**阻塞**至起飞完成 |
| `POST /flight/move` | 机体系速度控制，**非阻塞立即返回** |
| `POST /flight/hover` | 悬停 |
| `POST /flight/stop` | 急停（清零速度并悬停） |

**`POST /flight/move` 请求体（机体坐标系）：**

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `vx` | number | 0 | 前后速度 m/s，正=前进 |
| `vy` | number | 0 | 左右速度 m/s，正=右移 |
| `vz` | number | 0 | 上下速度 m/s，**正=下降，负=上升** |
| `yaw_rate` | number | 0 | 偏航角速度 度/s，正=顺时针 |
| `duration` | number | 0.5 | 指令持续秒数 |

```json
{ "vx": 2, "vy": 0, "vz": 0, "yaw_rate": 0, "duration": 0.5 }
```

所有手动接口返回：`{ "status": "success" | "error", "message": "..." }`

**前端遥控交互建议**：按钮/摇杆**按住时**按固定间隔（如每 0.3s）重复 POST `/flight/move`；**松开时**调一次 `/flight/hover`。`duration` 略大于发送间隔，避免指令间隙抖动。

```js
let timer = null
function startMove(payload) {              // 按下
  const send = () => api.post('/flight/move', payload)
  send(); timer = setInterval(send, 300)
}
function stopMove() {                       // 松开
  clearInterval(timer); timer = null
  api.post('/flight/hover')
}
// 例：前进 startMove({vx:2,vy:0,vz:0,yaw_rate:0,duration:0.5})
// 上升 vz:-2；下降 vz:2；左转 yaw_rate:-30；右转 yaw_rate:30
```

---

## 3. OpenLayers 对接关键注意事项（重要，易踩坑）

### 3.1 坐标系转换：地图是 EPSG:3857，接口要 EPSG:4326

OpenLayers 地图默认投影是 **Web Mercator (EPSG:3857)**。从几何体（Geometry）拿到的坐标**不是经纬度**，必须用 `toLonLat()` 转换成 **WGS-84 经纬度**后再传给接口。

### 3.2 坐标顺序：OpenLayers 是 `[经度, 纬度]`，接口要 `{lat, lng}`

**最常见的 bug 来源。** OpenLayers 坐标数组是 `[lon, lat]`（经度在前），而接口字段是 `{lat, lng}`。转换时不要搞反：

```js
const [lng, lat] = toLonLat(coord); // coord[0]=经度, coord[1]=纬度
```

### 3.3 底图坐标系

- 若底图是标准 WGS-84（如 OSM），直接传经纬度即可。
- 若使用高德/百度底图（GCJ-02/BD-09），需先做坐标纠偏，否则位置会偏移。

---

## 4. Vue3 + OpenLayers 参考实现

### 4.1 画线获取航点（`ol/interaction/Draw` + `LineString`）

```js
import Draw from 'ol/interaction/Draw'
import { toLonLat } from 'ol/proj'

// vectorSource 为已挂到地图上的矢量图层数据源
const draw = new Draw({ source: vectorSource, type: 'LineString' })
map.addInteraction(draw)

draw.on('drawend', (e) => {
  const coords = e.feature.getGeometry().getCoordinates() // [[x,y], ...] 地图投影坐标
  const waypoints = coords.map((c) => {
    const [lng, lat] = toLonLat(c) // 转成 WGS-84 经纬度
    return { lat, lng }
  })
  flyDrone(waypoints)
})
```

### 4.2 调用接口（axios）

```js
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8888', // 换成工作站 IP
  timeout: 120000,                  // 飞行阻塞，超时要设大
})

export async function flyDrone(waypoints, altitude = 80, speed = 5) {
  const { data } = await api.post('/flight/fly', { waypoints, altitude, speed })
  if (data.status !== 'success') throw new Error(data.message)
  return data
}

export async function getStatus() {
  const { data } = await api.get('/flight/status')
  return data
}

export async function land() {
  const { data } = await api.post('/flight/land')
  return data
}
```

### 4.3 建议的页面交互

- 一个「画路径」按钮 → 激活 Draw 交互
- 一个「起飞执行」按钮 → 调 `flyDrone(waypoints)`
- 一个「降落」按钮 → 调 `land()`
- 一个状态显示区 → 定时调 `getStatus()` 展示连接状态/位置

---

## 5. 其他注意事项

1. **飞行前先确认 AirSim 已启动**：否则 `/flight/status` 返回 `connected: false`。
2. **高度选择**：城市场景 `altitude` 要高于最高建筑，否则无人机撞墙导致 `moveOnPath` 卡住、`/fly` 请求长时间不返回。
3. **实时轨迹（可选增强）**：当前 `/fly` 阻塞返回，无法边飞边看。若需在地图上实时显示无人机移动，需后端改为「后台执行 + 前端轮询 `/status`」模式，并把 NED 坐标反算回经纬度绘制。此为后续优化项，需要时联系后端调整。
4. **NED 与经纬度**：`/status` 的 `position` 是以第一个航点为原点的 NED 米制坐标，不能直接当经纬度用。

---

## 6. 快速联调步骤

1. 工作站启动 AirSim（Multirotor 模式，RPC 端口 41451）
2. 启动后端：`docker compose up -d --build`
3. 浏览器打开 `http://localhost:8888/docs`，调 `GET /flight/status` 确认 `connected: true`
4. 前端 baseURL 指向后端，画路径 → 调 `/flight/fly` → 观察 AirSim 中无人机飞行
