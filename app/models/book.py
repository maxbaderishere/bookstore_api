from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import TimeStampMixin

if TYPE_CHECKING:
    from app.models.author import Author
    from app.models.genre import Genre
    from app.models.publisher import Publisher


class Book(Base, TimeStampMixin):
    __tablename__ = "books"
    title: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None]
    isbn: Mapped[str] = mapped_column(
        String(13),
        CheckConstraint("isbn ~ '^[0-9]+$'", name="ck_books_isbn_digits"),
        unique=True,
    )
    publisher_id: Mapped[int | None] = mapped_column(
        ForeignKey("publishers.id", ondelete="SET NULL"), index=True
    )
    publisher: Mapped["Publisher | None"] = relationship(back_populates="books")  # noqa: UP037
    publication_year: Mapped[int | None] = mapped_column(
        SmallInteger,
        CheckConstraint(
            "publication_year >= 1450",
            name="ck_books_publication_year_min",
        ),
        nullable=True,
    )

    language: Mapped[str] = mapped_column(String(2))
    pages: Mapped[int | None] = mapped_column(
        CheckConstraint("pages > 0", name="ck_books_pages_positive"),
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        CheckConstraint("price >= 0", name="ck_books_price_non_negative"),
    )
    stock: Mapped[int] = mapped_column(
        CheckConstraint("stock >= 0", name="ck_books_stock_positive"),
        default=0,
    )
    authors: Mapped[list["Author"]] = relationship(  # noqa: UP037
        secondary="book_authors",
        back_populates="books",
    )
    genres: Mapped[list["Genre"]] = relationship(  # noqa: UP037
        secondary="book_genres", back_populates="books"
    )
    cover_url: Mapped[str] = mapped_column(String(500))
    is_archived: Mapped[bool] = mapped_column(default=False)


class BookAuthor(Base):
    __tablename__ = "book_authors"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )

    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="RESTRICT"), primary_key=True
    )


class BookGenre(Base):
    __tablename__ = "book_genres"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )

    genre_id: Mapped[int] = mapped_column(
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True
    )
