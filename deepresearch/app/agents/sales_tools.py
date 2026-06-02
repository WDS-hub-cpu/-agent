# ============================================================
# LangChain 销售分析工具集（5 个 @tool）
# 所有输出均为结构化自然语言，对 LLM 友好
# ============================================================
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from typing import Optional

from langchain_core.tools import tool

from app.utils.context import get_current_user

# ════════════════════════════════════════════════════════════
# 自然语言格式化工具函数
# ════════════════════════════════════════════════════════════

def _fmt_money(amount: float) -> str:
    """金额 → 中文可读（万元）。"""
    wan = amount / 10000
    if abs(wan) >= 1:
        return f"{wan:,.2f} 万元"
    return f"{amount:,.2f} 元"


def _fmt_percent(value: float, decimals: int = 1) -> str:
    """小数 → 百分比字符串。"""
    return f"{value * 100:,.{decimals}f}%"


def _fmt_date(d: date) -> str:
    return d.strftime("%Y年%m月%d日")


def _fmt_month(d: date) -> str:
    return d.strftime("%Y年%m月")


# ════════════════════════════════════════════════════════════
# 工具 1：多条件查询销售数据
# ════════════════════════════════════════════════════════════

@tool
def query_sales_data(
    region: Optional[str] = None,
    product: Optional[str] = None,
    customer_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    limit: int = 10,
) -> str:
    """
    【正向能力】查询具体时间段的销售明细记录，获取订单ID、客户名称、金额、
    区域、产品等字段。支持按区域、产品、客户、日期区间、金额区间等多条件组合筛选。

    【反向排除】
    - 如需计算总额、平均值、最值等统计指标 → 请使用 calculate_statistics
    - 如需对比不同时期的涨跌幅或走势 → 请使用 analyze_trends
    - 本工具只返回原始明细，不计算任何衍生指标

    参数:
        region: 区域名称，如 "华东"、"华南"
        product: 产品名称，如 "智能手表"、"蓝牙耳机"
        customer_name: 客户名称（支持模糊匹配）
        start_date: 起始日期，格式 YYYY-MM-DD
        end_date: 截止日期，格式 YYYY-MM-DD
        min_amount: 最低订单金额
        max_amount: 最高订单金额
        limit: 返回记录条数上限，默认 10
    """
    # ---------- Mock 数据（实际项目中替换为 SalesService 查询） ----------
    mock = _mock_sales_dataset()
    results = mock

    # 模拟过滤
    if region:
        results = [r for r in results if region in r["region"]]
    if product:
        results = [r for r in results if product in r["product"]]
    if customer_name:
        results = [r for r in results if customer_name in r["customer_name"]]
    if start_date:
        sd = date.fromisoformat(start_date)
        results = [r for r in results if r["order_date"] >= sd]
    if end_date:
        ed = date.fromisoformat(end_date)
        results = [r for r in results if r["order_date"] <= ed]
    if min_amount is not None:
        results = [r for r in results if r["amount"] >= min_amount]
    if max_amount is not None:
        results = [r for r in results if r["amount"] <= max_amount]

    results = results[:limit]

    # ---------- 构建自然语言输出 ----------
    conditions_parts = []
    if region:
        conditions_parts.append(f"区域「{region}」")
    if product:
        conditions_parts.append(f"产品「{product}」")
    if customer_name:
        conditions_parts.append(f"客户「{customer_name}」")
    if start_date:
        conditions_parts.append(f"从 {start_date} 起")
    if end_date:
        conditions_parts.append(f"至 {end_date} 止")
    if min_amount is not None:
        conditions_parts.append(f"金额不低于 {_fmt_money(min_amount)}")
    if max_amount is not None:
        conditions_parts.append(f"金额不超过 {_fmt_money(max_amount)}")

    cond_str = "、".join(conditions_parts) if conditions_parts else "全部条件"

    if not results:
        return f"根据查询条件（{cond_str}），未找到匹配的销售记录。"

    lines = [f"根据查询条件（{cond_str}），共找到 {len(results)} 条销售记录，具体如下：", ""]
    total = 0.0
    for i, r in enumerate(results, 1):
        lines.append(
            f"  {i}. 订单「{r['order_id']}」— {_fmt_date(r['order_date'])}，"
            f"客户「{r['customer_name']}」在「{r['region']}」区域购买了「{r['product']}」，"
            f"金额为 {_fmt_money(r['amount'])}。"
        )
        total += r["amount"]
    lines.append("")
    lines.append(f"以上记录合计金额为 {_fmt_money(total)}。")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 工具 2：统计汇总
