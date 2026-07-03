import logging



import airsim



from app.core.config import settings



logger = logging.getLogger(__name__)



_client = None





def get_client():

    """Return a lazily-initialized, singleton AirSim client.



    连接被推迟到第一次调用时才建立，避免在 AirSim 未启动时导致服务无法启动。

    """

    global _client

    if _client is None:

        client = airsim.MultirotorClient(

            ip=settings.AIRSIM_IP,

            port=settings.AIRSIM_PORT,

        )

        client.confirmConnection()

        _client = client

        logger.info("Connected to AirSim at %s:%s", settings.AIRSIM_IP, settings.AIRSIM_PORT)

    return _client





def reset_client():

    """Drop the cached client so the next call reconnects (e.g. after AirSim restart)."""

    global _client

    _client = None