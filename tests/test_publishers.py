import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_publisher(client: AsyncClient):

    publisher_data = {"name": "test_publisher"}

    response = await client.post("/api/v1/publishers", json=publisher_data)
    assert response.status_code == 201
    assert response.json()["name"] == "test_publisher"