# ════════════════════════════════════════════════════════════

@tool
def calculate_statistics(
    region: Optional[str] = None,
    product: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: Optional[str] = None,
) -> str:
    """
    【正向能力】对销售数据进行统计汇总计算，输出总销售额、平均订单金额、
    订单总数、最高/最低订单。支持按区域（region）或产品（product）分组汇总。

    【反向排除】
    - 如需逐条查看订单明细 → 请使用 query_sales_data
    - 如需计算环比/同比涨跌幅或走势判断 → 请使用 analyze_trends
    - 本工具只做静态统计（某一时段的汇总值），不做跨时段对比

    参数:
        region: 按区域筛选
        product: 按产品筛选
        start_date: 起始日期 YYYY-MM-DD
        end_date: 截止日期 YYYY-MM-DD
        group_by: 分组维度，可选 "region" 或 "product"
    """
    mock = _mock_sales_dataset()
    data = mock

    # 过滤
    if region:
        data = [r for r in data if region in r["region"]]
    if product:
        data = [r for r in data if product in r["product"]]
    if start_date:
        sd = date.fromisoformat(start_date)
        data = [r for r in data if r["order_date"] >= sd]
    if end_date:
        ed = date.fromisoformat(end_date)
        data = [r for r in data if r["order_date"] <= ed]

    if not data:
        return "当前筛选条件下暂无销售数据，无法进行统计汇总。"

    # 过滤条件描述
    filter_desc = _build_filter_desc(region, product, start_date, end_date)

    if group_by in ("region", "product"):
        return _stats_grouped(data, group_by, filter_desc)
    else:
        return _stats_overall(data, filter_desc)


def _stats_overall(data: list[dict], filter_desc: str) -> str:
    amounts = [r["amount"] for r in data]
    total = sum(amounts)
    avg = total / len(amounts)
    max_r = max(data, key=lambda r: r["amount"])
    min_r = min(data, key=lambda r: r["amount"])
    return (
        f"在{filter_desc}条件下，销售统计汇总如下：\n"
        f"  • 订单总数：{len(data)} 笔\n"
        f"  • 总销售额：{_fmt_money(total)}\n"
        f"  • 平均订单金额：{_fmt_money(avg)}\n"
        f"  • 最高订单：{_fmt_date(max_r['order_date'])} 客户「{max_r['customer_name']}」"
        f"购买的「{max_r['product']}」，金额 {_fmt_money(max_r['amount'])}\n"
        f"  • 最低订单：{_fmt_date(min_r['order_date'])} 客户「{min_r['customer_name']}」"
        f"购买的「{min_r['product']}」，金额 {_fmt_money(min_r['amount'])}"
    )


def _stats_grouped(data: list[dict], group_by: str, filter_desc: str) -> str:
    groups: dict[str, list[dict]] = {}
    for r in data:
        key = r[group_by]
        groups.setdefault(key, []).append(r)

    lines = [f"在{filter_desc}条件下，按「{group_by}」分组统计如下：", ""]
    grand_total = 0.0
    for key, items in groups.items():
        total = sum(it["amount"] for it in items)
        avg = total / len(items)
        grand_total += total
        lines.append(
            f"  【{key}】订单 {len(items)} 笔，总销售额 {_fmt_money(total)}，"
            f"平均每笔 {_fmt_money(avg)}。"
        )
    lines.append("")
    lines.append(f"各组合计总销售额为 {_fmt_money(grand_total)}。")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 工具 3：同比/环比趋势分析
