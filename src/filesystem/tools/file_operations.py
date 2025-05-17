from typing import Optional, List
import asyncio
import fnmatch
import mimetypes
import shutil
import json
import difflib
from datetime import datetime, timezone
from pathlib import Path

from ..models import models
from ..tools import base
from ..context import context

class ReadFileTool(base.BaseTool):
    """Tool for reading a single file."""
    
    @base.mcp.tool()
    async def read_file(self, args: models.ReadFileArgs) -> types.TextContent:
        valid_path = await self.fs_context.validate_path(args.path)
        content = await self.fs_context._read_file_async(valid_path)
        return types.TextContent(text=content)

class ReadMultipleFilesTool(base.BaseTool):
    """Tool for reading multiple files."""
    
    @base.mcp.tool()
    async def read_multiple_files(self, args: models.ReadMultipleFilesArgs) -> List[models.FileContentResult]:
        results = []
        for file_path_str in args.paths:
            try:
                valid_path = await self.fs_context.validate_path(file_path_str)
                content = await self.fs_context._read_file_async(valid_path)
                result = models.FileContentResult(
                    path=file_path_str,
                    content=content,
                    error=None
                )
            except Exception as e:
                result = models.FileContentResult(
                    path=file_path_str,
                    content=None,
                    error=str(e)
                )
            results.append(result)
        return results

class WriteFileTool(base.BaseTool):
    """Tool for writing to a file."""
    
    @base.mcp.tool()
    async def write_file(self, args: models.WriteFileArgs) -> types.TextContent:
        valid_path = await self.fs_context.validate_path(args.path, check_existence=False, is_for_write=True)
        if not valid_path.parent.exists():
            await self.fs_context._mkdir_async(valid_path.parent, parents=True, exist_ok=True)
        await self.fs_context._write_file_async(valid_path, args.content)
        return types.TextContent(text=f"Successfully wrote to {args.path}")

class EditFileTool(base.BaseTool):
    """Tool for editing a file with multiple operations."""
    
    @base.mcp.tool()
    async def edit_file(self, args: models.EditFileArgs) -> types.TextContent:
        valid_path = await self.fs_context.validate_path(args.path, is_for_write=True, check_existence=True)
        original_content = await self.fs_context._read_file_async(valid_path)
        original_content_norm = original_content.replace('\r\n', '\n')
        modified_content_norm = original_content_norm

        for edit in args.edits:
            old_text_norm = edit.oldText.replace('\r\n', '\n')
            new_text_norm = edit.newText.replace('\r\n', '\n')
            if old_text_norm in modified_content_norm:
                modified_content_norm = modified_content_norm.replace(old_text_norm, new_text_norm)
            else:
                logger.warning(f"Edit 'oldText' not found for exact replacement: '{edit.oldText[:50]}...'"))
