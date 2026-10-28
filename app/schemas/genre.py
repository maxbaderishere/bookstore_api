from pydantic import BaseModel

from app.schemas.common import GenreName, Slug
from app.schemas.ormmodel import ORMModel


class GenreCreate(BaseModel):
    name: GenreName
    slug: Slug


class GenreOut(ORMModel):
    id: int
    name: str
    slug: str


class GenreUpdate(BaseModel):
    name: GenreName | None = None
    slug: Slug | None = None
