from decimal import Decimal

import pytest
from httpx import AsyncClient

URL = "/api/v1/books"
MISSING_ID = 999_999


async def create_author(client: AsyncClient, name: str) -> int:
    response = await client.post("/api/v1/authors", json={"full_name": name})
    return response.json()["id"]


async def create_publisher(client: AsyncClient, name: str) -> int:
    response = await client.post("/api/v1/publishers", json={"name": name})
    return response.json()["id"]


# ---------- GET /books ----------


async def test_get_books(client: AsyncClient):
    response = await client.get(URL)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_books_contains_book_with_relations(client: AsyncClient, book):
    response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == book.id
    assert item["publisher"]["id"] == book.publisher_id
    assert [a["id"] for a in item["authors"]] == [book.authors[0].id]
    assert [g["id"] for g in item["genres"]] == [book.genres[0].id]


async def test_get_books_pagination_ordered_by_id(client: AsyncClient, book_payload):
    ids = []
    for i in range(3):
        payload = {**book_payload, "isbn": f"978000000000{i}", "title": f"Book {i}"}
        ids.append((await client.post(URL, json=payload)).json()["id"])

    first = await client.get(URL, params={"limit": 2})
    rest = await client.get(URL, params={"limit": 2, "offset": 2})

    assert [b["id"] for b in first.json()] == ids[:2]
    assert [b["id"] for b in rest.json()] == ids[2:]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": "abc"},
        {"offset": -1},
        {"offset": "abc"},
    ],
)
async def test_get_books_invalid_query(client: AsyncClient, params):
    response = await client.get(URL, params=params)

    assert response.status_code == 422


# ---------- GET /books/{id} ----------


async def test_show_book(client: AsyncClient, book):
    response = await client.get(f"{URL}/{book.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == book.id
    assert data["title"] == "Test book"
    assert data["isbn"] == "0" * 13
    assert Decimal(data["price"]) == 100
    assert "created_at" in data


async def test_show_book_not_found(client: AsyncClient):
    response = await client.get(f"{URL}/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such book"


async def test_show_book_invalid_id(client: AsyncClient):
    response = await client.get(f"{URL}/abc")

    assert response.status_code == 422


# ---------- POST /books ----------


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

    response = await client.post(URL, json=data)
    body = response.json()
    assert response.status_code == 201
    assert isinstance(body, dict)
    assert body["title"] == "Это я — Эдичка"
    assert body["publisher"]["id"] == publisher.id


async def test_create_book_returns_full_object(
    client: AsyncClient, book_payload, author, genre
):
    response = await client.post(URL, json=book_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["isbn"] == book_payload["isbn"]
    assert Decimal(body["price"]) == Decimal("450.00")
    assert body["stock"] == 5
    assert body["authors"] == [{"id": author.id, "full_name": author.full_name}]
    assert [g["id"] for g in body["genres"]] == [genre.id]

    fetched = await client.get(f"{URL}/{body['id']}")
    assert fetched.json() == body


async def test_create_book_without_publisher(client: AsyncClient, book_payload):
    del book_payload["publisher_id"]

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 201
    assert response.json()["publisher"] is None


async def test_create_book_default_stock(client: AsyncClient, book_payload):
    del book_payload["stock"]

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 201
    assert response.json()["stock"] == 0


async def test_create_book_duplicate_author_ids(
    client: AsyncClient, book_payload, author
):
    book_payload["author_ids"] = [author.id, author.id]

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 201
    assert [a["id"] for a in response.json()["authors"]] == [author.id]


async def test_create_book_several_authors(client: AsyncClient, book_payload, author):
    second = await create_author(client, "Second Author")
    book_payload["author_ids"] = [author.id, second]

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 201
    assert {a["id"] for a in response.json()["authors"]} == {author.id, second}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", "x" * 301),
        ("title", None),
        ("isbn", "978517000000"),  # 12 цифр
        ("isbn", "97851700000070"),  # 14 цифр
        ("isbn", "978517000000X"),
        ("isbn", "978-5170000007"),
        ("language", "EN"),
        ("language", "eng"),
        ("language", "r"),
        ("language", "р1"),
        ("price", -1),
        ("price", "10.001"),
        ("price", "123456789.00"),  # больше 10 знаков
        ("price", "abc"),
        ("stock", -1),
        ("stock", 1.5),
        ("pages", 0),
        ("pages", -10),
        ("publication_year", 1449),
        ("publication_year", 2101),
        ("cover_url", "x" * 501),
        ("author_ids", None),
        ("author_ids", "1"),
        ("author_ids", ["abc"]),
        ("genre_ids", None),
        ("publisher_id", "abc"),
    ],
)
async def test_create_book_invalid_field(
    client: AsyncClient, book_payload, field, value
):
    book_payload[field] = value

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field", ["title", "isbn", "language", "price", "author_ids", "genre_ids"]
)
async def test_create_book_missing_required_field(
    client: AsyncClient, book_payload, field
):
    del book_payload[field]

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 422


async def test_create_book_empty_body(client: AsyncClient):
    response = await client.post(URL, json={})

    assert response.status_code == 422


async def test_create_book_publisher_not_found(client: AsyncClient, book_payload):
    book_payload["publisher_id"] = MISSING_ID

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Publisher not found"


