from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.book import Book

URL = "/api/v1/cart"
MISSING_ID = 999_999


@pytest_asyncio.fixture
async def stocked_book(db, publisher, author, genre) -> Book:
    obj = Book(
        title="Stocked book",
        isbn="1" * 13,
        publisher_id=publisher.id,
        language="en",
        price=Decimal("10.50"),
        stock=5,
        cover_url="https://example.com/s.jpg",
        authors=[author],
        genres=[genre],
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@pytest_asyncio.fixture
async def second_book(db) -> Book:
    obj = Book(
        title="Second book",
        isbn="2" * 13,
        language="en",
        price=Decimal("3.00"),
        stock=10,
        cover_url="https://example.com/2.jpg",
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def add(client: AsyncClient, book_id: int, quantity: int = 1):
    return await client.post(
        f"{URL}/items", json={"book_id": book_id, "quantity": quantity}
    )


# ---------- доступ ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", ""),
        ("POST", "/items"),
        ("PATCH", "/items/1"),
        ("DELETE", "/items/1"),
        ("DELETE", ""),
    ],
)
async def test_cart_requires_auth(anon_client: AsyncClient, method, path):
    response = await anon_client.request(
        method, URL + path, json={"book_id": 1, "quantity": 1}
    )

    assert response.status_code == 401


# ---------- GET /cart ----------


async def test_empty_cart(customer_client: AsyncClient):
    response = await customer_client.get(URL)

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total_quantity": 0,
        "total_amount": "0",
    }


async def test_cart_totals(customer_client: AsyncClient, stocked_book, second_book):
    await add(customer_client, stocked_book.id, 2)
    await add(customer_client, second_book.id, 3)

    body = (await customer_client.get(URL)).json()

    assert [i["book"]["id"] for i in body["items"]] == [stocked_book.id, second_book.id]
    assert Decimal(body["items"][0]["subtotal"]) == Decimal("21.00")
    assert body["total_quantity"] == 5
    assert Decimal(body["total_amount"]) == Decimal("30.00")


# ---------- POST /cart/items ----------


async def test_add_to_cart(customer_client: AsyncClient, stocked_book):
    response = await add(customer_client, stocked_book.id, 2)

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert item["quantity"] == 2
    assert item["book"] == {
        "id": stocked_book.id,
        "title": "Stocked book",
        "price": "10.50",
        "stock": 5,
        "cover_url": "https://example.com/s.jpg",
    }


async def test_add_default_quantity(customer_client: AsyncClient, stocked_book):
    response = await customer_client.post(
        f"{URL}/items", json={"book_id": stocked_book.id}
    )

    assert response.json()["items"][0]["quantity"] == 1


async def test_add_same_book_sums_quantity(customer_client: AsyncClient, stocked_book):
    await add(customer_client, stocked_book.id, 2)

    response = await add(customer_client, stocked_book.id, 3)

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert item["quantity"] == 5


async def test_add_exactly_stock(customer_client: AsyncClient, stocked_book):
    response = await add(customer_client, stocked_book.id, 5)

    assert response.status_code == 200


async def test_add_more_than_stock(customer_client: AsyncClient, stocked_book):
    response = await add(customer_client, stocked_book.id, 6)

    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Not enough stock for book {stocked_book.id}: requested 6, available 5"
    )
    assert (await customer_client.get(URL)).json()["items"] == []


async def test_add_sum_exceeds_stock(customer_client: AsyncClient, stocked_book):
    await add(customer_client, stocked_book.id, 4)

    response = await add(customer_client, stocked_book.id, 2)

    assert response.status_code == 409
    [item] = (await customer_client.get(URL)).json()["items"]
    assert item["quantity"] == 4  # не изменилось


async def test_add_out_of_stock_book(customer_client: AsyncClient, db, stocked_book):
    stocked_book.stock = 0
    await db.commit()

    response = await add(customer_client, stocked_book.id)

    assert response.status_code == 409


async def test_add_missing_book(customer_client: AsyncClient):
    response = await add(customer_client, MISSING_ID)

    assert response.status_code == 404
    assert response.json()["detail"] == f"Book {MISSING_ID} not found"


async def test_add_archived_book(customer_client: AsyncClient, db, stocked_book):
    stocked_book.is_archived = True
    await db.commit()

    response = await add(customer_client, stocked_book.id)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"quantity": 1},
        {"book_id": "abc"},
        {"book_id": 1, "quantity": 0},
        {"book_id": 1, "quantity": -1},
        {"book_id": 1, "quantity": "many"},
        {"book_id": 1, "quantity": 1.5},
    ],
)
async def test_add_invalid_body(customer_client: AsyncClient, payload):
    response = await customer_client.post(f"{URL}/items", json=payload)

    assert response.status_code == 422


# ---------- изоляция пользователей ----------


async def test_carts_are_per_user(
    customer_client: AsyncClient, client: AsyncClient, stocked_book, second_book
):
    await add(customer_client, stocked_book.id, 2)
    await add(client, second_book.id, 1)  # client — администратор

    customer_cart = (await customer_client.get(URL)).json()
    admin_cart = (await client.get(URL)).json()

    assert [i["book"]["id"] for i in customer_cart["items"]] == [stocked_book.id]
    assert [i["book"]["id"] for i in admin_cart["items"]] == [second_book.id]


