"""Корзина пользователя: у каждого пользователя своя, хранится в cart_items."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BookNotFoundError,
    CartItemNotFoundError,
    InsufficientStockError,
)
from app.models.book import Book
from app.models.cart import CartItem


class CartService:
    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self._db = db
        self._user_id = user_id

    async def items(self) -> list[CartItem]:
        result = await self._db.execute(
            select(CartItem)
            .where(CartItem.user_id == self._user_id)
            .options(selectinload(CartItem.book))
            .order_by(CartItem.added_at, CartItem.id)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def add(self, book_id: int, quantity: int) -> list[CartItem]:
        """Добавляет книгу; если она уже в корзине — увеличивает количество."""
        book = await self._get_book(book_id)
        item = await self._get_item(book_id)

        new_quantity = quantity + (item.quantity if item else 0)
        self._ensure_stock(book, new_quantity)

        if item is None:
            self._db.add(
                CartItem(user_id=self._user_id, book_id=book_id, quantity=quantity)
            )
        else:
            item.quantity = new_quantity
        await self._db.commit()
        return await self.items()

    async def set_quantity(self, book_id: int, quantity: int) -> list[CartItem]:
        item = await self._get_item(book_id)
        if item is None:
            raise CartItemNotFoundError(book_id)

        book = await self._get_book(book_id)
        self._ensure_stock(book, quantity)

        item.quantity = quantity
        await self._db.commit()
        return await self.items()

    async def remove(self, book_id: int) -> None:
        item = await self._get_item(book_id)
        if item is None:
            raise CartItemNotFoundError(book_id)
        await self._db.delete(item)
        await self._db.commit()

    async def clear(self) -> None:
        await self._db.execute(
            delete(CartItem).where(CartItem.user_id == self._user_id)
        )
        await self._db.commit()

    # ---------- helpers ----------

    async def _get_book(self, book_id: int) -> Book:
        book = await self._db.get(Book, book_id)
        if book is None or book.is_archived:
            raise BookNotFoundError(book_id)
        return book

    async def _get_item(self, book_id: int) -> CartItem | None:
        # FOR UPDATE: два параллельных add одной книги не потеряют количество
        result = await self._db.execute(
            select(CartItem)
            .where(CartItem.user_id == self._user_id, CartItem.book_id == book_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _ensure_stock(book: Book, quantity: int) -> None:
        if quantity > book.stock:
            raise InsufficientStockError(book.id, quantity, book.stock)
