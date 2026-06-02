# ============================================================
# ReAct Agent 执行器
# · 绑定 5 个销售分析工具
# · 注入裁剪后的历史消息
# · 支持流式输出
# ============================================================
from __future__ import annotations

from typing import AsyncIterator

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from app.agents.llm import get_llm
from app.agents.sales_tools import SALES_TOOLS
from app.agents.memory_manager import load_and_trim_history, save_message

# ---------- System Prompt（≤200 Tokens，Thought-Action-Observation 链） ----------
SYSTEM_PROMPT = """你是资深销售数据分析专家。严格遵循 思考→行动→观察 推理链：

【思考】分析用户意图，确定需要什么维度的数据。
【行动】从以下工具中选择最匹配的一个调用（每次只选一个）：
  · 查明细 → query_sales_data
  · 算统计 → calculate_statistics
  · 看趋势 → analyze_trends
  · 画图表 → generate_chart_data
  · 找异常 → detect_anomalies
【观察】解读工具返回的数据，判断是否需要进一步调用其他工具，或直接给出最终结论。

输出准则：用流畅中文呈现分析结果；金额以万元为单位；主动提炼业务洞察；未明确要求图表时不要生成图表。"""


# ════════════════════════════════════════════════════════════
# Agent 实例（懒加载 + 缓存）
# ════════════════════════════════════════════════════════════

_agent = None


def _get_react_agent():
    """
    创建 ReAct Agent（单例）。
    system prompt 已内嵌在工具描述和 prompt 中，运行时动态拼接历史。
    """
    global _agent
    if _agent is None:
        llm = get_llm()
        _agent = create_react_agent(
            model=llm,
            tools=SALES_TOOLS,
            prompt=SYSTEM_PROMPT,
        )
    return _agent


# ════════════════════════════════════════════════════════════
# 对外执行接口
# ════════════════════════════════════════════════════════════

async def run_agent(
    user_message: str,
    user_id: int,
    session_id: str,
) -> str:
    """
    同步执行 Agent（非流式），返回完整答案。
    """
    agent = _get_react_agent()

    # 加载 & 裁剪历史
    history = await load_and_trim_history(user_id, session_id, system_prompt=SYSTEM_PROMPT)
    history.append(HumanMessage(content=user_message))

    # 执行
    result = await agent.ainvoke({"messages": history})
    output_messages = result.get("messages", [])
    answer = _extract_final_answer(output_messages)

    # 保存对话
    await save_message(user_id, session_id, user_message, answer)

    return answer


async def run_agent_stream(
    user_message: str,
    user_id: int,
    session_id: str,
) -> AsyncIterator[str]:
    """
    流式执行 Agent，逐 Token 返回答案文本。
    使用 astream_events 获取流式事件。
    """
    agent = _get_react_agent()

    # 加载 & 裁剪历史
    history = await load_and_trim_history(user_id, session_id, system_prompt=SYSTEM_PROMPT)
    history.append(HumanMessage(content=user_message))

    # 流式执行
    full_answer_parts: list[str] = []

    async for event in agent.astream_events(
        {"messages": history},
        version="v2",
    ):
        kind = event.get("event", "")
        # 仅捕获 LLM 的流式文本输出
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                token_text = chunk.content
                if isinstance(token_text, str):
                    full_answer_parts.append(token_text)
                    yield token_text

    # 保存对话（流式结束后）
    full_answer = "".join(full_answer_parts)
    if full_answer.strip():
        await save_message(user_id, session_id, user_message, full_answer)


# ════════════════════════════════════════════════════════════
# 辅助
# ════════════════════════════════════════════════════════════

def _extract_final_answer(messages: list[BaseMessage]) -> str:
    """从 Agent 输出的消息列表中提取最后一条 AI 回答。"""
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            return str(m.content)
    return "抱歉，未能生成回答。"
