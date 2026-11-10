from fastapi import APIRouter

from app.dependencies import Cart
from app.models.cart import CartItem
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut

router = APIRouter(prefix="/cart", tags=["cart"])


def to_out(items: list[CartItem]) -> CartOut:
    return CartOut.model_validate({"items": items}, from_attributes=True)


@router.get("", response_model=CartOut)
async def get_cart(cart: Cart):
    return to_out(await cart.items())


@router.post("/items", response_model=CartOut)
async def add_to_cart(cart: Cart, data: CartItemAdd):
    """Добавить книгу; если она уже в корзине — количество суммируется."""
    return to_out(await cart.add(data.book_id, data.quantity))


@router.patch("/items/{book_id}", response_model=CartOut)
async def change_quantity(cart: Cart, book_id: int, data: CartItemUpdate):
    """Установить точное количество книги в корзине."""
    return to_out(await cart.set_quantity(book_id, data.quantity))


@router.delete("/items/{book_id}", status_code=204)
async def remove_from_cart(cart: Cart, book_id: int):
    await cart.remove(book_id)


@router.delete("", status_code=204)
async def clear_cart(cart: Cart):
    await cart.clear()
