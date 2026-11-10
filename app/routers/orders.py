from fastapi import APIRouter, Query

from app.core.enums import OrderStatus
from app.dependencies import AdminUser, BookCacheDep, OrderServiceDep
from app.schemas.order import OrderCreate, OrderOut, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(orders: OrderServiceDep, cache: BookCacheDep, data: OrderCreate):
    """Оформить заказ из содержимого корзины; корзина очищается, склад уменьшается."""
    order = await orders.create_from_cart(data.shipping_address)
    await cache.invalidate()  # изменился stock книг
    return order


@router.get("", response_model=list[OrderOut])
async def my_orders(
    orders: OrderServiceDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return await orders.list_own(limit, offset)


@router.get("/all", response_model=list[OrderOut])
async def all_orders(
    orders: OrderServiceDep,
    _: AdminUser,
    status: OrderStatus | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Все заказы магазина (только администратор)."""
    return await orders.list_all(limit, offset, status)


@router.get("/{order_id}", response_model=OrderOut)
async def show_order(orders: OrderServiceDep, order_id: int):
    return await orders.get(order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(orders: OrderServiceDep, cache: BookCacheDep, order_id: int):
    """Отменить свой заказ, пока он не оплачен; товар возвращается на склад."""
    order = await orders.cancel(order_id)
    await cache.invalidate()
    return order


@router.patch("/{order_id}/status", response_model=OrderOut)
async def change_status(
    orders: OrderServiceDep,
    cache: BookCacheDep,
    _: AdminUser,
    order_id: int,
    data: OrderStatusUpdate,
):
    """Сменить статус заказа (только администратор)."""
    order = await orders.set_status(order_id, data.status)
    if data.status == OrderStatus.cancelled:
        await cache.invalidate()
    return order
