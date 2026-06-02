# ============================================================
# 模型: sales_data 表（含 user_id 数据归属）
# ============================================================
from datetime import date, datetime

from sqlalchemy import String, Date, DateTime, DECIMAL, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SalesData(Base):
    __tablename__ = "sales_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[float] = mapped_column(DECIMAL(12, 2), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # ---------- 数据归属 ----------
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<SalesData(order_id={self.order_id!r}, customer={self.customer_name!r}, "
            f"amount={self.amount}, region={self.region!r}, user_id={self.user_id})>"
        )
