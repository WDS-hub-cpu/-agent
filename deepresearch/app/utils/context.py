# ============================================================
# 请求上下文 — 基于 contextvars（适配 FastAPI 异步）
# ============================================================
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(slots=True)
class RequestUser:
    """当前请求的用户身份信息。"""
    user_id: int
    role: str          # admin / analyst / viewer
    username: str = ""


# ---------- 全局上下文变量 ----------
_current_user: ContextVar[RequestUser | None] = ContextVar(
    "_current_user", default=None
)


def set_current_user(user: RequestUser) -> Token:
    """设置当前请求的用户上下文，返回一个 Token 用于后续重置。"""
    return _current_user.set(user)


def get_current_user() -> RequestUser | None:
    """获取当前请求的用户上下文。"""
    return _current_user.get(None)


def reset_current_user(token: Token) -> None:
    """请求结束时重置上下文。"""
    _current_user.reset(token)
