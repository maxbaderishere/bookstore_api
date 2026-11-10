from redis.asyncio import Redis

from app.core.config import cfg

# Соединение устанавливается лениво при первой команде.
redis_client: Redis = Redis.from_url(
    cfg.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


async def get_redis() -> Redis:
    return redis_client


async def close_redis() -> None:
    await redis_client.aclose()
