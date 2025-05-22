from datetime import datetime

from pydantic import Field

from .base import BaseModel


class ReadFileArgs(BaseModel):
    path: str
    offset: int | None = Field(
        default=0,
        ge=0,
        description="The position in the file to start reading from (in bytes).",
    )
    length: int | None = Field(
        default=None,
        gt=0,
        description="Maximum number of bytes to read. If None, reads to the end of the file.",
    )
    encoding: str = Field(
        default="utf-8",
        description="The encoding to use when reading the file (e.g., 'utf-8', 'latin-1').",
    )


class ReadMultipleFilesArgs(BaseModel):
    paths: list[str]


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
    edits: list[EditOperation]
    dryRun: bool = Field(
        default=False, description="Preview changes using git-style diff format"
    )


class CreateDirectoryArgs(BaseModel):
    path: str


class ListDirectoryArgs(BaseModel):
    path: str
    show_hidden: bool = Field(
        default=False,
        description="Whether to include hidden files/directories (those starting with '.')",
    )
    pattern: str | None = Field(
        default=None,
        description="Optional glob pattern to filter directory entries by name (e.g., '*.txt' for .txt files)",
    )


class DirectoryTreeArgs(BaseModel):
    path: str


class MoveFileArgs(BaseModel):
    source: str
    destination: str


class SearchFilesArgs(BaseModel):
    path: str
    pattern: str
    excludePatterns: list[str] | None = Field(default_factory=lambda: [])


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
    mimeType: str = Field(description="The MIME type of the file")
    path: str = Field(description="The full path to the file")


class TreeEntry(BaseModel):
    name: str
    type: str  # "file" or "directory"
    children: list["TreeEntry"] | None = None


TreeEntry.model_rebuild()


class DirectoryEntryItem(BaseModel):
    name: str
    type: str  # "file" or "directory"
    size: int | None = None
    modified_timestamp: datetime | None = None
    error: str | None = None


class FileContentResult(BaseModel):
    path: str
    content: str | None = None
    error: str | None = None


class ReadPdfFileArgs(BaseModel):
    path: str = Field(..., description="The path to the PDF file to read.")
    page_numbers: list[int] | None = Field(
        default=None,
        description="Specific page numbers to extract text from. If None, extracts from all pages.",
    )


class PdfPage(BaseModel):
    page_number: int = Field(..., description="1-based page number")
    text_content: str = Field(..., description="Extracted text content from the page")


class PdfContent(BaseModel):
    """Structured representation of PDF content with page-wise text extraction."""

    path: str = Field(..., description="Path to the PDF file")
    total_pages: int = Field(..., description="Total number of pages in the PDF")
    pages: list[PdfPage] = Field(..., description="List of pages with extracted text")
