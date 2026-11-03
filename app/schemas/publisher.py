from pydantic import BaseModel, Field

from app.schemas.out_schema import out_schema


class PublisherCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


@out_schema
class PublisherOut(BaseModel):
    id: int
    name: str


class PublisherUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
