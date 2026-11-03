from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field

ShippingAddress = Annotated[str, Field(min_length=1, max_length=500)]
Title = Annotated[str, Field(min_length=1, max_length=300)]
ISBN = Annotated[str, Field(pattern=r"^\d{13}$")]
Language = Annotated[str, Field(pattern=r"^[a-z]{2}$")]
Price = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Year = Annotated[int, Field(ge=1450, le=2100)]
GenreName = Annotated[str, Field(min_length=1, max_length=100)]
Slug = Annotated[
    str, Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
