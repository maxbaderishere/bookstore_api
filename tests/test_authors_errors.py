from httpx import AsyncClient

URL = "/api/v1/authors"
MISSING_ID = 999_999


async def test_delete_author_not_found(client: AsyncClient):
    response = await client.delete(f"{URL}/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "There is no such author"
