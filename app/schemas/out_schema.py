from pydantic import BaseModel


def out_schema(cls: type[BaseModel]) -> type[BaseModel]:
    cls.model_config = {**cls.model_config, "from_attributes": True}
    cls.model_rebuild(force=True)
    return cls
