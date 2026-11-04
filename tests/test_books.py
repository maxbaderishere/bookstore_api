import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_books(client: AsyncClient):
    response = await client.get("/api/v1/books")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


