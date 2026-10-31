from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Publishers(Base):
    __tablename__ = "publishers"
    name: Mapped[str] = mapped_column(
        String(200),
        unique=True, 
        nullable=False
    )