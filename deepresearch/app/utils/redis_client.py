# ============================================================
# 智能销售分析系统 — Redis 客户端（连接池）
# ============================================================
import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool

from app.config import get_settings

settings = get_settings()

# ---------- 全局连接池 ----------
_redis_pool: ConnectionPool | None = None


async def get_redis_pool() -> ConnectionPool:
    """懒初始化 Redis 连接池（单例）。"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_dsn,
            max_connections=settings.REDIS_POOL_MAX_CONNECTIONS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            decode_responses=True,
        )
    return _redis_pool


async def get_redis() -> aioredis.Redis:
    """获取一个 Redis 连接（从连接池）。"""
    pool = await get_redis_pool()
    return aioredis.Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    """应用关闭时释放连接池。"""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.disconnect()
        _redis_pool = None
