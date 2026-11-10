import pytest
from httpx import AsyncClient

URL = "/api/v1/publishers"
MISSING_ID = 999_999


# ---------- GET /publishers ----------


async def test_get_publishers(client: AsyncClient, publisher):
    response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert {"id": publisher.id, "name": publisher.name} in body


async def test_get_publishers_empty(client: AsyncClient):
    response = await client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


async def test_get_publishers_pagination(client: AsyncClient):
    for i in range(3):
        await client.post(URL, json={"name": f"publisher {i}"})

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
async def test_get_publishers_invalid_query(client: AsyncClient, params):
    response = await client.get(URL, params=params)

    assert response.status_code == 422


# ---------- GET /publishers/{id} ----------


async def test_show_publisher(client: AsyncClient, publisher):
    response = await client.get(f"{URL}/{publisher.id}")

    assert response.status_code == 200
    assert response.json() == {"id": publisher.id, "name": "Test Publisher"}


async def test_show_publisher_not_found(client: AsyncClient):
    response = await client.get(f"{URL}/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such publisher"


async def test_show_publisher_invalid_id(client: AsyncClient):
    response = await client.get(f"{URL}/abc")

    assert response.status_code == 422


# ---------- POST /publishers ----------


async def test_create_publisher(client: AsyncClient):
    response = await client.post(URL, json={"name": "test_publisher"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "test_publisher"
    assert isinstance(body["id"], int)

    fetched = await client.get(f"{URL}/{body['id']}")
    assert fetched.json() == body


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": None},
        {"name": "x" * 201},
        {"name": 123},
        {"title": "wrong field"},
    ],
    ids=["missing", "empty", "null", "too_long", "not_string", "wrong_field"],
)
async def test_create_publisher_invalid(client: AsyncClient, payload):
    response = await client.post(URL, json=payload)

    assert response.status_code == 422


async def test_create_publisher_max_length_name(client: AsyncClient):
    response = await client.post(URL, json={"name": "x" * 200})

    assert response.status_code == 201


async def test_create_publisher_not_json(client: AsyncClient):
    response = await client.post(
        URL, content="name=test", headers={"Content-Type": "text/plain"}
    )

    assert response.status_code == 422


async def test_create_publisher_duplicate_name(client: AsyncClient, publisher):
    response = await client.post(URL, json={"name": publisher.name})

    assert response.status_code == 409


# ---------- PATCH /publishers/{id} ----------


async def test_change_publisher(client: AsyncClient, publisher):
    response = await client.patch(f"{URL}/{publisher.id}", json={"name": "Renamed"})

    assert response.status_code == 200
    assert response.json() == {"id": publisher.id, "name": "Renamed"}

    fetched = await client.get(f"{URL}/{publisher.id}")
    assert fetched.json()["name"] == "Renamed"


async def test_change_publisher_empty_body(client: AsyncClient, publisher):
    response = await client.patch(f"{URL}/{publisher.id}", json={})

    assert response.status_code == 200
    assert response.json()["name"] == publisher.name


async def test_change_publisher_not_found(client: AsyncClient):
    response = await client.patch(f"{URL}/{MISSING_ID}", json={"name": "New"})

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such publisher"


@pytest.mark.parametrize(
    "payload",
    [{"name": ""}, {"name": "x" * 201}, {"name": 123}],
    ids=["empty", "too_long", "not_string"],
)
async def test_change_publisher_invalid(client: AsyncClient, publisher, payload):
    response = await client.patch(f"{URL}/{publisher.id}", json=payload)

    assert response.status_code == 422


async def test_change_publisher_duplicate_name(client: AsyncClient, publisher):
    other = await client.post(URL, json={"name": "Other Publisher"})

    response = await client.patch(
        f"{URL}/{other.json()['id']}", json={"name": publisher.name}
    )

    assert response.status_code == 409


# ---------- DELETE /publishers/{id} ----------


async def test_delete_publisher(client: AsyncClient, publisher):
    response = await client.delete(f"{URL}/{publisher.id}")

    assert response.status_code == 204
    assert response.content == b""

    fetched = await client.get(f"{URL}/{publisher.id}")
    assert fetched.status_code == 404


async def test_delete_publisher_not_found(client: AsyncClient):
    response = await client.delete(f"{URL}/{MISSING_ID}")

    assert response.status_code == 404


async def test_delete_publisher_invalid_id(client: AsyncClient):
    response = await client.delete(f"{URL}/abc")

    assert response.status_code == 422


async def test_delete_publisher_with_books_unlinks_them(
    client: AsyncClient, publisher, book
):
    response = await client.delete(f"{URL}/{publisher.id}")

    assert response.status_code == 204
    fetched = await client.get(f"/api/v1/books/{book.id}")
    assert fetched.status_code == 200
    assert fetched.json()["publisher"] is None
