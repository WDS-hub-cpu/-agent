# ============================================================
# Pydantic Schema: 销售数据（含 user_id）
# ============================================================
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SalesDataBase(BaseModel):
    order_id: str
    customer_name: str
    amount: float
    order_date: date
    region: str
    product: str


class SalesDataCreate(SalesDataBase):
    """创建时无需传 user_id，由后端根据当前登录用户自动填充。"""
    pass


class SalesDataUpdate(BaseModel):
    customer_name: str | None = None
    amount: float | None = None
    order_date: date | None = None
    region: str | None = None
    product: str | None = None


class SalesDataOut(SalesDataBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
