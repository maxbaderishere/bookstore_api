from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.book import Book


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_cart_items_user_book"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive")
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    book: Mapped["Book"] = relationship()  # noqa: UP037
