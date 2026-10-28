from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import AliasPath, BaseModel, Field, computed_field

from app.schemas.common import ShippingAddress
from app.schemas.ormmodel import ORMModel


class OrderStatus(StrEnum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class OrderCreate(BaseModel):
    shipping_address: ShippingAddress


class OrderItemOut(ORMModel):
    book_id: int
    title: str = Field(validation_alias=AliasPath("book", "title"))
    quantity: int 
    unit_price: Decimal

    @computed_field
    def subtotal(self) -> Decimal:
        return self.quantity * self.unit_price


class OrderOut(ORMModel):
    id: int
    items: list[OrderItemOut]
    status: OrderStatus
    total_amount: Decimal
    shipping_address: ShippingAddress
    created_at: datetime
    paid_at: datetime | None



class OrderStatusUpdate(BaseModel):
    status: OrderStatus
