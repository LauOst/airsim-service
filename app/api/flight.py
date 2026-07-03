import logging
import math
from typing import List

import airsim
from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.core.airsim_client import get_client, reset_client

logger = logging.getLogger(__name__)

router = APIRouter()

class Waypoint(BaseModel):
    lat: float
    lng: float

class FlightPlan(BaseModel):
    waypoints: List[Waypoint]
    altitude: float = 80.0
    speed: float = 5.0

def latlng_to_ned(waypoints: List[Waypoint], altitude: float) -> List["airsim.Vector3r"]:
    """把前端画的经纬度航点转换成 AirSim 的 NED 坐标（以第一个点为原点）。"""
    origin = waypoints[0]
    lng_scale = math.cos(math.radians(origin.lat))
    path = []
    for wp in waypoints:
        x = (wp.lat - origin.lat) * 111000
        y = (wp.lng - origin.lng) * 111000 * lng_scale
        z = -altitude
        path.append(airsim.Vector3r(x, y, z))
    return path


def _run_flight(path: List["airsim.Vector3r"], altitude: float, speed: float):
    """阻塞式飞行流程，放到线程池执行，避免卡住事件循环。"""
    client = get_client()
    client.enableApiControl(True)
    client.armDisarm(True)
    client.takeoffAsync().join()
    # 先爬升到目标高度，再按航点飞行
    client.moveToZAsync(-altitude, speed).join()
    client.moveOnPathAsync(path, speed).join()
    client.hoverAsync().join()


@router.post("/fly")
async def fly(plan: FlightPlan):
    if not plan.waypoints:
        return {"status": "error", "message": "航点列表为空"}

    path = latlng_to_ned(plan.waypoints, plan.altitude)
    path_preview = [{"x": p.x_val, "y": p.y_val, "z": p.z_val} for p in path]

    try:
        await run_in_threadpool(_run_flight, path, plan.altitude, plan.speed)
        return {"status": "success", "message": "飞行完成", "path": path_preview}
    except Exception as e:
        reset_client()
        logger.exception("飞行执行失败")
        return {"status": "error", "message": str(e), "path": path_preview}

def _run_land():
    client = get_client()
    client.landAsync().join()
    client.armDisarm(False)
    client.enableApiControl(False)


@router.post("/land")
async def land():
    try:
        await run_in_threadpool(_run_land)
        return {"status": "success", "message": "已降落"}
    except Exception as e:
        reset_client()
        logger.exception("降落失败")
        return {"status": "error", "message": str(e)}


class MoveCommand(BaseModel):
    vx: float = 0.0        # 机体系前后速度 (m/s)，正=前
    vy: float = 0.0        # 机体系左右速度 (m/s)，正=右
    vz: float = 0.0        # 上下速度 (m/s)，正=下降
    yaw_rate: float = 0.0  # 偏航角速度 (度/s)，正=顺时针
    duration: float = 0.5  # 指令持续时间 (s)


def _run_takeoff():
    client = get_client()
    client.enableApiControl(True)
    client.armDisarm(True)
    client.takeoffAsync().join()


@router.post("/takeoff")
async def takeoff():
    """起飞（手动模式入口，含解锁）。"""
    try:
        await run_in_threadpool(_run_takeoff)
        return {"status": "success", "message": "已起飞"}
    except Exception as e:
        reset_client()
        logger.exception("起飞失败")
        return {"status": "error", "message": str(e)}


@router.post("/move")
def move(cmd: MoveCommand):
    """机体系速度控制，非阻塞立即返回。前端长按时按固定间隔重复发送。"""
    try:
        client = get_client()
        client.moveByVelocityBodyFrameAsync(
            cmd.vx, cmd.vy, cmd.vz, cmd.duration,
            yaw_mode=airsim.YawMode(is_rate=True, yaw_or_rate=cmd.yaw_rate),
        )
        return {"status": "success", "message": "ok"}
    except Exception as e:
        reset_client()
        logger.exception("手动控制失败")
        return {"status": "error", "message": str(e)}


@router.post("/hover")
def hover():
    """悬停（松开按钮时调用，立即停住）。"""
    try:
        get_client().hoverAsync()
        return {"status": "success", "message": "悬停"}
    except Exception as e:
        reset_client()
        logger.exception("悬停失败")
        return {"status": "error", "message": str(e)}


@router.post("/stop")
def stop():
    """急停：清零速度并悬停。"""
    try:
        client = get_client()
        client.moveByVelocityBodyFrameAsync(0, 0, 0, 1)
        client.hoverAsync()
        return {"status": "success", "message": "已急停"}
    except Exception as e:
        reset_client()
        logger.exception("急停失败")
        return {"status": "error", "message": str(e)}


@router.get("/status")
def status():
    try:

        state = get_client().getMultirotorState()

        return {
            "connected": True,
            "position": {
                "x": state.kinematics_estimated.position.x_val,
                "y": state.kinematics_estimated.position.y_val,
                "z": state.kinematics_estimated.position.z_val,
            },
            "landed": int(state.landed_state)
        }

    except Exception as e:
        # 连接失败时清除缓存，下次请求会重新尝试连接
        reset_client()
        return {
            "connected": False,
            "error": str(e)
        }