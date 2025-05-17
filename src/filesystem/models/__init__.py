from .base import BaseModel
from .schemas import (
    ReadFileArgs, ReadMultipleFilesArgs, WriteFileArgs, EditOperation, EditFileArgs,
    CreateDirectoryArgs, ListDirectoryArgs, DirectoryTreeArgs, MoveFileArgs,
    SearchFilesArgs, GetFileInfoArgs, FileInfo, TreeEntry, DirectoryEntryItem, FileContentResult
)

# For backward compatibility
import sys
import importlib

# Import all symbols from schemas into the models namespace
from . import schemas
from .schemas import *

# Make the schemas module available as models.schemas
sys.modules[__name__ + '.schemas'] = schemas

# Also make it available as models.models for backward compatibility
sys.modules[__name__ + '.models'] = schemas

__all__ = [
    'BaseModel',
    'schemas',
    'models',  # For backward compatibility
    'ReadFileArgs', 'ReadMultipleFilesArgs', 'WriteFileArgs', 'EditOperation',
    'EditFileArgs', 'CreateDirectoryArgs', 'ListDirectoryArgs', 'DirectoryTreeArgs',
    'MoveFileArgs', 'SearchFilesArgs', 'GetFileInfoArgs', 'FileInfo', 'TreeEntry',
    'DirectoryEntryItem', 'FileContentResult'
]