async def test_create_book_author_not_found(client: AsyncClient, book_payload, author):
    book_payload["author_ids"] = [author.id, MISSING_ID]

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Some authors not found"


async def test_create_book_genre_not_found(client: AsyncClient, book_payload):
    book_payload["genre_ids"] = [MISSING_ID]

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Some genres not found"


async def test_create_book_not_found_does_not_create(client: AsyncClient, book_payload):
    book_payload["genre_ids"] = [MISSING_ID]
    await client.post(URL, json=book_payload)

    response = await client.get(URL)

    assert response.json() == []


async def test_create_book_duplicate_isbn(client: AsyncClient, book, book_payload):
    book_payload["isbn"] = book.isbn

    response = await client.post(URL, json=book_payload)

    assert response.status_code == 409


# ---------- PATCH /books/{id} ----------


async def test_change_book(client: AsyncClient, book):
    response = await client.patch(
        f"{URL}/{book.id}", json={"title": "New title", "price": "99.99"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert Decimal(body["price"]) == Decimal("99.99")
    assert body["isbn"] == book.isbn  # не передан — не изменился

    fetched = await client.get(f"{URL}/{book.id}")
    assert fetched.json() == body


async def test_change_book_empty_body(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={})

    assert response.status_code == 200
    assert response.json()["title"] == book.title


async def test_change_book_replace_authors_and_genres(client: AsyncClient, book):
    new_author = await create_author(client, "Replacement Author")

    # жанры 1 и 2 создаются сидом (app/db/seeds.py)
    response = await client.patch(
        f"{URL}/{book.id}", json={"author_ids": [new_author], "genre_ids": [1, 2]}
    )

    assert response.status_code == 200
    body = response.json()
    assert [a["id"] for a in body["authors"]] == [new_author]
    assert {g["id"] for g in body["genres"]} == {1, 2}


async def test_change_book_clear_genres(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={"genre_ids": []})

    assert response.status_code == 200
    assert response.json()["genres"] == []


async def test_change_book_change_publisher(client: AsyncClient, book):
    new_publisher = await create_publisher(client, "New Publisher")

    response = await client.patch(
        f"{URL}/{book.id}", json={"publisher_id": new_publisher}
    )

    assert response.status_code == 200
    assert response.json()["publisher"]["id"] == new_publisher


async def test_change_book_unset_publisher(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={"publisher_id": None})

    assert response.status_code == 200
    assert response.json()["publisher"] is None


async def test_change_book_nullable_description(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={"description": None})

    assert response.status_code == 200
    assert response.json()["description"] is None


@pytest.mark.parametrize(
    "field",
    ["title", "isbn", "price", "stock", "publication_year", "language", "pages"],
)
async def test_change_book_not_nullable_field(client: AsyncClient, book, field):
    response = await client.patch(f"{URL}/{book.id}", json={field: None})

    assert response.status_code == 422
    assert response.json()["detail"] == f"{field} cannot be null"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("isbn", "123"),
        ("language", "EN"),
        ("price", -1),
        ("stock", -1),
        ("pages", 0),
        ("publication_year", 1449),
        ("cover_url", "x" * 501),
        ("author_ids", ["abc"]),
    ],
)
async def test_change_book_invalid_field(client: AsyncClient, book, field, value):
    response = await client.patch(f"{URL}/{book.id}", json={field: value})

    assert response.status_code == 422


async def test_change_book_not_found(client: AsyncClient):
    response = await client.patch(f"{URL}/{MISSING_ID}", json={"title": "X"})

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such book"


async def test_change_book_publisher_not_found(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={"publisher_id": MISSING_ID})

    assert response.status_code == 404
    assert response.json()["detail"] == "Publisher not found"


async def test_change_book_author_not_found(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={"author_ids": [MISSING_ID]})

    assert response.status_code == 404
    assert response.json()["detail"] == "Some authors not found"


async def test_change_book_genre_not_found(client: AsyncClient, book):
    response = await client.patch(f"{URL}/{book.id}", json={"genre_ids": [MISSING_ID]})

    assert response.status_code == 404
    assert response.json()["detail"] == "Some genres not found"


async def test_change_book_duplicate_isbn(client: AsyncClient, book, book_payload):
    other = (await client.post(URL, json=book_payload)).json()

    response = await client.patch(f"{URL}/{other['id']}", json={"isbn": book.isbn})

    assert response.status_code == 409


# ---------- DELETE /books/{id} ----------


async def test_delete_book(client: AsyncClient, book):
    response = await client.delete(f"{URL}/{book.id}")

    assert response.status_code == 204
    assert response.content == b""

    fetched = await client.get(f"{URL}/{book.id}")
    assert fetched.status_code == 404


async def test_delete_book_keeps_related_entities(
    client: AsyncClient, book, author, publisher
):
    await client.delete(f"{URL}/{book.id}")

    assert (await client.get(f"/api/v1/authors/{author.id}")).status_code == 200
    assert (await client.get(f"/api/v1/publishers/{publisher.id}")).status_code == 200


async def test_delete_book_not_found(client: AsyncClient):
    response = await client.delete(f"{URL}/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such book"


async def test_delete_book_invalid_id(client: AsyncClient):
    response = await client.delete(f"{URL}/abc")

    assert response.status_code == 422