async def test_stock_check_is_per_user(
    customer_client: AsyncClient, client: AsyncClient, stocked_book
):
    """Корзина не резервирует товар: оба могут положить весь остаток."""
    assert (await add(customer_client, stocked_book.id, 5)).status_code == 200
    assert (await add(client, stocked_book.id, 5)).status_code == 200


async def test_cannot_change_other_users_item(
    customer_client: AsyncClient, client: AsyncClient, stocked_book
):
    await add(client, stocked_book.id, 1)

    patch = await customer_client.patch(
        f"{URL}/items/{stocked_book.id}", json={"quantity": 2}
    )
    delete = await customer_client.delete(f"{URL}/items/{stocked_book.id}")

    assert patch.status_code == delete.status_code == 404
    assert (await client.get(URL)).json()["items"][0]["quantity"] == 1


async def test_clear_does_not_touch_other_users(
    customer_client: AsyncClient, client: AsyncClient, stocked_book
):
    await add(client, stocked_book.id, 1)
    await add(customer_client, stocked_book.id, 1)

    await customer_client.delete(URL)

    assert len((await client.get(URL)).json()["items"]) == 1


# ---------- PATCH /cart/items/{book_id} ----------


async def test_change_quantity(customer_client: AsyncClient, stocked_book):
    await add(customer_client, stocked_book.id, 1)

    response = await customer_client.patch(
        f"{URL}/items/{stocked_book.id}", json={"quantity": 4}
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["quantity"] == 4


async def test_change_quantity_down(customer_client: AsyncClient, stocked_book):
    await add(customer_client, stocked_book.id, 4)

    response = await customer_client.patch(
        f"{URL}/items/{stocked_book.id}", json={"quantity": 1}
    )

    assert response.json()["items"][0]["quantity"] == 1


async def test_change_quantity_over_stock(customer_client: AsyncClient, stocked_book):
    await add(customer_client, stocked_book.id, 1)

    response = await customer_client.patch(
        f"{URL}/items/{stocked_book.id}", json={"quantity": 6}
    )

    assert response.status_code == 409
    assert (await customer_client.get(URL)).json()["items"][0]["quantity"] == 1


async def test_change_quantity_not_in_cart(customer_client: AsyncClient, stocked_book):
    response = await customer_client.patch(
        f"{URL}/items/{stocked_book.id}", json={"quantity": 1}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == f"Book {stocked_book.id} is not in the cart"


@pytest.mark.parametrize("payload", [{}, {"quantity": 0}, {"quantity": -2}])
async def test_change_quantity_invalid(
    customer_client: AsyncClient, stocked_book, payload
):
    await add(customer_client, stocked_book.id, 1)

    response = await customer_client.patch(
        f"{URL}/items/{stocked_book.id}", json=payload
    )

    assert response.status_code == 422


# ---------- DELETE /cart/items/{book_id} ----------


async def test_remove_from_cart(
    customer_client: AsyncClient, stocked_book, second_book
):
    await add(customer_client, stocked_book.id)
    await add(customer_client, second_book.id)

    response = await customer_client.delete(f"{URL}/items/{stocked_book.id}")

    assert response.status_code == 204
    items = (await customer_client.get(URL)).json()["items"]
    assert [i["book"]["id"] for i in items] == [second_book.id]


async def test_remove_not_in_cart(customer_client: AsyncClient):
    response = await customer_client.delete(f"{URL}/items/{MISSING_ID}")

    assert response.status_code == 404


async def test_remove_invalid_id(customer_client: AsyncClient):
    response = await customer_client.delete(f"{URL}/items/abc")

    assert response.status_code == 422


# ---------- DELETE /cart ----------


async def test_clear_cart(customer_client: AsyncClient, stocked_book, second_book):
    await add(customer_client, stocked_book.id)
    await add(customer_client, second_book.id)

    response = await customer_client.delete(URL)

    assert response.status_code == 204
    assert (await customer_client.get(URL)).json()["items"] == []


async def test_clear_empty_cart(customer_client: AsyncClient):
    response = await customer_client.delete(URL)

    assert response.status_code == 204


# ---------- связь с каталогом ----------


async def test_deleted_book_disappears_from_cart(
    customer_client: AsyncClient, client: AsyncClient, stocked_book
):
    await add(customer_client, stocked_book.id)

    await client.delete(f"/api/v1/books/{stocked_book.id}")

    assert (await customer_client.get(URL)).json()["items"] == []


async def test_cart_shows_current_price(
    customer_client: AsyncClient, client: AsyncClient, stocked_book
):
    await add(customer_client, stocked_book.id, 2)

    await client.patch(f"/api/v1/books/{stocked_book.id}", json={"price": "20.00"})

    body = (await customer_client.get(URL)).json()
    assert Decimal(body["total_amount"]) == Decimal("40.00")