# ════════════════════════════════════════════════════════════

@tool
def analyze_trends(
    period: str = "monthly",
    compare_type: str = "mom",
    months: int = 6,
) -> str:
    """
    【正向能力】分析销售额随时间的变化趋势，计算环比（MoM，较上月）或
    同比（YoY，较去年同期）的涨跌幅百分比。按月或周粒度输出每期变化方向
    （增长/下降）及幅度，并给出整体走势判断（上升、下滑或平稳）。

    【反向排除】
    - 如需查看某个时间点的绝对销售额 → 请使用 calculate_statistics
    - 如需生成 ECharts 图表 JSON 供前端渲染 → 请使用 generate_chart_data
    - 本工具只输出趋势文字描述，不生成图表代码

    参数:
        period: 时间粒度，可选 "monthly"（按月）或 "weekly"（按周）
        compare_type: 对比方式，可选 "mom"（环比）或 "yoy"（同比）
        months: 回溯月份数，默认最近 6 个月
    """
    # ---------- Mock 月度趋势数据 ----------
    today = date.today()
    mock_monthly = _mock_monthly_trend(today, months)

    if period == "weekly":
        # 按周聚合（简化为 4 周 = 1 个月做演示）
        mock_monthly = _monthly_to_weekly(mock_monthly)

    # ---------- 构建自然语言趋势报告 ----------
    period_label = "月" if period == "monthly" else "周"
    compare_label = "环比" if compare_type == "mom" else "同比"

    lines = [f"以下是最近 {len(mock_monthly)} 个{period_label}的销售额趋势（{compare_label}）分析：", ""]

    prev_amount: float | None = None
    trends: list[dict] = []

    for i, item in enumerate(mock_monthly):
        current = item["amount"]
        label = item["label"]

        if prev_amount is not None and prev_amount > 0:
            change = (current - prev_amount) / prev_amount
            if compare_type == "yoy":
                # 同比：与去年同期对比（Mock 模拟）
                yoy_amount = prev_amount * (0.7 + 0.6 * (i % 3) / 3)  # 模拟波动
                change = (current - yoy_amount) / yoy_amount if yoy_amount > 0 else 0

            direction = "增长" if change > 0 else "下降"
            lines.append(
                f"  {label}：销售额 {_fmt_money(current)}，"
                f"较上期{compare_label}{direction} {_fmt_percent(abs(change))}。"
            )
        else:
            lines.append(f"  {label}：销售额 {_fmt_money(current)}（基准期）。")

        prev_amount = current
        trends.append({"label": label, "amount": current})

    # 整体趋势判断
    if len(trends) >= 2:
        first = trends[0]["amount"]
        last = trends[-1]["amount"]
        overall_change = (last - first) / first if first > 0 else 0
        if overall_change > 0.05:
            verdict = f"整体呈上升趋势，期内累计增长 {_fmt_percent(overall_change)}，势头良好。"
        elif overall_change < -0.05:
            verdict = f"整体呈下滑趋势，期内累计下降 {_fmt_percent(abs(overall_change))}，需要引起关注。"
        else:
            verdict = "整体趋势平稳，波动幅度较小。"
        lines.append("")
        lines.append(f"📊 趋势判断：{verdict}")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 工具 4：生成 ECharts 图表数据
# ════════════════════════════════════════════════════════════

