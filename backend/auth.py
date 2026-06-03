"""
身份认证 + 角色权限控制

- JWT Token 登录验证
- contextvars 异步安全传递用户角色
- SQL 查询前的区域权限校验
"""

import os
import re
import time
import logging
from contextvars import ContextVar
from typing import Optional
from pathlib import Path

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger("auth")

# ============================================================
# JWT 配置
# ============================================================
JWT_SECRET = os.getenv("JWT_SECRET", "deepresearch-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_SECONDS = 3600 * 8  # 8 小时

# ============================================================
# 用户凭证库（内存版，生产环境应迁移到 MySQL）
# ============================================================
USERS: dict[str, dict] = {
    "admin":    {"password": "admin123",  "role": "管理员",   "name": "系统管理员"},
    "east":     {"password": "east123",   "role": "华东区专员", "name": "张华东"},
    "south":    {"password": "south123",  "role": "华南区专员", "name": "李华南"},
    "north":    {"password": "north123",  "role": "华北区专员", "name": "王华北"},
    "central":  {"password": "central123","role": "华中区专员", "name": "赵华中"},
    "west":     {"password": "west123",   "role": "西南区专员", "name": "陈西南"},
    "northwest":{"password": "nw123",     "role": "西北区专员", "name": "刘西北"},
}

# ============================================================
# 异步安全的上下文变量
# ============================================================
user_role_ctx: ContextVar[Optional[str]] = ContextVar("user_role", default=None)
user_name_ctx: ContextVar[Optional[str]] = ContextVar("user_name", default=None)

# ============================================================
# 角色 → 允许的大区映射
# ============================================================
ROLE_REGION_MAP: dict[str, set[str]] = {
    "华东区专员": {"华东"},
    "华南区专员": {"华南"},
    "华北区专员": {"华北"},
    "华中区专员": {"华中"},
    "西南区专员": {"西南"},
    "西北区专员": {"西北"},
}

ADMIN_ROLES = {"管理员", "admin", "超级管理员"}
ALL_REGIONS = {"华东", "华南", "华北", "华中", "西南", "西北"}


# ============================================================
# JWT Token 操作
# ============================================================
def create_token(username: str, role: str, name: str) -> str:
    """根据用户信息生成 JWT token"""
    payload = {
        "sub": username,
        "role": role,
        "name": name,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """验证 JWT token，返回 payload 或 None"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except ExpiredSignatureError:
        logger.warning("Token 已过期")
        return None
    except InvalidTokenError:
        logger.warning("Token 无效")
        return None


# ============================================================
# 用户认证
# ============================================================
def authenticate(username: str, password: str) -> dict | None:
    """验证用户名密码，成功返回用户信息，失败返回 None"""
    user = USERS.get(username.lower())
    if user and user["password"] == password:
        return {
            "username": username,
            "role": user["role"],
            "name": user["name"],
        }
    return None


# ============================================================
# 上下文管理
# ============================================================
def set_user_role(role: str | None) -> None:
    user_role_ctx.set(role)


def get_user_role() -> str | None:
    return user_role_ctx.get()


def set_user_name(name: str | None) -> None:
    user_name_ctx.set(name)


def get_user_name() -> str | None:
    return user_name_ctx.get()


def get_allowed_regions(role: str | None) -> set[str]:
    if role is None:
        return ALL_REGIONS.copy()
    role_lower = role.strip().lower()
    if role_lower in {r.lower() for r in ADMIN_ROLES}:
        return ALL_REGIONS.copy()
    for role_name, regions in ROLE_REGION_MAP.items():
        if role.strip() == role_name:
            return regions.copy()
    logger.warning(f"未知角色: '{role}'，拒绝访问")
    return set()


# ============================================================
# SQL 权限校验
# ============================================================
def extract_regions_from_sql(sql: str) -> set[str]:
    found = set()
    for m in re.finditer(r"region\s*=\s*'(\S+?)'", sql, re.IGNORECASE):
        found.add(m.group(1))
    in_match = re.search(r"region\s+IN\s*\(([^)]+)\)", sql, re.IGNORECASE)
    if in_match:
        for m in re.finditer(r"'(\S+?)'", in_match.group(1)):
            found.add(m.group(1))
    return found


def check_sql_permission(sql: str) -> tuple[bool, str]:
    role = get_user_role()
    allowed = get_allowed_regions(role)

    if allowed == ALL_REGIONS:
        return True, ""

    if not allowed:
        return False, f"您的角色「{role}」未被授权查询任何数据，请联系管理员。"

    queried_regions = extract_regions_from_sql(sql)

    if not queried_regions:
        return (
            False,
            f"您的角色「{role}」只能查询{'/'.join(sorted(allowed))}大区的数据。"
            f"请在 SQL 中添加 region 过滤条件，"
            f"例如: WHERE region IN ({', '.join(repr(r) for r in sorted(allowed))})",
        )

    forbidden = queried_regions - allowed
    if forbidden:
        return (
            False,
            f"您的角色「{role}」只能查询{'/'.join(sorted(allowed))}大区的数据，"
            f"但当前 SQL 涉及 {'/'.join(sorted(forbidden))} 大区，已拦截。",
        )

    return True, ""
