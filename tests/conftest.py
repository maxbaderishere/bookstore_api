import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import cfg
from app.db.seeds import seed_database
from app.db.session import get_db
from app.main import app
from app.models.author import Author
from app.models.base import BaseModel
from app.models.book import Book
from app.models.genre import Genre
from app.models.publisher import Publisher

test_engine = create_async_engine(cfg.TEST_DATABASE_URL, echo=False, poolclass=NullPool)

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


@pytest_asyncio.fixture
async def db(db_setup):
    async with test_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_setup, override_dependencies):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def author(db):
    obj = Author(full_name="Test Author", birth_year=1900)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@pytest_asyncio.fixture
async def publisher(db):
    obj = Publisher(name="Test Publisher")
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@pytest_asyncio.fixture
async def genre(db):
    obj = Genre(name="Test genre", slug="Test slug")
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@pytest_asyncio.fixture
async def book(db, publisher, author, genre):
    obj = Book(
        title="Test book",
        description="",
        isbn="0" * 13,
        publisher_id=publisher.id,
        publication_year=1900,
        language="en",
        pages=100,
        price=100,
        stock=1,
        cover_url="https://example.com/cover.jpg",
        authors=[author],
        genres=[genre],
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj, attribute_names=["authors", "genres"])
    return obj
