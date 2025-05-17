from pydantic import BaseModel as PydanticBaseModel, Field, RootModel
from typing import Optional, List, Dict, Any, Union

class BaseModel(PydanticBaseModel):
    """Base model class for all our Pydantic models."""
    class Config:
        from_attributes = True
