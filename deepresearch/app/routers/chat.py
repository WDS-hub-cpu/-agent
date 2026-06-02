# ============================================================
# 路由: 智能对话接口 (POST /chat) — 支持流式 SSE
# ============================================================
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.dependencies.auth import get_current_user
from app.utils.context import RequestUser
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatHistoryInfo,
)
from app.agents.agent_executor import run_agent, run_agent_stream
from app.agents.memory_manager import (
    get_history,
    clear_history,
    estimate_total_tokens,
)

router = APIRouter(prefix="/chat", tags=["Chat Agent"])


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: RequestUser = Depends(get_current_user),
):
    """
    同步对话接口（非流式）。
    返回完整回答，适用于批处理或调试场景。
    """
    answer = await run_agent(
        user_message=payload.message,
        user_id=current_user.user_id,
        session_id=payload.session_id,
    )
    history = get_history(current_user.user_id, payload.session_id)
    return ChatResponse(
        answer=answer,
        session_id=payload.session_id,
        message_count=len(history.messages),
    )


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: RequestUser = Depends(get_current_user),
):
    """
    流式对话接口（SSE）。
    返回 text/event-stream，前端可逐 Token 渲染。

    使用方式（curl）:
      curl -X POST http://localhost:8000/chat/stream \
        -H "Authorization: Bearer token-admin-001" \
        -H "Content-Type: application/json" \
        -d '{"message":"华东区域季度销售情况如何？","session_id":"demo-session"}' \
        --no-buffer
    """
    async def event_generator():
        try:
            async for token in run_agent_stream(
                user_message=payload.message,
                user_id=current_user.user_id,
                session_id=payload.session_id,
            ):
                # SSE 格式: data: <content>\n\n
                yield f"data: {token}\n\n"
            # 结束标记
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.get("/history/{session_id}", response_model=ChatHistoryInfo)
async def get_chat_history(
    session_id: str,
    current_user: RequestUser = Depends(get_current_user),
):
    """查看指定会话的历史消息信息。"""
    history = get_history(current_user.user_id, session_id)
    messages = history.messages
    return ChatHistoryInfo(
        session_id=session_id,
        message_count=len(messages),
        token_estimate=estimate_total_tokens(messages),
    )


@router.delete("/history/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    session_id: str,
    current_user: RequestUser = Depends(get_current_user),
):
    """清除指定会话的全部历史消息。"""
    await clear_history(current_user.user_id, session_id)
