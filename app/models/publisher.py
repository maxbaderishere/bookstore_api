from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.book import Book


class Publisher(Base):
    __tablename__ = "publishers"
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    books: Mapped[list["Book"]] = relationship(back_populates="publisher")  # noqa: UP037
