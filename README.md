# AirSim Service

## 项目简介

AirSim Service 是工作站中的一个独立业务模块。

作用：

- 接收前端飞行任务
- 调用 AirSim Python API
- 控制无人机飞行
- 提供视频流接口
- 提供 REST API

该项目采用 Docker 部署，不依赖宿主机 Python 环境。

---

# 项目目录

```
airsim-service
│
├── app/                    # FastAPI 源码
│
├── sdk/
│   └── airsim/             # AirSim Python SDK（官方源码复制）
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# Docker 镜像构建

首次构建：

```bash
docker build --no-cache -t airsim-service:1.0 .
```

说明：

- `--no-cache`
  不使用缓存重新构建

- `airsim-service:1.0`
  镜像名称及版本

---

# Docker Compose 启动（推荐）

启动服务：

```bash
docker compose up -d
```

停止服务：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f
```

重新构建：

```bash
docker compose up -d --build
```

查看运行中的容器：

```bash
docker ps
```

查看所有容器：

```bash
docker ps -a
```

---

# 容器说明

容器名称：

```
airsim-service
```

镜像：

```
airsim-service:1.0
```

端口：

```
8888
```

访问地址：

```
http://localhost:8888
```

---

# API 测试

首页：

```
GET /
```

返回：

```json
{
    "status": "ok",
    "message": "AirSim Service is running"
}
```

Swagger：

```
http://localhost:8888/docs
```

OpenAPI：

```
http://localhost:8888/openapi.json
```

---

# 开发流程

修改 Python 代码：

↓

重新构建镜像

```bash
docker compose up -d --build
```

↓

刷新浏览器验证接口。

---

# AirSim SDK

SDK 来源：

```
D:\docker\sdk\AirSim-source
```

项目内使用：

```
sdk/
└── airsim/
```

说明：

为了避免依赖 GitHub 在线安装，项目直接引用官方 SDK。

无需：

```
pip install airsim
```

---

# 工作站架构

本项目属于：

```
D:\docker
│
├── platform
│
│   ├── postgres
│   ├── geoserver
│   └── ...
│
├── projects
│
│   └── airsim-service
│
├── sdk
│
│   └── AirSim-source
│
└── docs
```

本项目属于：

```
业务模块（Projects）
```

不是：

```
平台底座（Platform）
```

---

# 后续规划

- [x] Docker 化
- [x] FastAPI 服务
- [x] Docker Compose 管理
- [ ] 连接 AirSim
- [ ] 控制无人机
- [ ] 视频流推送
- [ ] Vue 前端联调
- [ ] AI 识别接入