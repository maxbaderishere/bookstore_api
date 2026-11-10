from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import OrderStatus
from app.models.base import Base
from app.models.mixins import TimeStampMixin

if TYPE_CHECKING:
    from app.models.book import Book


class Orders(Base, TimeStampMixin):
    __tablename__ = "orders"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    status: Mapped[OrderStatus]
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0.00
    )
    shipping_address: Mapped[str] = mapped_column(String(500), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=None
    )
    items: Mapped[list["OrderItems"]] = relationship(  # noqa: UP037
        order_by="OrderItems.id", cascade="all, delete-orphan"
    )


class OrderItems(Base):
    __tablename__ = "order_items"
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
    )
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    book: Mapped["Book"] = relationship()  # noqa: UP037
