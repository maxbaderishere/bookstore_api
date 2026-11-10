import pytest
from httpx import AsyncClient

URL = "/api/v1/authors"
MISSING_ID = 999_999


# ---------- GET /authors ----------


async def test_get_authors(client: AsyncClient, author):
    response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert [a["id"] for a in body] == [author.id]
    assert body[0]["full_name"] == "Test Author"


async def test_get_authors_empty(client: AsyncClient):
    response = await client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


async def test_get_authors_pagination(client: AsyncClient):
    for i in range(3):
        await client.post(URL, json={"full_name": f"Author {i}"})

    first = await client.get(URL, params={"limit": 2})
    rest = await client.get(URL, params={"limit": 2, "offset": 2})

    assert first.status_code == 200
    assert len(first.json()) == 2
    assert len(rest.json()) == 1


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
async def test_get_authors_invalid_query(client: AsyncClient, params):
    response = await client.get(URL, params=params)

    assert response.status_code == 422


# ---------- GET /authors/{id} ----------


async def test_show_author(client: AsyncClient, author):
    response = await client.get(f"{URL}/{author.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": author.id,
        "full_name": "Test Author",
        "bio": None,
        "birth_year": 1900,
    }


async def test_show_author_not_found(client: AsyncClient):
    response = await client.get(f"{URL}/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such author"


async def test_show_author_invalid_id(client: AsyncClient):
    response = await client.get(f"{URL}/abc")

    assert response.status_code == 422


# ---------- POST /authors ----------


async def test_create_author(client: AsyncClient):
    payload = {"full_name": "Лев Толстой", "birth_year": 1828, "bio": "Writer"}

    response = await client.post(URL, json=payload)

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body == {"id": body["id"], **payload}

    fetched = await client.get(f"{URL}/{body['id']}")
    assert fetched.json() == body


async def test_create_author_only_required_fields(client: AsyncClient):
    response = await client.post(URL, json={"full_name": "Anonymous"})

    assert response.status_code == 201
    body = response.json()
    assert body["bio"] is None
    assert body["birth_year"] is None


@pytest.mark.parametrize("birth_year", [1450, 2100])
async def test_create_author_birth_year_bounds(client: AsyncClient, birth_year):
    response = await client.post(
        URL, json={"full_name": "Edge", "birth_year": birth_year}
    )

    assert response.status_code == 201
    assert response.json()["birth_year"] == birth_year


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"full_name": ""},
        {"full_name": None},
        {"full_name": "x" * 201},
        {"full_name": 123},
        {"full_name": "A", "birth_year": 1449},
        {"full_name": "A", "birth_year": 2101},
        {"full_name": "A", "birth_year": "nineteen hundred"},
        {"full_name": "A", "birth_year": 1900.5},
        {"full_name": "A", "bio": 123},
    ],
    ids=[
        "missing_name",
        "empty_name",
        "null_name",
        "too_long_name",
        "name_not_string",
        "birth_year_too_small",
        "birth_year_too_big",
        "birth_year_string",
        "birth_year_float",
        "bio_not_string",
    ],
)
async def test_create_author_invalid(client: AsyncClient, payload):
    response = await client.post(URL, json=payload)

    assert response.status_code == 422


async def test_create_author_not_json(client: AsyncClient):
    response = await client.post(
        URL, content="full_name=x", headers={"Content-Type": "text/plain"}
    )

    assert response.status_code == 422


# ---------- PATCH /authors/{id} ----------


async def test_change_author(client: AsyncClient, author):
    response = await client.patch(
        f"{URL}/{author.id}", json={"full_name": "Renamed", "bio": "New bio"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Renamed"
    assert body["bio"] == "New bio"
    assert body["birth_year"] == 1900  # не передан — не изменился

    fetched = await client.get(f"{URL}/{author.id}")
    assert fetched.json() == body


async def test_change_author_empty_body(client: AsyncClient, author):
    response = await client.patch(f"{URL}/{author.id}", json={})

    assert response.status_code == 200
    assert response.json()["full_name"] == author.full_name


async def test_change_author_nullable_fields_to_null(client: AsyncClient, author):
    response = await client.patch(
        f"{URL}/{author.id}", json={"bio": None, "birth_year": None}
    )

    assert response.status_code == 200
    assert response.json()["bio"] is None
    assert response.json()["birth_year"] is None


async def test_change_author_full_name_null(client: AsyncClient, author):
    response = await client.patch(f"{URL}/{author.id}", json={"full_name": None})

    assert response.status_code == 422
    assert response.json()["detail"] == "full_name cannot be null"


async def test_change_author_not_found(client: AsyncClient):
    response = await client.patch(f"{URL}/{MISSING_ID}", json={"full_name": "X"})

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such author"


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": ""},
        {"full_name": "x" * 201},
        {"birth_year": 1449},
        {"birth_year": 2101},
        {"birth_year": "abc"},
    ],
    ids=["empty_name", "too_long_name", "year_small", "year_big", "year_string"],
)
async def test_change_author_invalid(client: AsyncClient, author, payload):
    response = await client.patch(f"{URL}/{author.id}", json=payload)

    assert response.status_code == 422


# ---------- DELETE /authors/{id} ----------


async def test_delete_author(client: AsyncClient, author):
    response = await client.delete(f"{URL}/{author.id}")

    assert response.status_code == 204
    assert response.content == b""

    fetched = await client.get(f"{URL}/{author.id}")
    assert fetched.status_code == 404


async def test_delete_author_invalid_id(client: AsyncClient):
    response = await client.delete(f"{URL}/abc")

    assert response.status_code == 422
