"""
Redis 持久化记忆模块

功能:
- 按 session_id 隔离不同用户的对话历史
- 最多保留最近 20 条消息
- Token 超限时自动截断旧消息
- Redis 不可用时自动降级为内存存储（有警告提示）
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("memory")


# 默认配置
MAX_MESSAGES = 20        # 每个 session 最多保留的消息条数
MAX_TOKENS = 4000        # Token 上限（触发截断）
CHARS_PER_TOKEN = 2      # 中文场景: 约 2 个字符 ≈ 1 个 token


class RedisMemory:
    """基于 Redis 的对话记忆管理器，不可用时自动降级为内存存储"""

    def __init__(
        self,
        redis_url: str | None = None,
        max_messages: int = MAX_MESSAGES,
        max_tokens: int = MAX_TOKENS,
        ttl: int = 86400,  # 24 小时过期
    ):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.ttl = ttl
        self._fallback: dict[str, list[dict]] = {}  # 内存降级存储

        # 尝试连接 Redis
        try:
            import redis
            from config import REDIS_URL as cfg_redis_url
            url = redis_url or cfg_redis_url
            self.client = redis.from_url(
                url, decode_responses=True,
                socket_connect_timeout=2,
                protocol=2,  # Redis 3.x 兼容（RESP2 协议）
            )
            self.client.ping()  # 测试连接
            self._use_redis = True
            logger.info(f"✅ Redis 连接成功: {url}")
        except Exception as e:
            self.client = None
            self._use_redis = False
            logger.warning(
                f"⚠️ Redis 不可用 ({e})，降级为内存存储。"
                f"内存存储不持久化，重启后历史丢失。"
                f"请用 Docker 启动: docker run -d --name redis -p 6379:6379 redis:7-alpine"
            )

    # ---------- 键名生成（按用户隔离） ----------
    def _key(self, session_id: str, username: str | None = None) -> str:
        if username:
            return f"chat:user:{username}:session:{session_id}"
        return f"chat:session:{session_id}"

    def _index_key(self, username: str | None = None) -> str:
        if username:
            return f"chat:user:{username}:sessions"
        return "chat:sessions"

    # ----------------------------------------------------------------
    # 读取历史
    # ----------------------------------------------------------------
    def get_history(self, session_id: str, username: str | None = None) -> list[dict]:
        key = self._key(session_id, username)
        if self._use_redis:
            try:
                data = self.client.get(key)
                if data:
                    return json.loads(data)
                return []
            except Exception:
                pass
        return self._fallback.get(key, [])

    def get_messages_for_agent(self, session_id: str, username: str | None = None) -> list[dict]:
        return self.get_history(session_id, username)

    # ----------------------------------------------------------------
    # 写入消息
    # ----------------------------------------------------------------
    def add_message(self, session_id: str, role: str, content: str, username: str | None = None) -> None:
        history = self.get_history(session_id, username)
        history.append({"role": role, "content": content})

        if len(history) > self.max_messages:
            history = history[-self.max_messages:]

        history = self._truncate_by_tokens(history)

        key = self._key(session_id, username)
        if self._use_redis:
            try:
                self.client.set(key, json.dumps(history, ensure_ascii=False), ex=self.ttl)
            except Exception:
                pass
        else:
            self._fallback[key] = history

        self._track_session(session_id, username)

    def add_user_message(self, session_id: str, content: str, username: str | None = None) -> None:
        self.add_message(session_id, "user", content, username)

    def add_assistant_message(self, session_id: str, content: str, username: str | None = None) -> None:
        self.add_message(session_id, "assistant", content, username)

    # ----------------------------------------------------------------
    # Token 估算与截断
    # ----------------------------------------------------------------
    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // CHARS_PER_TOKEN)

    def _total_tokens(self, history: list[dict]) -> int:
        return sum(self._estimate_tokens(msg["content"]) for msg in history)

    def _truncate_by_tokens(self, history: list[dict]) -> list[dict]:
        while self._total_tokens(history) > self.max_tokens and len(history) > 2:
            history.pop(0)
        return history

    # ----------------------------------------------------------------
    # 管理操作
    # ----------------------------------------------------------------
    def clear(self, session_id: str, username: str | None = None) -> None:
        key = self._key(session_id, username)
        ik = self._index_key(username)
        if self._use_redis:
            try:
                self.client.delete(key)
                self.client.zrem(ik, session_id)
            except Exception:
                pass
        self._fallback.pop(key, None)

    def list_sessions(self, username: str | None = None) -> list[dict]:
        """列出当前用户的所有会话（按时间倒序）"""
        sessions = []
        ik = self._index_key(username)
        if self._use_redis:
            try:
                ids = self.client.zrevrange(ik, 0, 99)
                for sid in ids:
                    history = self.get_history(sid, username)
                    first_msg = ""
                    for m in history:
                        if m["role"] == "user":
                            first_msg = m["content"][:40]
                            break
                    sessions.append({
                        "session_id": sid,
                        "title": first_msg or "(空会话)",
                        "message_count": len(history),
                    })
                return sessions
            except Exception:
                pass
        prefix = f"chat:user:{username}:" if username else "chat"
        for key, history in list(self._fallback.items()):
            if not username or key.startswith(prefix):
                sid = key.rsplit(":session:", 1)[-1] if ":session:" in key else key
                first_msg = ""
                for m in history:
                    if m["role"] == "user":
                        first_msg = m["content"][:40]
                        break
                sessions.append({
                    "session_id": sid,
                    "title": first_msg or "(空会话)",
                    "message_count": len(history),
                })
        sessions.sort(key=lambda s: s["session_id"], reverse=True)
        return sessions

    def _track_session(self, session_id: str, username: str | None = None) -> None:
        """在 session 索引中记录此会话"""
        import time
        score = time.time()
        ik = self._index_key(username)
        if self._use_redis:
            try:
                self.client.zadd(ik, {session_id: score})
            except Exception:
                pass

    def session_exists(self, session_id: str, username: str | None = None) -> bool:
        key = self._key(session_id, username)
        if self._use_redis:
            try:
                return bool(self.client.exists(key))
            except Exception:
                pass
        return key in self._fallback

    def get_stats(self, session_id: str, username: str | None = None) -> dict:
        history = self.get_history(session_id, username)
        ttl_val = -1
        if self._use_redis:
            try:
                ttl_val = self.client.ttl(self._key(session_id, username))
            except Exception:
                pass
        return {
            "session_id": session_id,
            "message_count": len(history),
            "estimated_tokens": self._total_tokens(history),
            "ttl_seconds": ttl_val,
            "storage": "redis" if self._use_redis else "memory（重启丢失）",
        }
