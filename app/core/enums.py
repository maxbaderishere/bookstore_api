from enum import StrEnum


class Role(StrEnum):
    customer = "customer"
    admin = "admin"


class OrderStatus(StrEnum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
