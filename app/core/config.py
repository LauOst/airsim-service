import os


class Settings:
    AIRSIM_IP: str = os.getenv("AIRSIM_IP", "host.docker.internal")
    AIRSIM_PORT: int = int(os.getenv("AIRSIM_PORT", "41451"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()
