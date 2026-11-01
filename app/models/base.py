from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import cfg

engine = create_async_engine(cfg.DATABASE_URL, echo=False)

session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)

