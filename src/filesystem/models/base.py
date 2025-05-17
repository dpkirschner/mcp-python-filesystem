
from pydantic import BaseModel as PydanticBaseModel


class BaseModel(PydanticBaseModel):
    """Base model class for all our Pydantic models."""
    class Config:
        from_attributes = True
