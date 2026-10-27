from pydantic import BaseModel, Field

from app.schemas.ormmodel import ORMMODEL


class GenreCreate(BaseModel):
    name : str = Field(min_length=1)
    slug : str = Field(min_length=1)

class GenreOut(ORMMODEL):
    id : int
    name : str
    slug : str
    
    
class GenreUpdate(BaseModel):
    name : str | None = None
    slug : str | None = None
    