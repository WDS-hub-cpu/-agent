# ============================================================
# 服务: 销售数据 CRUD（含角色级数据权限）
# ============================================================
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sales_data import SalesData
from app.schemas.sales_data import SalesDataCreate, SalesDataUpdate
from app.utils.context import RequestUser

# 可查看全量数据的角色
_FULL_ACCESS_ROLES = {"admin", "analyst"}


class SalesService:

    # ======================== 权限核心 ========================
    @staticmethod
    def _apply_ownership_filter(stmt, current_user: RequestUser):
        """
        数据级权限过滤：
        - admin / analyst → 查看全量
        - viewer（普通销售） → 仅查看自己创建的记录
        """
        if current_user.role not in _FULL_ACCESS_ROLES:
            stmt = stmt.where(SalesData.user_id == current_user.user_id)
        return stmt

    # ======================== CRUD ========================
    @staticmethod
    async def create(
        db: AsyncSession, payload: SalesDataCreate, current_user: RequestUser
    ) -> SalesData:
        """创建时自动绑定当前用户为数据归属人。"""
        record = SalesData(**payload.model_dump(), user_id=current_user.user_id)
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record

    @staticmethod
    async def get_by_id(
        db: AsyncSession, record_id: int, current_user: RequestUser
    ) -> SalesData | None:
        record = await db.get(SalesData, record_id)
        if record is None:
            return None
        # 越权拦截：非全量角色只能看自己的数据
        if current_user.role not in _FULL_ACCESS_ROLES and record.user_id != current_user.user_id:
            return None
        return record

    @staticmethod
    async def get_all(
        db: AsyncSession,
        current_user: RequestUser,
        offset: int = 0,
        limit: int = 50,
    ) -> list[SalesData]:
        stmt = select(SalesData).order_by(SalesData.order_date.desc())
        stmt = SalesService._apply_ownership_filter(stmt, current_user)
        stmt = stmt.offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        record: SalesData,
        payload: SalesDataUpdate,
        current_user: RequestUser,
    ) -> SalesData:
        _verify_ownership(record, current_user)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        await db.flush()
        await db.refresh(record)
        return record

    @staticmethod
    async def delete(
        db: AsyncSession, record: SalesData, current_user: RequestUser
    ) -> None:
        _verify_ownership(record, current_user)
        await db.delete(record)
        await db.flush()

    # ======================== 分析查询（角色过滤） ========================
    @staticmethod
    async def total_by_region(
        db: AsyncSession, current_user: RequestUser
    ) -> list[dict]:
        stmt = (
            select(
                SalesData.region,
                func.sum(SalesData.amount).label("total_amount"),
                func.count(SalesData.id).label("order_count"),
            )
            .group_by(SalesData.region)
            .order_by(func.sum(SalesData.amount).desc())
        )
        stmt = SalesService._apply_ownership_filter(stmt, current_user)
        result = await db.execute(stmt)
        return [
            {"region": r, "total_amount": float(a), "order_count": c}
            for r, a, c in result.all()
        ]

    @staticmethod
    async def total_by_product(
        db: AsyncSession, current_user: RequestUser
    ) -> list[dict]:
        stmt = (
            select(
                SalesData.product,
                func.sum(SalesData.amount).label("total_amount"),
                func.count(SalesData.id).label("order_count"),
            )
            .group_by(SalesData.product)
            .order_by(func.sum(SalesData.amount).desc())
        )
        stmt = SalesService._apply_ownership_filter(stmt, current_user)
        result = await db.execute(stmt)
        return [
            {"product": p, "total_amount": float(a), "order_count": c}
            for p, a, c in result.all()
        ]


# ======================== 辅助函数 ========================
def _verify_ownership(record: SalesData, current_user: RequestUser) -> None:
    """非全量角色修改/删除他人数据时抛出 403。"""
    if current_user.role not in _FULL_ACCESS_ROLES and record.user_id != current_user.user_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this record.",
        )
