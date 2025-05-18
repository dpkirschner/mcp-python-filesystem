from datetime import datetime
from typing import List, Optional

from pydantic import Field

from .base import BaseModel


class ReadFileArgs(BaseModel):
    path: str
    offset: Optional[int] = Field(
        default=0,
        ge=0,
        description="The position in the file to start reading from (in bytes).",
    )
    length: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum number of bytes to read. If None, reads to the end of the file.",
    )
    encoding: str = Field(
        default="utf-8",
        description="The encoding to use when reading the file (e.g., 'utf-8', 'latin-1').",
    )


class ReadMultipleFilesArgs(BaseModel):
    paths: List[str]


class WriteFileArgs(BaseModel):
    path: str
    content: str
    mode: str = Field(
        default="overwrite",
        description="File write mode: 'overwrite' (default) to replace file contents, 'append' to add to the end of the file",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "path": "/path/to/file.txt",
                "content": "File content",
                "mode": "overwrite",
            }
        }

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        if self.mode not in ["overwrite", "append"]:
            raise ValueError("Mode must be either 'overwrite' or 'append'")


class EditOperation(BaseModel):
    oldText: str = Field(description="Text to search for - must match exactly")
    newText: str = Field(description="Text to replace with")


class EditFileArgs(BaseModel):
    path: str
    edits: List[EditOperation]
    dryRun: bool = Field(
        default=False, description="Preview changes using git-style diff format"
    )


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
    excludePatterns: Optional[List[str]] = Field(default_factory=lambda: [])


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
    children: Optional[List["TreeEntry"]] = None


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
