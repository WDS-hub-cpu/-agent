# ============================================================
# 智能销售分析系统 — FastAPI 入口
# ============================================================
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.utils.redis_client import close_redis_pool, get_redis_pool


# ---------- 生命周期 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动 & 关闭钩子。"""
    # 启动：建表 + 预热 Redis 连接池
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await get_redis_pool()
    yield
    # 关闭：释放资源
    await engine.dispose()
    await close_redis_pool()


# ---------- 应用实例 ----------
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ---------- CORS 跨域 ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 注册路由 ----------
from app.routers import users, sales, chat  # noqa: E402

app.include_router(users.router)
app.include_router(sales.router)
app.include_router(chat.router)

# ---------- 认证调试端点 ----------
from app.dependencies.auth import get_current_user  # noqa: E402
from app.utils.context import RequestUser  # noqa: E402


@app.get("/auth/me", tags=["Auth"])
async def whoami(current_user: RequestUser = Depends(get_current_user)):
    """查看当前 Token 对应的用户身份（调试用）。"""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
    }


# ---------- 健康检查 ----------
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
