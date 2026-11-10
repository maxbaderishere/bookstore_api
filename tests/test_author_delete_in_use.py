from httpx import AsyncClient

URL = "/api/v1/authors"


async def test_delete_author_with_books(client: AsyncClient, author, book):
    response = await client.delete(f"{URL}/{author.id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Author has books and cannot be deleted"

    assert (await client.get(f"{URL}/{author.id}")).status_code == 200
    book_authors = (await client.get(f"/api/v1/books/{book.id}")).json()["authors"]
    assert [a["id"] for a in book_authors] == [author.id]


async def test_delete_author_after_book_deleted(client: AsyncClient, author, book):
    await client.delete(f"/api/v1/books/{book.id}")

    response = await client.delete(f"{URL}/{author.id}")

    assert response.status_code == 204
