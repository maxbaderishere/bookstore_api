import pytest
from httpx import AsyncClient

URL = "/api/v1/books"


@pytest.fixture
def payload(publisher, author, genre) -> dict:
    return {
        "title": "Cover test",
        "isbn": "9785170000014",
        "publisher_id": publisher.id,
        "language": "en",
        "price": "10.00",
        "author_ids": [author.id],
        "genre_ids": [genre.id],
    }


async def test_create_book_without_cover_url(client: AsyncClient, payload):
    response = await client.post(URL, json=payload)

    assert response.status_code == 422


async def test_create_book_null_cover_url(client: AsyncClient, payload):
    payload["cover_url"] = None

    response = await client.post(URL, json=payload)

    assert response.status_code == 422


async def test_create_book_with_cover_url(client: AsyncClient, payload):
    payload["cover_url"] = "https://example.com/c.jpg"

    response = await client.post(URL, json=payload)

    assert response.status_code == 201
    assert response.json()["cover_url"] == "https://example.com/c.jpg"


async def test_change_book_null_cover_url(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={"cover_url": None})

    assert response.status_code == 422
    assert response.json()["detail"] == "cover_url cannot be null"
