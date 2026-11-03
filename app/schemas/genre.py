from pydantic import BaseModel

from app.schemas.common import GenreName, Slug
from app.schemas.out_schema import out_schema


class GenreCreate(BaseModel):
    name: GenreName
    slug: Slug


@out_schema
class GenreOut(BaseModel):
    id: int
    name: str
    slug: str


class GenreUpdate(BaseModel):
    name: GenreName | None = None
    slug: Slug | None = None
