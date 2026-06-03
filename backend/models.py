from sqlalchemy import Column, BigInteger, Date, String, Integer, DateTime, Numeric, Index
from database import Base


class SalesData(Base):
    __tablename__ = "sales_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    sale_date = Column(Date, nullable=False, comment="销售日期")
    product_name = Column(String(100), nullable=False, comment="产品名称")
    category = Column(String(50), nullable=False, comment="产品类别")
    region = Column(String(50), nullable=False, comment="大区")
    city = Column(String(50), nullable=False, comment="城市")
    sales_amount = Column(Numeric(12, 2), nullable=False, default=0, comment="销售额（元）")
    profit = Column(Numeric(12, 2), nullable=False, default=0, comment="利润（元）")
    quantity = Column(Integer, nullable=False, default=0, comment="销售数量")
    unit_price = Column(Numeric(10, 2), nullable=False, default=0, comment="单价（元）")
    channel = Column(String(30), nullable=False, default="线下", comment="销售渠道（线上/线下）")
    salesperson = Column(String(50), nullable=False, default="", comment="销售员")
    created_at = Column(DateTime, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, comment="更新时间")

    __table_args__ = (
        Index("idx_sale_date", "sale_date"),
        Index("idx_product", "product_name"),
        Index("idx_region", "region"),
        Index("idx_category", "category"),
        Index("idx_region_date", "region", "sale_date"),
        {"comment": "销售数据表"},
    )
