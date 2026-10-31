
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimeStampMixin
from app.schemas.user import Role


class Users(Base, TimeStampMixin):

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str] 
    full_name: Mapped[str] 
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name = "user_role",
    values_callable = lambda e: [m.value for m in e]),
        default=Role.customer,
        server_default=Role.customer.value,
        nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    