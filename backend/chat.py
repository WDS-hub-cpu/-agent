import uuid
from dotenv import load_dotenv
from pathlib import Path
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from agent import run_agent
from memory import RedisMemory
from auth import set_user_role, get_user_name

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

router = APIRouter(prefix="/chat", tags=["AI 对话"])

# 全局记忆管理器
memory = RedisMemory()


def _current_user() -> str | None:
    """获取当前登录用户名（从 JWT 中间件注入的 contextvars）"""
    return get_user_name()


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户输入的消息", min_length=1, max_length=4096)
    session_id: str | None = Field(
        default=None,
        description="会话 ID，用于隔离多轮对话。不传则自动生成新会话。",
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Agent 的回复（经过 ReAct 推理链）")
    session_id: str = Field(..., description="当前会话 ID，后续请求传入同一个以保持上下文")


@router.post("", response_model=ChatResponse, summary="ReAct Agent 对话（按用户隔离记忆 + 角色权限）")
async def chat(
    request: ChatRequest,
    user_role: str | None = Header(None, alias="User-Role", description="用户角色，如 华东区专员"),
):
    """
    通过 ReAct Agent 处理用户消息，Redis 持久化记忆按用户隔离。

    - **session_id**: 传入已有会话 ID 可延续对话；不传自动创建
    - **User-Role** (Header): 控制数据访问权限
    - 不同用户之间的对话历史相互隔离
    """
    username = _current_user()
    if user_role:
        set_user_role(user_role.strip())

    session_id = request.session_id or str(uuid.uuid4())

    chat_history = memory.get_messages_for_agent(session_id, username)
    memory.add_user_message(session_id, request.message, username)
    reply = run_agent(request.message, chat_history)
    memory.add_assistant_message(session_id, reply, username)

    return ChatResponse(reply=reply, session_id=session_id)


@router.get("/sessions", summary="获取当前用户的会话列表")
async def list_sessions():
    """返回当前用户的历史会话摘要（按时间倒序），用于前端侧边栏"""
    return {"sessions": memory.list_sessions(_current_user())}


@router.get("/session/{session_id}/messages", summary="获取会话完整消息")
async def get_session_messages(session_id: str):
    """返回指定 session 的完整对话历史消息列表"""
    return {"messages": memory.get_history(session_id, _current_user())}


@router.get("/session/{session_id}", summary="查看会话统计")
async def get_session_stats(session_id: str):
    """查询指定 session 的消息数量和预估 Token 数"""
    return memory.get_stats(session_id, _current_user())


@router.delete("/session/{session_id}", summary="清除会话记忆")
async def clear_session(session_id: str):
    """删除指定 session 的全部对话历史"""
    memory.clear(session_id, _current_user())
    return {"success": True, "message": f"会话 {session_id} 已清除"}
