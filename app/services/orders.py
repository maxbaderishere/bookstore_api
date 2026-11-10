"""Оформление заказов из корзины и управление их статусами."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import OrderStatus, Role
from app.core.exceptions import (
    BookNotFoundError,
    EmptyCartError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    OrderNotFoundError,
)
from app.models.book import Book
from app.models.cart import CartItem
from app.models.order import OrderItems, Orders
from app.models.user import User

# Разрешённые переходы статусов; из delivered и cancelled выхода нет.
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.pending: {OrderStatus.paid, OrderStatus.cancelled},
    OrderStatus.paid: {OrderStatus.shipped, OrderStatus.cancelled},
    OrderStatus.shipped: {OrderStatus.delivered},
    OrderStatus.delivered: set(),
    OrderStatus.cancelled: set(),
}


def order_query() -> Select[tuple[Orders]]:
    return select(Orders).options(
        selectinload(Orders.items).selectinload(OrderItems.book)
    )


class OrderService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self._db = db
        self._user = user

    @property
    def _is_admin(self) -> bool:
        return self._user.role == Role.admin

    # ---------- чтение ----------

    async def list_own(self, limit: int, offset: int) -> list[Orders]:
        return await self._list(
            order_query().where(Orders.user_id == self._user.id), limit, offset
        )

    async def list_all(
        self, limit: int, offset: int, status: OrderStatus | None = None
    ) -> list[Orders]:
        stmt = order_query()
        if status is not None:
            stmt = stmt.where(Orders.status == status)
        return await self._list(stmt, limit, offset)

    async def get(self, order_id: int) -> Orders:
        """Свой заказ; администратор видит любой. Чужой — 404, чтобы не светить id."""
        stmt = order_query().where(Orders.id == order_id)
        if not self._is_admin:
            stmt = stmt.where(Orders.user_id == self._user.id)
        order = (
            await self._db.execute(stmt.execution_options(populate_existing=True))
        ).scalar_one_or_none()
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    # ---------- оформление ----------

    async def create_from_cart(self, shipping_address: str) -> Orders:
        cart = (
            (
                await self._db.execute(
                    select(CartItem)
                    .where(CartItem.user_id == self._user.id)
                    .order_by(CartItem.book_id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if not cart:
            raise EmptyCartError

        books = await self._lock_books([item.book_id for item in cart])

        order = Orders(
            user_id=self._user.id,
            status=OrderStatus.pending,
            shipping_address=shipping_address,
            total_amount=Decimal(0),
        )
        for item in cart:
            book = books.get(item.book_id)
            if book is None or book.is_archived:
                raise BookNotFoundError(item.book_id)
            if item.quantity > book.stock:
                raise InsufficientStockError(book.id, item.quantity, book.stock)

            book.stock -= item.quantity
            order.items.append(
                OrderItems(
                    book_id=book.id, quantity=item.quantity, unit_price=book.price
                )
            )
            order.total_amount += book.price * item.quantity

        self._db.add(order)
        await self._db.execute(
            delete(CartItem).where(CartItem.user_id == self._user.id)
        )
        await self._db.commit()
        return await self.get(order.id)

    # ---------- статусы ----------

    async def cancel(self, order_id: int) -> Orders:
        """Отмена покупателем: только своего заказа и только до оплаты."""
        order = await self._get_for_update(order_id, own_only=True)
        if order.status != OrderStatus.pending:
            raise InvalidStatusTransitionError(order.status, OrderStatus.cancelled)
        return await self._apply_status(order, OrderStatus.cancelled)

    async def set_status(self, order_id: int, status: OrderStatus) -> Orders:
        """Смена статуса администратором по таблице TRANSITIONS."""
        order = await self._get_for_update(order_id, own_only=False)
        if status not in TRANSITIONS[order.status]:
            raise InvalidStatusTransitionError(order.status, status)
        return await self._apply_status(order, status)

    # ---------- helpers ----------

    async def _list(self, stmt: Select, limit: int, offset: int) -> list[Orders]:
        stmt = stmt.order_by(Orders.created_at.desc(), Orders.id.desc())
        result = await self._db.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def _get_for_update(self, order_id: int, *, own_only: bool) -> Orders:
        stmt = (
            select(Orders)
            .where(Orders.id == order_id)
            .options(selectinload(Orders.items))
            .with_for_update(of=Orders)
        )
        if own_only:
            stmt = stmt.where(Orders.user_id == self._user.id)
        order = (await self._db.execute(stmt)).scalar_one_or_none()
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    async def _lock_books(self, book_ids: list[int]) -> dict[int, Book]:
        # Блокируем строки книг в порядке id — без дедлоков между заказами.
        result = await self._db.execute(
            select(Book)
            .where(Book.id.in_(book_ids))
            .order_by(Book.id)
            .with_for_update()
        )
        return {book.id: book for book in result.scalars().all()}

    async def _apply_status(self, order: Orders, status: OrderStatus) -> Orders:
        if status == OrderStatus.cancelled:
            books = await self._lock_books([item.book_id for item in order.items])
            for item in order.items:
                books[item.book_id].stock += item.quantity
        if status == OrderStatus.paid:
            order.paid_at = datetime.now(UTC)

        order.status = status
        await self._db.commit()
        return await self.get(order.id)
