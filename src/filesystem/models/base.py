from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, RootModel


class BaseModel(PydanticBaseModel):
    """Base model class for all our Pydantic models."""
    class Config:
        from_attributes = True
