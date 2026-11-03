from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.book import Book


class Genre(Base):
    __tablename__ = "genres"
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    books: Mapped[list["Book"]] = relationship(  # noqa: UP037
        secondary="book_genres",
        back_populates="genres",
    )
