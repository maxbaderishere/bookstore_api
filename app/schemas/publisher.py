from pydantic import BaseModel


class PublisherCreate(BaseModel):
    pass

class PublisherOut(BaseModel):
    id : int
    name : str

class PublisherUpdate(BaseModel):
    pass