# ============================================================
# 认证依赖项 — 模拟 Token 解析 & 角色注入 & 越权拦截
# ============================================================
from fastapi import Depends, Header, HTTPException, status
from typing import Annotated

from app.utils.context import RequestUser, set_current_user, reset_current_user


# ---------- 模拟用户库（可替换为 DB 查询或 JWT 解析） ----------
_MOCK_USERS: dict[str, dict] = {
    "token-admin-001":    {"user_id": 1, "role": "admin",   "username": "admin_wang"},
    "token-analyst-002":  {"user_id": 2, "role": "analyst", "username": "analyst_li"},
    "token-viewer-003":   {"user_id": 3, "role": "viewer",  "username": "viewer_zhang"},
    "token-viewer-004":   {"user_id": 4, "role": "viewer",  "username": "viewer_zhao"},
}


async def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> RequestUser:
    """
    FastAPI 依赖项：
    1. 从 Authorization 请求头提取 Bearer Token（模拟）
    2. 解析出 user_id / role / username
    3. 注入 contextvars，在整个请求生命周期内可访问
    4. 返回 RequestUser 供路由层直接使用
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    # 解析 Bearer token
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization scheme, expected 'Bearer <token>'",
        )

    # 模拟查询用户（实际项目中此处应调用 DB 或解析 JWT）
    user_payload = _MOCK_USERS.get(token)
    if not user_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    request_user = RequestUser(
        user_id=user_payload["user_id"],
        role=user_payload["role"],
        username=user_payload["username"],
    )

    # 注入 contextvars，获取 reset token
    ctx_token = set_current_user(request_user)

    try:
        yield request_user
    finally:
        # 请求结束后重置上下文，防止泄漏到下一个请求
        reset_current_user(ctx_token)


# ---------- 角色守卫：仅允许指定角色访问 ----------
class RoleGuard:
    """依赖项工厂：限制只有特定角色可以访问。"""

    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: RequestUser = Depends(get_current_user),
    ) -> RequestUser:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not allowed. Required: {self.allowed_roles}",
            )
        return current_user


# 快捷依赖
RequireAdmin = RoleGuard(["admin"])
RequireAnalyst = RoleGuard(["admin", "analyst"])
