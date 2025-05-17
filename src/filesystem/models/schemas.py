from datetime import datetime
from typing import List, Optional

from pydantic import Field

from .base import BaseModel


class ReadFileArgs(BaseModel):
    path: str

class ReadMultipleFilesArgs(BaseModel):
    paths: List[str]

class WriteFileArgs(BaseModel):
    path: str
    content: str

class EditOperation(BaseModel):
    oldText: str = Field(description="Text to search for - must match exactly")
    newText: str = Field(description="Text to replace with")

class EditFileArgs(BaseModel):
    path: str
    edits: List[EditOperation]
    dryRun: bool = Field(default=False, description="Preview changes using git-style diff format")

class CreateDirectoryArgs(BaseModel):
    path: str

class ListDirectoryArgs(BaseModel):
    path: str

class DirectoryTreeArgs(BaseModel):
    path: str

class MoveFileArgs(BaseModel):
    source: str
    destination: str

class SearchFilesArgs(BaseModel):
    path: str
    pattern: str
    excludePatterns: Optional[List[str]] = Field(default_factory=list)

class GetFileInfoArgs(BaseModel):
    path: str

class FileInfo(BaseModel):
    size: int
    created: datetime
    modified: datetime
    accessed: datetime
    isDirectory: bool
    isFile: bool
    permissions: str

class TreeEntry(BaseModel):
    name: str
    type: str  # "file" or "directory"
    children: Optional[List['TreeEntry']] = None

TreeEntry.model_rebuild()

class DirectoryEntryItem(BaseModel):
    name: str
    type: str  # "file" or "directory"
    size: Optional[int] = None
    modified_timestamp: Optional[datetime] = None

class FileContentResult(BaseModel):
    path: str
    content: Optional[str] = None
    error: Optional[str] = None
