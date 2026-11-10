"""Кэширование GET /books и GET /books/{id}."""

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import cfg
from app.db.redis import get_redis
from app.main import app
from app.models.book import Book
from app.services.cache import BookCache

URL = "/api/v1/books"


async def book_keys(redis) -> list[str]:
    return [key async for key in redis.scan_iter("books:v*")]


# ---------- GET /books/{id} ----------


async def test_show_book_miss_then_hit(anon_client: AsyncClient, book):
    first = await anon_client.get(f"{URL}/{book.id}")
    second = await anon_client.get(f"{URL}/{book.id}")

    assert first.status_code == second.status_code == 200
    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert first.json() == second.json()


async def test_show_book_served_from_cache(anon_client: AsyncClient, db, book):
    await anon_client.get(f"{URL}/{book.id}")

    # меняем БД в обход API — инвалидации нет, значит ответ должен быть из кэша
    await db.execute(update(Book).where(Book.id == book.id).values(title="Changed"))
    await db.commit()

    response = await anon_client.get(f"{URL}/{book.id}")

    assert response.headers["X-Cache"] == "HIT"
    assert response.json()["title"] == "Test book"


async def test_show_book_sets_ttl(anon_client: AsyncClient, redis, book):
    await anon_client.get(f"{URL}/{book.id}")

    [key] = await book_keys(redis)
    assert key.endswith(f"item:{book.id}")
    assert 0 < await redis.ttl(key) <= cfg.CACHE_TTL_SECONDS


async def test_missing_book_not_cached(anon_client: AsyncClient, redis):
    first = await anon_client.get(f"{URL}/999999")
    second = await anon_client.get(f"{URL}/999999")

    assert first.status_code == second.status_code == 404
    assert await book_keys(redis) == []


async def test_invalid_id_not_cached(anon_client: AsyncClient, redis):
    response = await anon_client.get(f"{URL}/abc")

    assert response.status_code == 422
    assert await book_keys(redis) == []


# ---------- GET /books ----------


async def test_list_miss_then_hit(anon_client: AsyncClient, book):
    first = await anon_client.get(URL)
    second = await anon_client.get(URL)

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert first.json() == second.json()
    assert [b["id"] for b in second.json()] == [book.id]


async def test_list_cached_per_pagination(anon_client: AsyncClient, book):
    await anon_client.get(URL, params={"limit": 10})

    other_page = await anon_client.get(URL, params={"limit": 10, "offset": 1})
    same_page = await anon_client.get(URL, params={"limit": 10})

    assert other_page.headers["X-Cache"] == "MISS"
    assert other_page.json() == []
    assert same_page.headers["X-Cache"] == "HIT"


async def test_empty_list_is_cached(anon_client: AsyncClient):
    await anon_client.get(URL)

    response = await anon_client.get(URL)

    assert response.headers["X-Cache"] == "HIT"
    assert response.json() == []


async def test_invalid_query_not_cached(anon_client: AsyncClient, redis):
    response = await anon_client.get(URL, params={"limit": 0})

    assert response.status_code == 422
    assert await book_keys(redis) == []


# ---------- инвалидация ----------


async def test_create_book_invalidates_list(client: AsyncClient, book_payload):
    await client.get(URL)

    created = await client.post(URL, json=book_payload)
    response = await client.get(URL)

    assert response.headers["X-Cache"] == "MISS"
    assert created.json()["id"] in [b["id"] for b in response.json()]


async def test_change_book_invalidates(client: AsyncClient, book):
    await client.get(f"{URL}/{book.id}")
    await client.get(URL)

    await client.patch(f"{URL}/{book.id}", json={"title": "New title"})

    item = await client.get(f"{URL}/{book.id}")
    listing = await client.get(URL)
    assert item.headers["X-Cache"] == listing.headers["X-Cache"] == "MISS"
    assert item.json()["title"] == "New title"
    assert listing.json()[0]["title"] == "New title"


async def test_failed_change_does_not_invalidate(client: AsyncClient, book):
    await client.get(f"{URL}/{book.id}")

    failed = await client.patch(f"{URL}/{book.id}", json={"title": None})
    response = await client.get(f"{URL}/{book.id}")

    assert failed.status_code == 422
    assert response.headers["X-Cache"] == "HIT"


async def test_delete_book_invalidates(client: AsyncClient, book):
    await client.get(f"{URL}/{book.id}")
    await client.get(URL)

    await client.delete(f"{URL}/{book.id}")

    assert (await client.get(f"{URL}/{book.id}")).status_code == 404
    assert (await client.get(URL)).json() == []


async def test_change_author_invalidates_books(client: AsyncClient, book, author):
    await client.get(f"{URL}/{book.id}")

    await client.patch(f"/api/v1/authors/{author.id}", json={"full_name": "Renamed"})

    response = await client.get(f"{URL}/{book.id}")
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["authors"][0]["full_name"] == "Renamed"


async def test_change_publisher_invalidates_books(client: AsyncClient, book, publisher):
    await client.get(f"{URL}/{book.id}")

    await client.patch(f"/api/v1/publishers/{publisher.id}", json={"name": "Renamed"})

    response = await client.get(f"{URL}/{book.id}")
    assert response.json()["publisher"]["name"] == "Renamed"


async def test_delete_publisher_invalidates_books(client: AsyncClient, book, publisher):
    await client.get(f"{URL}/{book.id}")

    await client.delete(f"/api/v1/publishers/{publisher.id}")

    response = await client.get(f"{URL}/{book.id}")
    assert response.json()["publisher"] is None


async def test_create_author_does_not_invalidate(client: AsyncClient, book):
    await client.get(f"{URL}/{book.id}")

    await client.post("/api/v1/authors", json={"full_name": "Someone"})

    response = await client.get(f"{URL}/{book.id}")
    assert response.headers["X-Cache"] == "HIT"


# ---------- Redis недоступен ----------


@pytest.fixture
def broken_redis():
    server = FakeServer()
    server.connected = False
    broken = FakeAsyncRedis(server=server, decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: broken
    return broken


async def test_reads_work_without_redis(anon_client: AsyncClient, book, broken_redis):
    item = await anon_client.get(f"{URL}/{book.id}")
    listing = await anon_client.get(URL)

    assert item.status_code == listing.status_code == 200
    assert item.headers["X-Cache"] == "MISS"
    assert item.json()["id"] == book.id
    assert [b["id"] for b in listing.json()] == [book.id]


async def test_writes_work_without_redis(client: AsyncClient, book, broken_redis):
    response = await client.patch(f"{URL}/{book.id}", json={"title": "Offline"})

    assert response.status_code == 200
    assert response.json()["title"] == "Offline"


# ---------- BookCache (юнит) ----------


async def test_loader_result_written_under_version_read_before_load(redis):
    """Если данные изменились, пока грузили из БД, устаревший ответ не должен
    попасть в кэш под новой версией."""
    cache = BookCache(redis)

    async def stale_loader():
        await cache.invalidate()  # кто-то изменил книгу во время чтения БД
        return {"title": "stale"}

    await cache.get_or_load("item:1", stale_loader)

    async def fresh_loader():
        return {"title": "fresh"}

    value, hit = await cache.get_or_load("item:1", fresh_loader)
    assert not hit
    assert value == {"title": "fresh"}


async def test_loader_none_not_cached(redis):
    cache = BookCache(redis)
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1

    await cache.get_or_load("item:1", loader)
    await cache.get_or_load("item:1", loader)

    assert calls == 2
