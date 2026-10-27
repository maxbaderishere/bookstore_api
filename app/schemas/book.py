from datetime import UTC, datetime

from pydantic import BaseModel, Decimal, Field

from app.schemas.author import AuthorOut
from app.schemas.genre import GenreOut
from app.schemas.ormmodel import ORMMODEL
from app.schemas.publisher import PublisherOut


#POST
class BookCreate(BaseModel):
    title : str = Field(min_length=1, max_length=100)
    description : str | None = None
    isbn : str = Field(min_length=1, max_length=13)
    publisher_id : int
    publication_year : int 
    language : str 
    pages: int = Field(gt=0)
    price : Decimal = Field(gt=0)
    stock: int = Field(ge=0)
    cover_url : str | None = None
    authors_ids : list[int]
    genres_ids : list[int] 
    created_at : datetime = Field(default_factory = datetime.now(UTC))

#GET
class BookOut(ORMMODEL):
    id: int
    title : str 
    description : str | None = None
    isbn : str
    publication_year : int 
    language : str 
    pages : int
    price : str
    stock : int 
    cover_url : str
    publisher : PublisherOut
    authors : list[AuthorOut]
    genres : list[GenreOut]
    created_at : datetime 


#PATCH
class BookUpdate:
    pass