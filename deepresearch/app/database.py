# ============================================================
# 智能销售分析系统 — 数据库引擎 & 会话管理
# ============================================================
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# ---------- 异步引擎（MySQL 连接池） ----------
engine = create_async_engine(
    settings.mysql_dsn,
    pool_size=settings.MYSQL_POOL_SIZE,
    max_overflow=settings.MYSQL_MAX_OVERFLOW,
    pool_recycle=settings.MYSQL_POOL_RECYCLE,
    pool_pre_ping=True,          # 连接前检测可用性
    echo=settings.DEBUG,         # 开发时打印 SQL
)

# ---------- 会话工厂 ----------
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------- 声明式基类 ----------
class Base(DeclarativeBase):
    pass


# ---------- FastAPI 依赖：获取数据库会话 ----------
async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
