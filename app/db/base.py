from app.db.seeds import seed_database
from app.db.session import session_maker


async def init_db():
    async with session_maker() as session:
        await seed_database(session)
