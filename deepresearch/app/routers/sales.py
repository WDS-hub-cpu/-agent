# ============================================================
# 路由: 销售数据相关接口（含身份认证 + 数据级权限）
# ============================================================
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, RequireAnalyst
from app.schemas.sales_data import SalesDataCreate, SalesDataUpdate, SalesDataOut
from app.services.sales_service import SalesService
from app.utils.context import RequestUser

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post("/", response_model=SalesDataOut, status_code=status.HTTP_201_CREATED)
async def create_sales(
    payload: SalesDataCreate,
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(get_current_user),
):
    return await SalesService.create(db, payload, current_user)


@router.get("/", response_model=list[SalesDataOut])
async def list_sales(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(get_current_user),
):
    return await SalesService.get_all(db, current_user, offset, limit)


@router.get("/{sales_id}", response_model=SalesDataOut)
async def get_sales(
    sales_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(get_current_user),
):
    record = await SalesService.get_by_id(db, sales_id, current_user)
    if not record:
        raise HTTPException(status_code=404, detail="Sales record not found")
    return record


@router.patch("/{sales_id}", response_model=SalesDataOut)
async def update_sales(
    sales_id: int,
    payload: SalesDataUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(get_current_user),
):
    record = await SalesService.get_by_id(db, sales_id, current_user)
    if not record:
        raise HTTPException(status_code=404, detail="Sales record not found")
    return await SalesService.update(db, record, payload, current_user)


@router.delete("/{sales_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sales(
    sales_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(get_current_user),
):
    record = await SalesService.get_by_id(db, sales_id, current_user)
    if not record:
        raise HTTPException(status_code=404, detail="Sales record not found")
    await SalesService.delete(db, record, current_user)


# ---------- 分析接口（只有 admin/analyst 可查看全量） ----------
@router.get("/analytics/by-region")
async def analytics_by_region(
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(get_current_user),
):
    """按区域汇总（viewer 只看自己的数据，admin/analyst 看全量）。"""
    return await SalesService.total_by_region(db, current_user)


@router.get("/analytics/by-product")
async def analytics_by_product(
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(get_current_user),
):
    """按产品汇总（viewer 只看自己的数据，admin/analyst 看全量）。"""
    return await SalesService.total_by_product(db, current_user)


# ---------- 演示：只有 admin/analyst 才能删除 ----------
@router.delete("/admin/purge/{sales_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_sales(
    sales_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: RequestUser = Depends(RequireAnalyst),
):
    """仅 admin/analyst 可强制删除任意记录（角色守卫示例）。"""
    record = await SalesService.get_by_id(db, sales_id, current_user)
    if not record:
        raise HTTPException(status_code=404, detail="Sales record not found")
    await SalesService.delete(db, record, current_user)
