from pydantic import BaseModel, Field

from app.schemas.ormmodel import ORMModel


class PublisherCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PublisherOut(ORMModel):
    id: int
    name: str


class PublisherUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