@tool
def generate_chart_data(
    chart_type: str = "bar",
    dimension: str = "region",
    metric: str = "total_amount",
    top_n: int = 10,
) -> str:
    """
    【正向能力】生成前端 ECharts 可直接渲染的柱状图（bar）、饼图（pie）或
    折线图（line）JSON 配置。按区域、产品或月份维度聚合数据，返回图表 JSON
    并附带简要文字摘要。

    【反向排除】
    - 如需获取原始数值做进一步计算 → 请使用 query_sales_data 或 calculate_statistics
    - 如需分析趋势或涨跌幅 → 请使用 analyze_trends
    - 本工具只生成可视化图表 JSON，不做数值统计或趋势判断

    参数:
        chart_type: 图表类型，可选 "bar"（柱状图）、"pie"（饼图）、"line"（折线图）
        dimension: 分析维度，可选 "region"、"product"、"month"
        metric: 指标，可选 "total_amount"（总额）、"order_count"（订单数）
        top_n: 展示前 N 条数据
    """
    mock = _mock_sales_dataset()

    # 按维度聚合
    agg: dict[str, dict] = {}
    for r in mock:
        if dimension == "month":
            key = r["order_date"].strftime("%Y-%m")
        else:
            key = r[dimension]
        if key not in agg:
            agg[key] = {"total_amount": 0.0, "order_count": 0}
        agg[key]["total_amount"] += r["amount"]
        agg[key]["order_count"] += 1

    # 排序取 Top N
    sorted_items = sorted(agg.items(), key=lambda x: x[1][metric], reverse=True)[:top_n]

    labels = [k for k, _ in sorted_items]
    values = [v[metric] for _, v in sorted_items]

    # ---------- 构建 ECharts option JSON ----------
    option = {
        "tooltip": {"trigger": "axis" if chart_type == "bar" else "item"},
        "legend": {"data": [metric]},
    }

    if chart_type == "bar":
        option["xAxis"] = {"type": "category", "data": labels}
        option["yAxis"] = {"type": "value", "name": "金额（元）" if metric == "total_amount" else "订单数"}
        option["series"] = [{"name": metric, "type": "bar", "data": values}]
    elif chart_type == "pie":
        option["series"] = [{
            "name": metric,
            "type": "pie",
            "radius": "60%",
            "data": [{"name": k, "value": v} for k, v in zip(labels, values)],
        }]
    elif chart_type == "line":
        option["xAxis"] = {"type": "category", "data": labels, "boundaryGap": False}
        option["yAxis"] = {"type": "value", "name": "金额（元）" if metric == "total_amount" else "订单数"}
        option["series"] = [{"name": metric, "type": "line", "data": values, "smooth": True,
                              "areaStyle": {"opacity": 0.3}}]

    dim_label = {"region": "区域", "product": "产品", "month": "月份"}.get(dimension, dimension)
    metric_label = {"total_amount": "总销售额", "order_count": "订单数量"}.get(metric, metric)
    chart_label = {"bar": "柱状图", "pie": "饼图", "line": "折线图"}.get(chart_type, chart_type)

    # 自然语言摘要
    summary_lines = [
        f"已为您生成按「{dim_label}」维度的「{metric_label}」{chart_label}数据。",
        f"共包含 {len(sorted_items)} 个{dim_label}的数据，从高到低依次为：",
    ]
    for k, v in sorted_items:
        if metric == "total_amount":
            summary_lines.append(f"  • {k}：{_fmt_money(v[metric])}")
        else:
            summary_lines.append(f"  • {k}：{int(v[metric])} 笔订单")
    summary_lines.append("")

    # 返回自然语言 + ECharts JSON（放在末尾方便前端解析）
    chart_json = json.dumps(option, ensure_ascii=False, indent=2)
    summary_lines.append("【ECharts 配置 JSON】")
    summary_lines.append(chart_json)

    return "\n".join(summary_lines)


# ════════════════════════════════════════════════════════════
# 工具 5：异常检测 / 预警
# ════════════════════════════════════════════════════════════

