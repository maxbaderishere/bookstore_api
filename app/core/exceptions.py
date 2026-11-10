"""Доменные исключения приложения.

Сервисы бросают их, а обработчики из app/core/exception_handlers.py
переводят их в HTTP-ответы.
"""


class AppError(Exception):
    """Базовое исключение приложения."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    """Сущность не найдена (404)."""


class ConflictError(AppError):
    """Операция противоречит текущему состоянию данных (409)."""


class RefreshTokenError(AppError):
    """Refresh-токен невалиден, просрочен, отозван или принадлежит неактивному юзеру."""


# ---------- корзина ----------


class BookNotFoundError(NotFoundError):
    def __init__(self, book_id: int) -> None:
        super().__init__(f"Book {book_id} not found")
        self.book_id = book_id


class CartItemNotFoundError(NotFoundError):
    def __init__(self, book_id: int) -> None:
        super().__init__(f"Book {book_id} is not in the cart")
        self.book_id = book_id


class InsufficientStockError(ConflictError):
    def __init__(self, book_id: int, requested: int, available: int) -> None:
        super().__init__(
            f"Not enough stock for book {book_id}: "
            f"requested {requested}, available {available}"
        )
        self.book_id = book_id
        self.requested = requested
        self.available = available


# ---------- заказы ----------


class EmptyCartError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Cart is empty")


class OrderNotFoundError(NotFoundError):
    def __init__(self, order_id: int) -> None:
        super().__init__(f"Order {order_id} not found")
        self.order_id = order_id


class InvalidStatusTransitionError(ConflictError):
    def __init__(self, current: str, new: str) -> None:
        super().__init__(f"Cannot change order status from {current} to {new}")
        self.current = current
        self.new = new
