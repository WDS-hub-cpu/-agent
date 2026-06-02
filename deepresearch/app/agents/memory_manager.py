# ============================================================
# Agent 记忆管理器
# · RedisChatMessageHistory 多 Session 隔离
# · K=20 消息数量裁剪
# · Token 预算拦截器（拼接历史时动态截断）
# ============================================================
from __future__ import annotations

import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_message_histories import RedisChatMessageHistory

from app.config import get_settings

settings = get_settings()

# ---------- Redis Key 模板 ----------
SESSION_KEY_TPL = "chat_history:{user_id}:{session_id}"

# ---------- Tokenizer（使用 cl100k_base 近似 Qwen 系列） ----------
_tokenizer = tiktoken.get_encoding("cl100k_base")


# ════════════════════════════════════════════════════════════
# 对外 API
# ════════════════════════════════════════════════════════════

def get_history(user_id: int, session_id: str) -> RedisChatMessageHistory:
    """
    获取指定用户 + 会话的 Redis 消息历史。
    key 格式: chat_history:{user_id}:{session_id}
    """
    pool = None  # 由 RedisChatMessageHistory 内部创建连接
    return RedisChatMessageHistory(
        session_id=SESSION_KEY_TPL.format(user_id=user_id, session_id=session_id),
        url=settings.redis_dsn,
        ttl=settings.MEMORY_REDIS_TTL,
    )


async def get_history_async(user_id: int, session_id: str) -> RedisChatMessageHistory:
    """异步版本（连接池复用）。"""
    return RedisChatMessageHistory(
        session_id=SESSION_KEY_TPL.format(user_id=user_id, session_id=session_id),
        url=settings.redis_dsn,
        ttl=settings.MEMORY_REDIS_TTL,
    )


async def load_and_trim_history(
    user_id: int,
    session_id: str,
    system_prompt: str | None = None,
) -> list[BaseMessage]:
    """
    加载历史消息并执行双重裁剪：
      (1) K 裁剪：只保留最近 K 条消息
      (2) Token 裁剪：如果总 Token 超过预算，从旧到新逐条移除直到满足限制

    返回裁剪后的消息列表（SystemMessage 始终保留在最前面）。
    """
    history = get_history(user_id, session_id)
    raw_messages: list[BaseMessage] = history.messages

    # ---- 第一重：K 裁剪（保留最近 20 条） ----
    k = settings.MEMORY_MAX_MESSAGES
    if len(raw_messages) > k:
        trimmed = raw_messages[-k:]
    else:
        trimmed = list(raw_messages)

    # ---- 第二重：Token 预算裁剪 ----
    token_limit = settings.MEMORY_MAX_TOKENS

    # 先计算 system_prompt 的 Token
    system_tokens = 0
    if system_prompt:
        system_tokens = count_tokens(SystemMessage(content=system_prompt))

    available = token_limit - system_tokens
    if available <= 0:
        # 连 system prompt 都超了，只保留 system prompt
        if system_prompt:
            return [SystemMessage(content=system_prompt)]
        return []

    # 从旧到新逐条移除，直到总 Token ≤ available
    while trimmed:
        total = sum(count_tokens(m) for m in trimmed)
        if total <= available:
            break
        # 移除最旧的一条
        trimmed.pop(0)

    # ---- 保存裁剪后的历史回 Redis ----
    if len(trimmed) != len(raw_messages):
        history.clear()
        for m in trimmed:
            history.add_message(m)

    # ---- 在最前面插入 system prompt（不存入 Redis） ----
    result: list[BaseMessage] = []
    if system_prompt:
        result.append(SystemMessage(content=system_prompt))
    result.extend(trimmed)

    return result


async def save_message(
    user_id: int,
    session_id: str,
    human_message: str | HumanMessage,
    ai_message: str | AIMessage,
) -> None:
    """保存一轮对话到 Redis。"""
    history = get_history(user_id, session_id)
    if isinstance(human_message, str):
        history.add_message(HumanMessage(content=human_message))
    else:
        history.add_message(human_message)
    if isinstance(ai_message, str):
        history.add_message(AIMessage(content=ai_message))
    else:
        history.add_message(ai_message)

    # 写入后再次 K 裁剪
    await _trim_by_count(history, settings.MEMORY_MAX_MESSAGES)


async def clear_history(user_id: int, session_id: str) -> None:
    """清除指定会话的全部历史。"""
    history = get_history(user_id, session_id)
    history.clear()


# ════════════════════════════════════════════════════════════
# Token 计数 & 辅助
# ════════════════════════════════════════════════════════════

def count_tokens(message: BaseMessage) -> int:
    """
    计算单条消息的 Token 数。
    cl100k_base 对中文 ≈ 0.6~1.2 token/字，对英文 ≈ 0.25 token/字。
    """
    content = message.content if isinstance(message.content, str) else str(message.content)
    try:
        return len(_tokenizer.encode(content))
    except Exception:
        # fallback：粗略按字符数估算
        return max(1, len(content) // 2)


def estimate_total_tokens(messages: list[BaseMessage]) -> int:
    """估算消息列表总 Token。"""
    return sum(count_tokens(m) for m in messages)


async def _trim_by_count(history: RedisChatMessageHistory, max_count: int) -> None:
    """消息数量超过上限时从旧到新裁剪。"""
    msgs = history.messages
    if len(msgs) > max_count:
        # RedisChatMessageHistory 没有裁剪方法，采用 clear + 重写
        trimmed = msgs[-max_count:]
        history.clear()
        for m in trimmed:
            history.add_message(m)
