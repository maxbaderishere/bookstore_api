from sqlalchemy import SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Author(Base):
    __tablename__ = "authors"
    full_name: Mapped[str] = mapped_column(
        String(200),
        index=True,
        nullable=False
    )
    bio: Mapped[str | None]
    birth_year: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True
    ) 