@tool
def detect_anomalies(
    dimension: str = "product",
    threshold: float = 0.5,
    lookback_weeks: int = 4,
) -> str:
    """
    【正向能力】检测销售数据中的异常波动——按产品或区域维度，对比最近一周
    销售额与历史数周均值的比例。当比例低于阈值（默认 50%）时触发暴跌预警，
    高于 200% 时触发激增关注。输出预警文字，帮助快速定位问题维度。

    【反向排除】
    - 如需了解正常的趋势变化（非异常） → 请使用 analyze_trends
    - 如需查询具体订单明细以排查原因 → 请使用 query_sales_data
    - 本工具只标记异常信号，不提供常规统计或趋势分析

    参数:
        dimension: 检测维度，可选 "product" 或 "region"
        threshold: 异常阈值（0~1），销售额低于均值×threshold 即判定为异常，默认 0.5
        lookback_weeks: 回溯周数，默认 4 周
    """
    # ---------- Mock 周度数据（含一个明显的暴跌） ----------
    mock = _mock_sales_dataset()
    weekly_data = _build_weekly_aggregation(mock, lookback_weeks)

    # 按维度聚合
    dim_groups: dict[str, list[dict]] = {}
    for item in weekly_data:
        key = item[dimension]
        dim_groups.setdefault(key, []).append(item)

    alerts: list[str] = []
    normal_summary: list[str] = []

    for dim_value, weeks in dim_groups.items():
        if len(weeks) < 2:
            continue

        # 最近一周 vs 历史均值
        sorted_weeks = sorted(weeks, key=lambda x: x["week_start"])
        latest = sorted_weeks[-1]
        historical = sorted_weeks[:-1]

        hist_avg = sum(w["amount"] for w in historical) / len(historical) if historical else latest["amount"]
        latest_amount = latest["amount"]

        if hist_avg > 0:
            ratio = latest_amount / hist_avg
            if ratio < threshold:
                drop_pct = (1 - ratio) * 100
                alerts.append(
                    f"⚠️ 预警：「{dim_value}」在最近一周（{_fmt_date(latest['week_start'])} 起）"
                    f"销售额为 {_fmt_money(latest_amount)}，仅为过去 {lookback_weeks - 1} 周"
                    f"均值（{_fmt_money(hist_avg)}）的 {_fmt_percent(ratio)}，"
                    f"暴跌了 {_fmt_percent(drop_pct / 100)}，请立即关注！"
                )
            elif ratio > 2.0:
                surge_pct = (ratio - 1) * 100
                alerts.append(
                    f"📈 关注：「{dim_value}」在最近一周销售额激增至 {_fmt_money(latest_amount)}，"
                    f"是历史均值（{_fmt_money(hist_avg)}）的 {ratio:.1f} 倍，"
                    f"增幅 {_fmt_percent(surge_pct / 100)}，请核实原因。"
                )
            else:
                normal_summary.append(
                    f"「{dim_value}」近一周销售额 {_fmt_money(latest_amount)}，"
                    f"为历史均值的 {_fmt_percent(ratio)}，属于正常波动范围。"
                )

    # ---------- 自然语言报告 ----------
    lines = [f"销售异常检测报告（维度：{dimension}，阈值：{_fmt_percent(threshold)}，回溯 {lookback_weeks} 周）：", ""]

    if alerts:
        lines.append("【异常项】")
        lines.extend(alerts)
        lines.append("")

    if normal_summary:
        lines.append("【正常项】")
        lines.extend(normal_summary)

    if not alerts:
        lines.insert(1, "✅ 未检测到异常，所有维度销售额均在正常范围内。")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# Mock 数据 & 辅助函数
# ════════════════════════════════════════════════════════════

