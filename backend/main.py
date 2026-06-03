from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db
from chat import router as chat_router
from auth import (
    set_user_role, set_user_name, get_user_role,
    authenticate, create_token, verify_token,
)

app = FastAPI(
    title="销售数据 API",
    description="基于 FastAPI + SQLAlchemy + MySQL 的销售数据 Web 服务，集成 Qwen 大模型对话",
    version="1.0.0",
)

# CORS 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


# ============================================================
# 登录接口
# ============================================================
class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名", examples=["east"])
    password: str = Field(..., description="密码", examples=["east123"])


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    name: str


@app.post("/login", response_model=LoginResponse, tags=["认证"], summary="用户登录")
async def login(req: LoginRequest):
    """登录获取 JWT Token，后续请求在 Header 中携带 `Authorization: Bearer <token>`"""
    user = authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user["username"], user["role"], user["name"])
    return LoginResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
        name=user["name"],
    )


# ============================================================
# JWT 认证中间件
# ============================================================
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    从 Authorization Header 中提取 Bearer Token，解析用户角色。
    同时兼容旧的 User-Role 头（开发调试用）。
    """
    auth_header = request.headers.get("Authorization", "")
    role_from_header = request.headers.get("User-Role", None)

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = verify_token(token)
        if payload:
            set_user_role(payload.get("role"))
            set_user_name(payload.get("name"))
        else:
            set_user_role(None)
            set_user_name(None)
    elif role_from_header:
        # 兼容旧版 User-Role Header（开发调试）
        set_user_role(role_from_header.strip())
        set_user_name(role_from_header.strip())
    else:
        set_user_role(None)
        set_user_name(None)

    response = await call_next(request)
    set_user_role(None)
    set_user_name(None)
    return response


# 注册路由
app.include_router(chat_router)


@app.get("/health", tags=["系统"])
def health_check(db: Session = Depends(get_db)):
    """
    健康检查接口：测试数据库连接是否正常。
    返回 `{"status": "ok", "db": "connected"}` 表示一切正常。
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": "disconnected", "detail": str(e)}
