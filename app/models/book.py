
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimeStampMixin


class Books(Base, TimeStampMixin):
    __tablename__ = "books"
    title: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] 
    isbn: Mapped[str] = mapped_column(
    String(13),
    CheckConstraint("isbn ~ '^[0-9]+$'", name="ck_books_isbn_digits"),
    unique=True,
)
    publisher_id: Mapped[int | None] = mapped_column(
        ForeignKey("publishers.id", ondelete="SET NULL"),
        index=True
)
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
    cover_url: Mapped[str] = mapped_column(String(500))
    is_archived: Mapped[bool] = mapped_column(default=False)


class BookAuthor(Base):
    __tablename__ = "book_authors"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"),
        primary_key=True
    )

    author_id: Mapped[int] = mapped_column(
        ForeignKey("authors.id", ondelete="RESTRICT"),
        primary_key=True
    )