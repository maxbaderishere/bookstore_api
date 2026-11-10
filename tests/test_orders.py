from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.enums import OrderStatus
from app.models.book import Book

URL = "/api/v1/orders"
CART = "/api/v1/cart"
BOOKS = "/api/v1/books"
MISSING_ID = 999_999
ADDRESS = {"shipping_address": "Moscow, Tverskaya 1"}


async def make_book(db, isbn: str, price: str, stock: int, title: str) -> Book:
    obj = Book(
        title=title,
        isbn=isbn,
        language="en",
        price=Decimal(price),
        stock=stock,
        cover_url="https://example.com/c.jpg",
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@pytest_asyncio.fixture
async def book_a(db) -> Book:
    return await make_book(db, "1" * 13, "10.50", 5, "Book A")


@pytest_asyncio.fixture
async def book_b(db) -> Book:
    return await make_book(db, "2" * 13, "3.00", 10, "Book B")


async def add_to_cart(client: AsyncClient, book_id: int, quantity: int):
    response = await client.post(
        f"{CART}/items", json={"book_id": book_id, "quantity": quantity}
    )
    assert response.status_code == 200


async def stock_of(client: AsyncClient, book_id: int) -> int:
    return (await client.get(f"{BOOKS}/{book_id}")).json()["stock"]


@pytest_asyncio.fixture
async def order(customer_client: AsyncClient, book_a, book_b) -> dict:
    """Оформленный покупателем заказ: 2 × Book A + 3 × Book B."""
    await add_to_cart(customer_client, book_a.id, 2)
    await add_to_cart(customer_client, book_b.id, 3)
    response = await customer_client.post(URL, json=ADDRESS)
    assert response.status_code == 201
    return response.json()


async def set_status(client: AsyncClient, order_id: int, status: str):
    return await client.patch(f"{URL}/{order_id}/status", json={"status": status})


# ---------- доступ ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", ""),
        ("GET", ""),
        ("GET", "/all"),
        ("GET", "/1"),
        ("POST", "/1/cancel"),
        ("PATCH", "/1/status"),
    ],
)
async def test_orders_require_auth(anon_client: AsyncClient, method, path):
    response = await anon_client.request(method, URL + path, json={})

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("GET", "/all", None), ("PATCH", "/1/status", {"status": "paid"})],
)
async def test_admin_only_endpoints(customer_client: AsyncClient, method, path, body):
    response = await customer_client.request(method, URL + path, json=body)

    assert response.status_code == 403


# ---------- POST /orders ----------


async def test_create_order(customer_client: AsyncClient, order, book_a, book_b):
    assert order["status"] == "pending"
    assert order["shipping_address"] == ADDRESS["shipping_address"]
    assert order["paid_at"] is None
    assert Decimal(order["total_amount"]) == Decimal("30.00")  # 2*10.50 + 3*3.00
    assert [
        (i["book_id"], i["title"], i["quantity"], Decimal(i["unit_price"]))
        for i in order["items"]
    ] == [
        (book_a.id, "Book A", 2, Decimal("10.50")),
        (book_b.id, "Book B", 3, Decimal("3.00")),
    ]
    assert Decimal(order["items"][0]["subtotal"]) == Decimal("21.00")


async def test_create_order_decrements_stock(
    customer_client: AsyncClient, order, book_a, book_b
):
    assert await stock_of(customer_client, book_a.id) == 3
    assert await stock_of(customer_client, book_b.id) == 7


async def test_create_order_clears_cart(customer_client: AsyncClient, order):
    cart = (await customer_client.get(CART)).json()

    assert cart["items"] == []


async def test_create_order_invalidates_book_cache(
    customer_client: AsyncClient, book_a
):
    await customer_client.get(f"{BOOKS}/{book_a.id}")  # прогреваем кэш
    await add_to_cart(customer_client, book_a.id, 1)

    await customer_client.post(URL, json=ADDRESS)

    response = await customer_client.get(f"{BOOKS}/{book_a.id}")
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()["stock"] == 4


async def test_order_keeps_price_at_purchase(
    customer_client: AsyncClient, client: AsyncClient, order, book_a
):
    await client.patch(f"{BOOKS}/{book_a.id}", json={"price": "99.00"})

    fetched = (await customer_client.get(f"{URL}/{order['id']}")).json()

    assert Decimal(fetched["items"][0]["unit_price"]) == Decimal("10.50")
    assert Decimal(fetched["total_amount"]) == Decimal("30.00")


