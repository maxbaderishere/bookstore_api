import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import cfg
from app.core.enums import Role
from app.core.security import create_access_token, generate_salt, hash_password
from app.db.seeds import seed_database
from app.db.session import get_db
from app.main import app
from app.models.author import Author
from app.models.base import BaseModel
from app.models.book import Book
from app.models.genre import Genre
from app.models.publisher import Publisher
from app.models.user import User

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


TEST_PASSWORD = "correct-horse-battery"
# pbkdf2 медленный намеренно — считаем хэш один раз на всю сессию
TEST_SALT = generate_salt()
TEST_HASH = hash_password(TEST_PASSWORD, TEST_SALT)


async def make_user(db, email: str, role: Role, *, is_active: bool = True) -> User:
    user = User(
        email=email,
        full_name=f"{role.value} user",
        salt=TEST_SALT,
        hashed_password=TEST_HASH,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
def user_password() -> str:
    """Пароль всех пользователей из фикстур."""
    return TEST_PASSWORD


@pytest_asyncio.fixture
async def admin_user(db):
    return await make_user(db, "admin@example.com", Role.admin)


@pytest_asyncio.fixture
async def customer_user(db):
    return await make_user(db, "customer@example.com", Role.customer)


@pytest_asyncio.fixture
async def inactive_user(db):
    return await make_user(db, "inactive@example.com", Role.customer, is_active=False)


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest_asyncio.fixture
async def anon_client(db_setup, override_dependencies):
    """Клиент без токена."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def client(db_setup, override_dependencies, admin_user):
    """Клиент с access-токеном администратора."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(admin_user),
    ) as client:
        yield client


@pytest_asyncio.fixture
async def customer_client(db_setup, override_dependencies, customer_user):
    """Клиент с access-токеном обычного покупателя."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers(customer_user),
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


@pytest.fixture
def book_payload(publisher, author, genre) -> dict:
    """Валидное тело запроса POST /books; в тестах портят отдельные поля."""
    return {
        "title": "Payload book",
        "description": "Some description",
        "isbn": "9785170000007",
        "publisher_id": publisher.id,
        "publication_year": 2000,
        "language": "ru",
        "pages": 320,
        "price": "450.00",
        "stock": 5,
        "cover_url": "https://example.com/payload.jpg",
        "author_ids": [author.id],
        "genre_ids": [genre.id],
    }
