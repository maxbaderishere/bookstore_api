from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import cfg

engine = create_async_engine(cfg.DATABASE_URL, echo=False)

session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False
)

