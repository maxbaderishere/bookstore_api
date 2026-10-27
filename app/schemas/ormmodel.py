from pydantic import BaseModel, ConfigDict


class ORMMODEL(BaseModel):
    model_config = ConfigDict(from_attributes=True)