def _mock_sales_dataset() -> list[dict]:
    """模拟销售数据集（30 条记录）。"""
    base = date.today().replace(day=1)
    return [
        # 华东 - 智能手表
        {"order_id": "ORD-1001", "customer_name": "上海恒达科技", "amount": 125000.00,
         "order_date": base - timedelta(days=5), "region": "华东", "product": "智能手表"},
        {"order_id": "ORD-1002", "customer_name": "杭州未来电子", "amount": 89000.00,
         "order_date": base - timedelta(days=12), "region": "华东", "product": "智能手表"},
        {"order_id": "ORD-1003", "customer_name": "南京星辰数码", "amount": 210000.00,
         "order_date": base - timedelta(days=3), "region": "华东", "product": "智能手表"},
        {"order_id": "ORD-1004", "customer_name": "苏州云联科技", "amount": 67000.00,
         "order_date": base - timedelta(days=20), "region": "华东", "product": "蓝牙耳机"},
        {"order_id": "ORD-1005", "customer_name": "合肥智联", "amount": 45000.00,
         "order_date": base - timedelta(days=25), "region": "华东", "product": "蓝牙耳机"},
        # 华南
        {"order_id": "ORD-2001", "customer_name": "深圳华强电子", "amount": 320000.00,
         "order_date": base - timedelta(days=2), "region": "华南", "product": "智能手表"},
        {"order_id": "ORD-2002", "customer_name": "广州天河数码", "amount": 156000.00,
         "order_date": base - timedelta(days=8), "region": "华南", "product": "智能手表"},
        {"order_id": "ORD-2003", "customer_name": "东莞智能制造", "amount": 78000.00,
         "order_date": base - timedelta(days=15), "region": "华南", "product": "蓝牙耳机"},
        {"order_id": "ORD-2004", "customer_name": "佛山创新科技", "amount": 54000.00,
         "order_date": base - timedelta(days=22), "region": "华南", "product": "蓝牙耳机"},
        {"order_id": "ORD-2005", "customer_name": "珠海横琴科技", "amount": 182000.00,
         "order_date": base - timedelta(days=6), "region": "华南", "product": "智能手环"},
        # 华北
        {"order_id": "ORD-3001", "customer_name": "北京中关村科技", "amount": 275000.00,
         "order_date": base - timedelta(days=1), "region": "华北", "product": "智能手表"},
        {"order_id": "ORD-3002", "customer_name": "天津滨海数码", "amount": 93000.00,
         "order_date": base - timedelta(days=10), "region": "华北", "product": "智能手环"},
        {"order_id": "ORD-3003", "customer_name": "石家庄恒信", "amount": 41000.00,
         "order_date": base - timedelta(days=18), "region": "华北", "product": "蓝牙耳机"},
        {"order_id": "ORD-3004", "customer_name": "太原创新谷", "amount": 62000.00,
         "order_date": base - timedelta(days=28), "region": "华北", "product": "智能手环"},
        {"order_id": "ORD-3005", "customer_name": "青岛海尔智能", "amount": 198000.00,
         "order_date": base - timedelta(days=4), "region": "华北", "product": "智能手表"},
        # 西南
        {"order_id": "ORD-4001", "customer_name": "成都天府软件园", "amount": 143000.00,
         "order_date": base - timedelta(days=7), "region": "西南", "product": "智能手表"},
        {"order_id": "ORD-4002", "customer_name": "重庆两江数码", "amount": 87000.00,
         "order_date": base - timedelta(days=14), "region": "西南", "product": "蓝牙耳机"},
        {"order_id": "ORD-4003", "customer_name": "昆明阳光科技", "amount": 34000.00,
         "order_date": base - timedelta(days=21), "region": "西南", "product": "智能手环"},
        {"order_id": "ORD-4004", "customer_name": "贵阳大数据中心", "amount": 56000.00,
         "order_date": base - timedelta(days=30), "region": "西南", "product": "蓝牙耳机"},
        # 西北
        {"order_id": "ORD-5001", "customer_name": "西安高新区电子", "amount": 108000.00,
         "order_date": base - timedelta(days=9), "region": "西北", "product": "智能手表"},
        {"order_id": "ORD-5002", "customer_name": "兰州新区科技", "amount": 29000.00,
         "order_date": base - timedelta(days=17), "region": "西北", "product": "蓝牙耳机"},
        {"order_id": "ORD-5003", "customer_name": "银川智慧城", "amount": 47000.00,
         "order_date": base - timedelta(days=24), "region": "西北", "product": "智能手环"},
        # 更多数据充实
        {"order_id": "ORD-6001", "customer_name": "武汉光谷电子", "amount": 168000.00,
         "order_date": base - timedelta(days=5), "region": "华中", "product": "智能手表"},
        {"order_id": "ORD-6002", "customer_name": "长沙麓谷数码", "amount": 72000.00,
         "order_date": base - timedelta(days=13), "region": "华中", "product": "蓝牙耳机"},
        {"order_id": "ORD-6003", "customer_name": "郑州高新区", "amount": 51000.00,
         "order_date": base - timedelta(days=19), "region": "华中", "product": "智能手环"},
        {"order_id": "ORD-7001", "customer_name": "上海张江高科", "amount": 290000.00,
         "order_date": base - timedelta(days=1), "region": "华东", "product": "智能手环"},
        {"order_id": "ORD-7002", "customer_name": "深圳南山科技园", "amount": 350000.00,
         "order_date": base - timedelta(days=2), "region": "华南", "product": "智能手表"},
        {"order_id": "ORD-7003", "customer_name": "北京望京SOHO", "amount": 225000.00,
         "order_date": base - timedelta(days=3), "region": "华北", "product": "智能手环"},
        {"order_id": "ORD-7004", "customer_name": "广州珠江新城", "amount": 135000.00,
         "order_date": base - timedelta(days=4), "region": "华南", "product": "蓝牙耳机"},
        {"order_id": "ORD-7005", "customer_name": "杭州西溪数码", "amount": 95000.00,
         "order_date": base - timedelta(days=6), "region": "华东", "product": "蓝牙耳机"},
    ]


