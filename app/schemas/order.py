from datetime import datetime
from decimal import Decimal

from pydantic import AliasPath, BaseModel, Field, computed_field

from app.core.enums import OrderStatus
from app.schemas.common import ShippingAddress
from app.schemas.out_schema import out_schema


class OrderCreate(BaseModel):
    shipping_address: ShippingAddress


@out_schema
class OrderItemOut(BaseModel):
    book_id: int
    title: str = Field(validation_alias=AliasPath("book", "title"))
    quantity: int
    unit_price: Decimal

    @computed_field
    def subtotal(self) -> Decimal:
        return self.quantity * self.unit_price


@out_schema
class OrderOut(BaseModel):
    id: int
    items: list[OrderItemOut]
    status: OrderStatus
    total_amount: Decimal
    shipping_address: ShippingAddress
    created_at: datetime
    paid_at: datetime | None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
