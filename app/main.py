from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.flight import router as flight_router
from app.api.stream import router as stream_router
from app.core.config import settings

app = FastAPI(title="AirSim Service")

# 允许跨域，前端 Vue 可以直接调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(flight_router, prefix="/flight", tags=["flight"])
app.include_router(stream_router, prefix="/stream", tags=["stream"])

@app.get("/")
def root():
    return {"status": "ok", "message": "AirSim Service is running"}