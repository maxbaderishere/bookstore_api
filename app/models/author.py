from sqlalchemy import SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.book import Book


class Author(Base):
    __tablename__ = "authors"
    full_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    bio: Mapped[str | None]
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    books: Mapped[list["Book"]] = relationship(
        secondary="book_authors", back_populates="authors"
    )  # noqa: UP037
