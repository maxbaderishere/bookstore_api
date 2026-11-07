import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_books(client: AsyncClient):
    response = await client.get("/api/v1/books")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_books(client: AsyncClient, author, publisher, genre):
    data = {
        "title": "Это я — Эдичка",
        "description": "Дебютный автобиографический роман Эдуарда Лимонова, написанный в 1976 году в Нью-Йорке. От первого лица рассказывает о жизни русского эмигранта-поэта на дне американского общества: нищета, одиночество, разрыв с женой Еленой, случайные связи и поиск своего места в чужой стране. Роман отличается откровенностью и эпатажем, из-за чего считается одним из самых скандальных произведений русской литературы XX века.",
        "isbn": "9785170000007",
        "publisher_id": publisher.id,
        "publication_year": 1979,
        "language": "ru",
        "pages": 320,
        "price": 450,
        "stock": 1,
        "cover_url": "string",
        "author_ids": [author.id],
        "genre_ids": [genre.id],
    }

    response = await client.post("/api/v1/books", json=data)
    body = response.json()
    assert response.status_code == 201
    assert isinstance(body, dict)
    assert body["title"] == "Это я — Эдичка"
    assert body["publisher"]["id"] == publisher.id


@pytest.mark.asyncio
async def test_show_book(client: AsyncClient, book):
    response = await client.get(f"/api/v1/books/{book.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == book.id
    assert data["title"] == "Test book"
    assert data["isbn"] == "0" * 13
