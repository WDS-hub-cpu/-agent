# ============================================================
# 智能销售分析系统 — 配置文件
# ============================================================
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ---------- 应用 ----------
    APP_NAME: str = "Sales Analysis Agent System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ---------- MySQL ----------
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_DATABASE: str = "sales_db"
    MYSQL_POOL_SIZE: int = 20
    MYSQL_MAX_OVERFLOW: int = 40
    MYSQL_POOL_RECYCLE: int = 3600

    # ---------- Redis ----------
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_POOL_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5

    # ---------- LLM: Qwen (OpenAI 兼容接口 / DashScope) ----------
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "qwen-max"
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 4096

    # ---------- Agent 记忆管理 ----------
    MEMORY_MAX_MESSAGES: int = 20         # 最大保留消息数（K）
    MEMORY_MAX_TOKENS: int = 8000         # 历史消息总 Token 上限
    MEMORY_REDIS_TTL: int = 86400         # Redis 会话过期时间（秒），默认 24 小时

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    @property
    def redis_dsn(self) -> str:
        base = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        if self.REDIS_PASSWORD:
            base = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return base

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