def _mock_monthly_trend(today: date, months: int) -> list[dict]:
    """生成模拟月度趋势数据。"""
    result = []
    for i in range(months - 1, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        d = date(year, month, 1)
        # 模拟带波动的销售额：80万~350万
        base_amount = 1_500_000 + math.sin(i * 0.8) * 800_000 + (i % 3) * 300_000
        result.append({"label": _fmt_month(d), "amount": round(base_amount, 2)})
    return result


def _monthly_to_weekly(monthly: list[dict]) -> list[dict]:
    """按月数据模拟拆分为周数据。"""
    weekly = []
    for m in monthly:
        avg = m["amount"] / 4
        for wk in range(4):
            weekly.append({
                "label": f"{m['label']}第{wk + 1}周",
                "amount": round(avg * (0.7 + 0.6 * (wk % 3) / 3), 2),
            })
    return weekly


def _build_weekly_aggregation(data: list[dict], weeks: int) -> list[dict]:
    """将日级数据聚合为周级数据（含维度字段）。"""
    today = date.today()
    week_buckets: dict[str, dict] = {}
    for r in data:
        days_ago = (today - r["order_date"]).days
        week_idx = days_ago // 7
        if week_idx >= weeks:
            continue
        week_start = today - timedelta(days=days_ago - (days_ago % 7))
        bucket_key = f"{week_start.isoformat()}|{r.get('product', '')}|{r.get('region', '')}"
        if bucket_key not in week_buckets:
            week_buckets[bucket_key] = {
                "week_start": week_start,
                "product": r["product"],
                "region": r["region"],
                "amount": 0.0,
            }
        week_buckets[bucket_key]["amount"] += r["amount"]
    return list(week_buckets.values())


def _build_filter_desc(
    region: str | None, product: str | None, start: str | None, end: str | None
) -> str:
    parts = []
    if region:
        parts.append(f"区域「{region}」")
    if product:
        parts.append(f"产品「{product}」")
    if start:
        parts.append(f"从 {start} 起")
    if end:
        parts.append(f"至 {end} 止")
    return "、".join(parts) if parts else "全部"


# ════════════════════════════════════════════════════════════
# 工具列表（供 Agent 注册使用）
# ════════════════════════════════════════════════════════════

SALES_TOOLS = [
    query_sales_data,
    calculate_statistics,
    analyze_trends,
    generate_chart_data,
    detect_anomalies,
]
