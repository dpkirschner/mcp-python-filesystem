# For backward compatibility
import sys

# Import all symbols from schemas into the models namespace
from . import schemas
from .base import BaseModel
from .schemas import (
    CreateDirectoryArgs,
    DirectoryEntryItem,
    DirectoryTreeArgs,
    EditFileArgs,
    EditOperation,
    FileContentResult,
    FileInfo,
    GetFileInfoArgs,
    ListDirectoryArgs,
    MoveFileArgs,
    ReadFileArgs,
    ReadMultipleFilesArgs,
    SearchFilesArgs,
    TreeEntry,
    WriteFileArgs,
)

# Make the schemas module available as models.schemas
sys.modules[__name__ + ".schemas"] = schemas

# Also make it available as models.models for backward compatibility
sys.modules[__name__ + ".models"] = schemas

# Make schemas available as models for backward compatibility
models = schemas

__all__ = [
    "BaseModel",
    "schemas",
    "models",  # For backward compatibility
    "ReadFileArgs",
    "ReadMultipleFilesArgs",
    "WriteFileArgs",
    "EditOperation",
    "EditFileArgs",
    "CreateDirectoryArgs",
    "ListDirectoryArgs",
    "DirectoryTreeArgs",
    "MoveFileArgs",
    "SearchFilesArgs",
    "GetFileInfoArgs",
    "FileInfo",
    "TreeEntry",
    "DirectoryEntryItem",
    "FileContentResult",
]
