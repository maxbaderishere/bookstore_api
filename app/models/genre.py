from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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