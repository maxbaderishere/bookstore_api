from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    user_id: Mapped[int] = mapped_column(unique=True)
    book_id: Mapped[int] = mapped_column(unique=True)
    quantity: Mapped[int] = mapped_column(
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive")
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
