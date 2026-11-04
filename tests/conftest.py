import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from httpx import AsyncClient, ASGITransport

from sqlalchemy.pool import NullPool

from app.core.config import cfg
from app.db.seeds import seed_database
from app.db.session import get_db
from app.main import app
from app.models.base import BaseModel

test_engine = create_async_engine(cfg.TEST_DATABASE_URL, echo=False, poolclass = NullPool)

test_sessionmaker = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_session():
    async with test_sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(scope="session", autouse=True)
def override_dependencies():
    app.dependency_overrides[get_db] = override_get_session

    yield

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(autouse=True)
async def db_setup():
    async with test_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
        await conn.run_sync(BaseModel.metadata.create_all)

    async with test_sessionmaker() as session:
        await seed_database(session)

    yield


@pytest_asyncio.fixture()
async def client(db_setup, override_dependencies):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
