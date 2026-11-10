from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.author import AuthorShort
from app.schemas.common import ISBN, Language, Price, Title, Year
from app.schemas.genre import GenreOut
from app.schemas.out_schema import out_schema
from app.schemas.publisher import PublisherOut


# POST
class BookCreate(BaseModel):
    title: Title
    description: str | None = None
    isbn: ISBN
    publisher_id: int | None = None
    publication_year: Year | None = None
    language: Language
    pages: int | None = Field(default=None, gt=0)
    price: Price
    stock: int = Field(default=0, ge=0)
    cover_url: str = Field(max_length=500)
    author_ids: list[int]
    genre_ids: list[int]


# GET
@out_schema
class BookOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    isbn: str
    publication_year: Year | None
    language: str
    pages: int | None
    price: Decimal
    stock: int
    cover_url: str | None
    publisher: PublisherOut | None
    authors: list[AuthorShort]
    genres: list[GenreOut]
    created_at: datetime


# PATCH
class BookUpdate(BaseModel):
    title: Title | None = None
    description: str | None = None
    isbn: ISBN | None = None
    publisher_id: int | None = None
    publication_year: Year | None = None
    language: Language | None = None
    pages: int | None = Field(default=None, gt=0)
    price: Price | None = None
    stock: int | None = Field(default=None, ge=0)
    cover_url: str | None = Field(default=None, max_length=500)
    author_ids: list[int] | None = None
    genre_ids: list[int] | None = None