async def test_create_order_empty_cart(customer_client: AsyncClient):
    response = await customer_client.post(URL, json=ADDRESS)

    assert response.status_code == 409
    assert response.json()["detail"] == "Cart is empty"


async def test_create_order_stock_dropped_after_adding_to_cart(
    customer_client: AsyncClient, client: AsyncClient, book_a, book_b
):
    await add_to_cart(customer_client, book_b.id, 1)
    await add_to_cart(customer_client, book_a.id, 5)
    await client.patch(f"{BOOKS}/{book_a.id}", json={"stock": 2})

    response = await customer_client.post(URL, json=ADDRESS)

    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Not enough stock for book {book_a.id}: requested 5, available 2"
    )
    # ничего не списано и корзина цела
    assert await stock_of(customer_client, book_b.id) == 10
    assert len((await customer_client.get(CART)).json()["items"]) == 2
    assert (await customer_client.get(URL)).json() == []


async def test_two_customers_compete_for_last_items(
    customer_client: AsyncClient, client: AsyncClient, book_a
):
    """Корзина не резервирует товар: второй заказ на тот же остаток отклоняется."""
    await add_to_cart(customer_client, book_a.id, 5)
    await add_to_cart(client, book_a.id, 5)

    first = await customer_client.post(URL, json=ADDRESS)
    second = await client.post(URL, json=ADDRESS)

    assert first.status_code == 201
    assert second.status_code == 409
    assert await stock_of(client, book_a.id) == 0


async def test_create_order_archived_book(customer_client: AsyncClient, db, book_a):
    await add_to_cart(customer_client, book_a.id, 1)
    book_a.is_archived = True
    await db.commit()

    response = await customer_client.post(URL, json=ADDRESS)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{}, {"shipping_address": ""}, {"shipping_address": "x" * 501}],
    ids=["missing", "empty", "too_long"],
)
async def test_create_order_invalid_address(
    customer_client: AsyncClient, book_a, payload
):
    await add_to_cart(customer_client, book_a.id, 1)

    response = await customer_client.post(URL, json=payload)

    assert response.status_code == 422


# ---------- GET /orders ----------


async def test_my_orders(customer_client: AsyncClient, order, book_a):
    await add_to_cart(customer_client, book_a.id, 1)
    second = (await customer_client.post(URL, json=ADDRESS)).json()

    response = await customer_client.get(URL)

    assert response.status_code == 200
    assert [o["id"] for o in response.json()] == [second["id"], order["id"]]


async def test_my_orders_only_own(
    customer_client: AsyncClient, client: AsyncClient, order
):
    response = await client.get(URL)  # администратор, своих заказов нет

    assert response.json() == []


async def test_my_orders_pagination(customer_client: AsyncClient, order, book_a):
    await add_to_cart(customer_client, book_a.id, 1)
    await customer_client.post(URL, json=ADDRESS)

    page = await customer_client.get(URL, params={"limit": 1, "offset": 1})

    assert [o["id"] for o in page.json()] == [order["id"]]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
async def test_my_orders_invalid_query(customer_client: AsyncClient, params):
    response = await customer_client.get(URL, params=params)

    assert response.status_code == 422


# ---------- GET /orders/all ----------


async def test_all_orders(client: AsyncClient, order):
    response = await client.get(f"{URL}/all")

    assert response.status_code == 200
    assert [o["id"] for o in response.json()] == [order["id"]]


async def test_all_orders_filter_by_status(client: AsyncClient, order):
    pending = await client.get(f"{URL}/all", params={"status": "pending"})
    paid = await client.get(f"{URL}/all", params={"status": "paid"})

    assert len(pending.json()) == 1
    assert paid.json() == []


async def test_all_orders_invalid_status(client: AsyncClient):
    response = await client.get(f"{URL}/all", params={"status": "lost"})

    assert response.status_code == 422


# ---------- GET /orders/{id} ----------


async def test_show_order(customer_client: AsyncClient, order):
    response = await customer_client.get(f"{URL}/{order['id']}")

    assert response.status_code == 200
    assert response.json() == order


async def test_show_order_by_admin(client: AsyncClient, order):
    response = await client.get(f"{URL}/{order['id']}")

    assert response.status_code == 200


