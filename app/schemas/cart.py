from decimal import Decimal

from pydantic import BaseModel, Field, computed_field

from app.schemas.out_schema import out_schema


class CartItemAdd(BaseModel):
    book_id: int
    quantity: int = Field(default=1, gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


@out_schema
class BookInCart(BaseModel):
    id: int
    title: str
    price: Decimal
    stock: int
    cover_url: str | None


@out_schema
class CartItemOut(BaseModel):
    book: BookInCart
    quantity: int

    @computed_field
    def subtotal(self) -> Decimal:
        return self.book.price * self.quantity


class CartOut(BaseModel):
    items: list[CartItemOut]

    @computed_field
    def total_quantity(self) -> int:
        return sum(i.quantity for i in self.items)

    @computed_field
    def total_amount(self) -> Decimal:
        return sum((i.subtotal for i in self.items), Decimal(0))
