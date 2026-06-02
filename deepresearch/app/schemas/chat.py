# ============================================================
# Pydantic Schema: 聊天请求 / 响应
# ============================================================
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入的消息", min_length=1, max_length=4000)
    session_id: str = Field(
        default="default",
        description="会话 ID，同一会话内保持上下文连续。传入新值即开始新会话。",
        max_length=128,
    )


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    message_count: int = 0


class ChatHistoryClearRequest(BaseModel):
    session_id: str = Field(default="default", max_length=128)


class ChatHistoryInfo(BaseModel):
    session_id: str
    message_count: int
    token_estimate: int