async def test_show_other_users_order(
    customer_client: AsyncClient, client: AsyncClient, book_a
):
    await add_to_cart(client, book_a.id, 1)
    admin_order = (await client.post(URL, json=ADDRESS)).json()

    response = await customer_client.get(f"{URL}/{admin_order['id']}")

    assert response.status_code == 404


async def test_show_order_not_found(customer_client: AsyncClient):
    response = await customer_client.get(f"{URL}/{MISSING_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == f"Order {MISSING_ID} not found"


async def test_show_order_invalid_id(customer_client: AsyncClient):
    response = await customer_client.get(f"{URL}/abc")

    assert response.status_code == 422


# ---------- POST /orders/{id}/cancel ----------


async def test_cancel_order(customer_client: AsyncClient, order, book_a, book_b):
    response = await customer_client.post(f"{URL}/{order['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert await stock_of(customer_client, book_a.id) == 5
    assert await stock_of(customer_client, book_b.id) == 10


async def test_cancel_twice(customer_client: AsyncClient, order, book_a):
    await customer_client.post(f"{URL}/{order['id']}/cancel")

    response = await customer_client.post(f"{URL}/{order['id']}/cancel")

    assert response.status_code == 409
    assert await stock_of(customer_client, book_a.id) == 5  # не вернули дважды


async def test_cancel_paid_order_by_customer(
    customer_client: AsyncClient, client: AsyncClient, order
):
    await set_status(client, order["id"], "paid")

    response = await customer_client.post(f"{URL}/{order['id']}/cancel")

    assert response.status_code == 409
    assert (
        response.json()["detail"] == "Cannot change order status from paid to cancelled"
    )


async def test_cancel_other_users_order(
    customer_client: AsyncClient, client: AsyncClient, book_a
):
    await add_to_cart(client, book_a.id, 1)
    admin_order = (await client.post(URL, json=ADDRESS)).json()

    response = await customer_client.post(f"{URL}/{admin_order['id']}/cancel")

    assert response.status_code == 404


async def test_cancel_not_found(customer_client: AsyncClient):
    response = await customer_client.post(f"{URL}/{MISSING_ID}/cancel")

    assert response.status_code == 404


# ---------- PATCH /orders/{id}/status ----------


async def test_full_lifecycle(client: AsyncClient, order):
    paid = await set_status(client, order["id"], "paid")
    assert paid.status_code == 200
    assert paid.json()["paid_at"] is not None

    for status in ("shipped", "delivered"):
        response = await set_status(client, order["id"], status)
        assert response.status_code == 200
        assert response.json()["status"] == status


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ([], "shipped"),
        ([], "delivered"),
        ([], "pending"),
        (["paid"], "pending"),
        (["paid"], "delivered"),
        (["paid", "shipped"], "cancelled"),
        (["paid", "shipped", "delivered"], "cancelled"),
        (["cancelled"], "paid"),
    ],
)
async def test_invalid_transitions(client: AsyncClient, order, path, target):
    for status in path:
        assert (await set_status(client, order["id"], status)).status_code == 200

    response = await set_status(client, order["id"], target)

    assert response.status_code == 409


async def test_admin_cancels_paid_order_restores_stock(
    client: AsyncClient, order, book_a
):
    await set_status(client, order["id"], "paid")

    response = await set_status(client, order["id"], "cancelled")

    assert response.status_code == 200
    assert await stock_of(client, book_a.id) == 5


async def test_set_status_not_found(client: AsyncClient):
    response = await set_status(client, MISSING_ID, "paid")

    assert response.status_code == 404


@pytest.mark.parametrize("payload", [{}, {"status": "lost"}, {"status": None}])
async def test_set_status_invalid_body(client: AsyncClient, order, payload):
    response = await client.patch(f"{URL}/{order['id']}/status", json=payload)

    assert response.status_code == 422


# ---------- связь с каталогом ----------


async def test_cannot_delete_ordered_book(client: AsyncClient, order, book_a):
    response = await client.delete(f"{BOOKS}/{book_a.id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Book has orders and cannot be deleted"
    assert (await client.get(f"{BOOKS}/{book_a.id}")).status_code == 200


def test_status_enum_values():
    assert {s.value for s in OrderStatus} == {
        "pending",
        "paid",
        "shipped",
        "delivered",
        "cancelled",
    }
