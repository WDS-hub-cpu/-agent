"""
销售数据分析工具集 (Tools for LLM Agent)

本模块提供两个独立工具函数，可供 LangChain Agent 调用，
也支持独立运行测试。
"""

from typing import Any
from sqlalchemy import text
from database import SessionLocal
from auth import check_sql_permission


# ============================================================
# Tool 1: query_sales_data
# ============================================================

def query_sales_data(sql: str) -> dict[str, Any]:
    """
    [工具名称] query_sales_data

    [正向能力]
    - 执行只读的 SELECT 类 SQL 查询，从 sales_data 表中检索销售数据。
    - 支持聚合查询（SUM / AVG / COUNT / MAX / MIN）、分组（GROUP BY）、
      排序（ORDER BY）、条件过滤（WHERE）、多表 JOIN、子查询等标准 SQL 语法。
    - 返回结构化的 JSON 结果，包含列名列表和行数据列表，方便大模型解析。
    - 可查询的字段包括：sale_date, product_name, category, region, city,
      sales_amount, profit, quantity, unit_price, channel, salesperson。

    [反向排除]
    - **禁止** 执行 INSERT / UPDATE / DELETE / DROP / TRUNCATE / ALTER
      等任何会修改数据或表结构的 SQL 语句。如果检测到此类语句，直接返回错误。
    - **禁止** 查询 sales_data 表以外的任何表或数据库。
    - **禁止** 使用分号 `;` 执行多条语句（防止 SQL 注入）。
    - **不支持** 创建临时表、存储过程、触发器等 DDL 操作。
    - **不负责** 数据的可视化或图表生成，仅返回原始查询结果。

    [参数]
    sql : str
        仅限 SELECT 查询语句。

    [返回]
    dict[str, Any]
        {
            "success": True / False,
            "columns": ["col1", "col2", ...],
            "rows": [ [val1, val2, ...], ... ],
            "row_count": int,
            "error": str (仅失败时)
        }
    """
    # --- 安全检查：禁止修改类 SQL ---
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER",
        "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "REPLACE",
    ]
    sql_upper = sql.strip().upper()
    # 多语句检测
    if ";" in sql.rstrip(";"):
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": "安全限制：禁止执行多条 SQL 语句。",
        }
    for kw in dangerous_keywords:
        if sql_upper.startswith(kw) or f" {kw} " in sql_upper:
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": f"安全限制：禁止执行 {kw} 语句，仅允许 SELECT 查询。",
            }

    # --- 角色权限校验 ---
    permitted, reason = check_sql_permission(sql)
    if not permitted:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": f"权限拒绝: {reason}",
        }

    db = SessionLocal()
    try:
        result = db.execute(text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        return {
            "success": True,
            "columns": columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
        }
    except Exception as e:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": str(e),
        }
    finally:
        db.close()


# ============================================================
# Tool 2: calculate_trend
# ============================================================

