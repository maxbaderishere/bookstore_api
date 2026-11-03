import app.models  # noqa: F401, RUF100
from app.db.seeds import seed_database
from app.db.session import engine, session_maker
from app.models.base import Base


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        await seed_database(session)