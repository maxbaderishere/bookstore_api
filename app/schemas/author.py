from pydantic import BaseModel, Field

from app.schemas.ormmodel import ORMMODEL


class AuthorBase(BaseModel):
    name : str = Field(min_length=1,max_length=100)
    bio : str | None = None

class AuthorCreate(AuthorBase):
    pass

class AuthorUpdate(AuthorBase):
    name : str | None = Field(min_length=1,max_length=100)
    bio : str | None = None

class AuthorOut(ORMMODEL):
    id: int
    full_name : str