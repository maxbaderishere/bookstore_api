from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import cfg

engine = create_async_engine(cfg.DATABASE_URL, echo=False)

session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:  # noqa: UP043
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]