def calculate_trend(data: list[float | int]) -> dict[str, Any]:
    """
    [工具名称] calculate_trend

    [正向能力]
    - 接收一个数值列表，计算多项统计趋势指标。
    - 支持的指标：
        • mean（平均值）
        • median（中位数）
        • max / min（最大 / 最小值）
        • std（标准差，反映数据波动幅度）
        • growth_rates（环比增长率列表，每相邻两项的变化百分比）
        • trend_direction（整体趋势方向：上升 / 下降 / 平稳）
        • total（总和）
        • count（数据量）
    - 自动处理浮点精度，结果保留 4 位小数。
    - 适用于销售金额、利润、数量等任意数值型时间序列的趋势判断。

    [反向排除]
    - **不接受** 非数值类型数据（字符串、布尔值等会直接报错）。
    - **不接受** 空列表（至少需要 1 个数据点；增长率至少需要 2 个点）。
    - **不支持** 季节性分解、ARIMA 预测、机器学习等高级时序分析。
    - **不支持** 带有时间戳的配对数据，仅接受纯数值列表。
    - **不负责** 图表渲染或 HTML 输出，仅返回结构化指标字典。

    [参数]
    data : list[float | int]
        待分析的数值序列，例如 [1200, 1350, 1180, 1500]。

    [返回]
    dict[str, Any]
        {
            "success": True / False,
            "mean": float,
            "median": float,
            "max": float,
            "min": float,
            "std": float,
            "total": float,
            "count": int,
            "growth_rates": [float, ...],   # 长度 = len(data) - 1
            "trend_direction": "上升" | "下降" | "平稳",
            "error": str (仅失败时)
        }
    """
    import math

    # --- 输入校验 ---
    if not data:
        return {
            "success": False,
            "error": "输入数据为空列表，至少需要 1 个数值。",
        }

    # 类型校验
    clean_data: list[float] = []
    for i, v in enumerate(data):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return {
                "success": False,
                "error": f"第 {i} 个元素类型错误：期望 int/float，实际为 {type(v).__name__}。",
            }
        clean_data.append(float(v))

    n = len(clean_data)
    sorted_data = sorted(clean_data)

    # --- 计算指标 ---
    mean_val = round(sum(clean_data) / n, 4)
    total_val = round(sum(clean_data), 4)

    # 中位数
    if n % 2 == 1:
        median_val = round(sorted_data[n // 2], 4)
    else:
        median_val = round((sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2, 4)

    max_val = round(max(clean_data), 4)
    min_val = round(min(clean_data), 4)

    # 标准差
    if n > 1:
        variance = sum((x - mean_val) ** 2 for x in clean_data) / (n - 1)
        std_val = round(math.sqrt(variance), 4)
    else:
        std_val = 0.0

    # 环比增长率
    growth_rates: list[float] = []
    if n >= 2:
        for i in range(1, n):
            prev = clean_data[i - 1]
            if prev == 0:
                growth_rates.append(0.0)
            else:
                rate = (clean_data[i] - prev) / prev * 100
                growth_rates.append(round(rate, 4))

    # 趋势方向
    if n < 2 or len(growth_rates) == 0:
        trend_direction = "数据不足"
    else:
        positive = sum(1 for g in growth_rates if g > 0)
        negative = sum(1 for g in growth_rates if g < 0)
        if positive > negative:
            trend_direction = "上升"
        elif negative > positive:
            trend_direction = "下降"
        else:
            trend_direction = "平稳"

    return {
        "success": True,
        "mean": mean_val,
        "median": median_val,
        "max": max_val,
        "min": min_val,
        "std": std_val,
        "total": total_val,
        "count": n,
        "growth_rates": growth_rates,
        "trend_direction": trend_direction,
    }


# ============================================================
# 独立运行测试
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Tool 测试：query_sales_data & calculate_trend")
    print("=" * 60)

    # --------------------------------------------------
    # 测试 1: query_sales_data（合法查询 & 非法拦截）
    # --------------------------------------------------
    print("\n>>> [测试 1] query_sales_data — 合法查询")
    result = query_sales_data("SELECT COUNT(*) AS total_count FROM sales_data")
    if result["success"]:
        print(f"   ✅ 成功: columns={result['columns']}, rows={result['rows']}, "
              f"row_count={result['row_count']}")
    else:
        print(f"   ⚠️ 错误: {result['error']}")

    print("\n>>> [测试 2] query_sales_data — 非法语句拦截 (INSERT)")
    result = query_sales_data("INSERT INTO sales_data VALUES (1, '2025-01-01', 'test')")
    if not result["success"]:
        print(f"   ✅ 正确拦截: {result['error']}")

    print("\n>>> [测试 3] query_sales_data — 非法语句拦截 (DELETE)")
    result = query_sales_data("DELETE FROM sales_data WHERE id=1")
    if not result["success"]:
        print(f"   ✅ 正确拦截: {result['error']}")

    # --------------------------------------------------
    # 测试 2: calculate_trend（正常数据 & 边界情况）
    # --------------------------------------------------
    print("\n>>> [测试 4] calculate_trend — 正常销售数据")
    sales = [1200, 1350, 1180, 1500, 1620, 1580, 1750]
    result = calculate_trend(sales)
    if result["success"]:
        print(f"   数据: {sales}")
        print(f"   均值: {result['mean']}")
        print(f"   中位数: {result['median']}")
        print(f"   最大/最小: {result['max']} / {result['min']}")
        print(f"   标准差: {result['std']}")
        print(f"   总和: {result['total']}")
        print(f"   数据量: {result['count']}")
        print(f"   环比增长率(%): {result['growth_rates']}")
        print(f"   趋势方向: {result['trend_direction']}")

    print("\n>>> [测试 5] calculate_trend — 空列表边界")
    result = calculate_trend([])
    if not result["success"]:
        print(f"   ✅ 正确拦截: {result['error']}")

    print("\n>>> [测试 6] calculate_trend — 单元素列表")
    result = calculate_trend([100])
    if result["success"]:
        print(f"   均值: {result['mean']}, 趋势: {result['trend_direction']}")

    print("\n>>> [测试 7] calculate_trend — 类型错误拦截 (字符串混入)")
    result = calculate_trend([100, 200, "hello"])
    if not result["success"]:
        print(f"   ✅ 正确拦截: {result['error']}")

    print("\n>>> [测试 8] calculate_trend — 下降趋势")
    result = calculate_trend([1800, 1650, 1500, 1320, 1100])
    if result["success"]:
        print(f"   数据: [1800, 1650, 1500, 1320, 1100]")
        print(f"   环比增长率(%): {result['growth_rates']}")
        print(f"   趋势方向: {result['trend_direction']}")

    print("\n" + "=" * 60)
    print("  全部测试完成！")
    print("=" * 60)
