"""Права доступа: чтение публичное, изменения — только для администратора."""

import pytest
from httpx import AsyncClient

API = "/api/v1"

# (метод, путь, тело) — {id} подставляется id сущности из фикстуры
MUTATIONS = [
    ("POST", "/publishers", {"name": "P"}),
    ("PATCH", "/publishers/{publisher}", {"name": "P2"}),
    ("DELETE", "/publishers/{publisher}", None),
    ("POST", "/authors", {"full_name": "A"}),
    ("PATCH", "/authors/{author}", {"full_name": "A2"}),
    ("DELETE", "/authors/{author}", None),
    ("POST", "/books", {"title": "B"}),
    ("PATCH", "/books/{book}", {"title": "B2"}),
    ("DELETE", "/books/{book}", None),
]

READS = [
    "/publishers",
    "/publishers/{publisher}",
    "/authors",
    "/authors/{author}",
    "/books",
    "/books/{book}",
]


@pytest.fixture
def ids(book, author, publisher) -> dict[str, int]:
    return {"book": book.id, "author": author.id, "publisher": publisher.id}


@pytest.mark.parametrize(("method", "path", "body"), MUTATIONS)
async def test_mutation_requires_auth(
    anon_client: AsyncClient, ids, method, path, body
):
    response = await anon_client.request(method, API + path.format(**ids), json=body)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(("method", "path", "body"), MUTATIONS)
async def test_mutation_forbidden_for_customer(
    customer_client: AsyncClient, ids, method, path, body
):
    response = await customer_client.request(
        method, API + path.format(**ids), json=body
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


async def test_customer_cannot_change_data(customer_client: AsyncClient, book):
    await customer_client.delete(f"{API}/books/{book.id}")

    response = await customer_client.get(f"{API}/books/{book.id}")
    assert response.status_code == 200


@pytest.mark.parametrize("path", READS)
async def test_reads_are_public(anon_client: AsyncClient, ids, path):
    response = await anon_client.get(API + path.format(**ids))

    assert response.status_code == 200


async def test_admin_can_mutate(client: AsyncClient):
    response = await client.post(f"{API}/publishers", json={"name": "By admin"})

    assert response.status_code == 201
