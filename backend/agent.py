"""
ReAct Agent — 结合 Qwen 大模型 + 销售数据工具

Agent 范式: Thought → Action → Observation → Final Answer
终端日志 (debug=True) 会展示完整推理过程。

LangChain 1.3.x 新 API: create_agent (替代旧的 create_tool_calling_agent + AgentExecutor)
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from tools import query_sales_data, calculate_trend

# 加载项目根目录 .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ============================================================
# Tool 包装（转为 LangChain Tool）
# ============================================================

@tool
def query_sales_data_tool(sql: str) -> str:
    """
    在 MySQL 的 sales_data 表上执行 SELECT 查询，返回销售数据。

    表名: sales_data
    可用字段:
    - sale_date (日期)        - product_name (产品名称)
    - category (产品类别)      - region (大区: 华东/华南/华北/华中/西南/西北)
    - city (城市)             - sales_amount (销售额/元)
    - profit (利润/元)         - quantity (销售数量)
    - unit_price (单价/元)     - channel (销售渠道: 线上/线下)
    - salesperson (销售员)

    SQL 示例:
    - 查华东区总销售额:
      SELECT region, SUM(sales_amount) AS total_sales FROM sales_data WHERE region='华东' GROUP BY region
    - 查最近销售明细:
      SELECT sale_date, product_name, region, sales_amount FROM sales_data ORDER BY sale_date DESC LIMIT 10
    - 按产品类别汇总:
      SELECT category, SUM(sales_amount) AS total, COUNT(*) AS cnt FROM sales_data GROUP BY category ORDER BY total DESC
    """
    result = query_sales_data(sql)
    if result["success"]:
        return (
            f"查询成功，共 {result['row_count']} 条记录。\n"
            f"列: {result['columns']}\n"
            f"数据: {result['rows']}"
        )
    else:
        return f"查询失败: {result['error']}"


@tool
def calculate_trend_tool(data: str) -> str:
    """
    对一组数值进行趋势分析，计算均值、中位数、标准差、环比增长率、趋势方向等。

    参数 data: 逗号分隔的数值字符串，例如 "1200,1350,1180,1500,1620"。
    通常先通过 query_sales_data_tool 查到数值列，再提取数值传入本工具。
    """
    try:
        numbers = [float(x.strip()) for x in data.split(",") if x.strip()]
    except ValueError:
        return "错误: 无法解析，请传入逗号分隔的纯数值，如 '100,200,150'。"

    if not numbers:
        return "错误: 没有有效数值。"

    result = calculate_trend(numbers)
    if result["success"]:
        return (
            f"📊 趋势分析结果 (共 {result['count']} 个数据点):\n"
            f"  • 均值: {result['mean']}\n"
            f"  • 中位数: {result['median']}\n"
            f"  • 最大值: {result['max']}\n"
            f"  • 最小值: {result['min']}\n"
            f"  • 标准差: {result['std']}\n"
            f"  • 总和: {result['total']}\n"
            f"  • 环比增长率(%): {result['growth_rates']}\n"
            f"  • 趋势方向: {result['trend_direction']}"
        )
    else:
        return f"计算失败: {result['error']}"


# ============================================================
# ReAct Agent 组装（LangChain 1.3.x 新版 API）
# ============================================================

tools = [query_sales_data_tool, calculate_trend_tool]

llm = ChatOpenAI(
    model=os.getenv("QWEN_MODEL", "qwen-plus"),
    api_key=os.getenv("QWEN_API_KEY", "sk-your-api-key-here"),
    base_url=os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    temperature=0.1,  # Agent 场景用低温度，确保工具调用稳定
)

# ReAct 范式 System Prompt
system_prompt = (
    "你是一个专业的销售数据分析助手，可以直接查询 MySQL 数据库中的 sales_data 表。\n\n"
    "## 工作流程 (ReAct)\n"
    "1. **Thought**（思考）: 理解用户问题，拆解为具体的数据查询需求\n"
    "2. **Action**（行动）: 调用 query_sales_data_tool 执行 SQL 查询\n"
    "3. **Observation**（观察）: 分析查询结果，必要时用 calculate_trend_tool 做趋势分析\n"
    "4. **Final Answer**（最终回答）: 用自然语言清晰、有条理地总结分析结果\n\n"
    "## 重要规则\n"
    "- 涉及数据查询时，**必须先调用 query_sales_data_tool**，不要凭空编造数据\n"
    "- SQL 查询请写完整、合法的 SELECT 语句\n"
    "- region 可用值: 华东、华南、华北、华中、西南、西北\n"
    "- 如果用户只问「销售额」，默认指 sales_amount 字段\n"
    "- 查询结果用中文回复，适当使用数字和结构化的格式\n"
    "- 如果查询返回空，告知用户未找到匹配数据，建议调整条件"
)

# LangChain 1.3.x: create_agent 取代 create_tool_calling_agent + AgentExecutor
agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=system_prompt,
    debug=True,  # ✅ 控制台打印 Thought → Action → Observation 完整日志
)


def run_agent(message: str, chat_history: list[dict] | None = None) -> str:
    """
    执行 ReAct Agent，支持带历史记忆的对话。

    参数:
        message: 用户当前自然语言问题
        chat_history: 历史消息列表，格式 [{"role": "user/assistant", "content": "..."}, ...]

    返回:
        Agent 的最终回答文本
    """
    # 组装消息列表：历史 + 当前问题
    messages = []
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                messages.append({"role": role, "content": content})
    # 追加当前用户消息
    messages.append({"role": "user", "content": message})

    result = agent.invoke({"messages": messages})

    # 提取最后一条 AI 消息作为回复
    all_messages = result.get("messages", [])
    for msg in reversed(all_messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return "Agent 未生成有效回复。"

