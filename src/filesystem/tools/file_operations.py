import asyncio
import logging
import mimetypes
from datetime import datetime
from typing import List

from mcp.types import TextContent

from .. import models
from ..decorators import flat_args
from ..tools import base

logger = logging.getLogger(__name__)


class ReadFileTool(base.BaseTool):
    """Tool for reading a single file."""

    async def execute(self, args: models.ReadFileArgs) -> TextContent:
        """Execute the file read operation.

        Args:
            args: The arguments for reading a file, including the file path.

        Returns:
            TextContent: The content of the file.
        """
        return await self.read_file(args)

    @flat_args(models.ReadFileArgs)
    async def read_file(self, args: models.ReadFileArgs) -> TextContent:
        valid_path = await self.fs_context.validate_path(args.path)
        content = await self.fs_context._read_file_async(
            valid_path, offset=args.offset, length=args.length, encoding=args.encoding
        )
        return TextContent(type="text", text=content)

    # Register the tool with the MCP server
    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def read_file_tool(args: models.ReadFileArgs) -> TextContent:
            return await self.read_file(args)


class GetFileInfoTool(base.BaseTool):
    """Tool for getting information about a file, including MIME type and metadata."""

    async def execute(self, args: models.GetFileInfoArgs) -> models.FileInfo:
        """Execute the get file info operation.

        Args:
            args: The arguments for getting file info, including the file path.

        Returns:
            FileInfo: Information about the file including size, timestamps, and MIME type.
        """
        return await self.get_file_info(args)

    @flat_args(models.GetFileInfoArgs)
    async def get_file_info(self, args: models.GetFileInfoArgs) -> models.FileInfo:
        valid_path = await self.fs_context.validate_path(args.path)
        stat = await self.fs_context._get_stat(valid_path)

        # Get MIME type
        mime_type, _ = mimetypes.guess_type(valid_path)
        if mime_type is None:
            mime_type = "application/octet-stream"  # Default MIME type

        # Check if the path is a directory or file
        is_dir = stat.st_mode & 0o040000 != 0
        is_file = not is_dir

        # Format permissions (e.g., 'rwxr-xr-x')
        mode = stat.st_mode

        # Define permission bits for user, group, and others (read, write, execute)
        permission_bits = [
            (0o400, 0o200, 0o100),  # User (owner) permissions
            (0o040, 0o020, 0o010),  # Group permissions
            (0o004, 0o002, 0o001),  # Others permissions
        ]

        # Build the permission string
        perms = ""
        for read_bit, write_bit, exec_bit in permission_bits:
            perms += "r" if mode & read_bit else "-"
            perms += "w" if mode & write_bit else "-"
            perms += "x" if mode & exec_bit else "-"

        return models.FileInfo(
            size=stat.st_size,
            created=datetime.fromtimestamp(stat.st_ctime),
            modified=datetime.fromtimestamp(stat.st_mtime),
            accessed=datetime.fromtimestamp(stat.st_atime),
            isDirectory=is_dir,
            isFile=is_file,
            permissions=perms,
            mimeType=mime_type,
            path=str(valid_path),  # Convert Path to string
        )

    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def get_file_info_tool(args: models.GetFileInfoArgs) -> models.FileInfo:
            return await self.get_file_info(args)


class ReadMultipleFilesTool(base.BaseTool):
    """Tool for reading multiple files."""

    async def execute(
        self, args: models.ReadMultipleFilesArgs
    ) -> List[models.FileContentResult]:
        """Execute the multiple files read operation.

        Args:
            args: The arguments for reading multiple files, including the list of file paths.

        Returns:
            List[FileContentResult]: A list of results for each file read operation.
        """
        return await self.read_multiple_files(args)

    @flat_args(models.ReadMultipleFilesArgs)
    async def read_multiple_files(
        self, args: models.ReadMultipleFilesArgs
    ) -> List[models.FileContentResult]:
        """Read multiple files and return their contents.

        Args:
            args: The arguments containing the list of file paths to read.

        Returns:
            List[FileContentResult]: A list of file content results, one for each file.
        """
        results: List[models.FileContentResult] = []
        for file_path_str in args.paths:
            try:
                valid_path = await self.fs_context.validate_path(file_path_str)
                content = await self.fs_context._read_file_async(valid_path)
                result = models.FileContentResult(
                    path=file_path_str, content=content, error=None
                )
            except Exception as e:
                result = models.FileContentResult(
                    path=file_path_str, content=None, error=str(e)
                )
            results.append(result)
        return results

    # Register the tool with the MCP server
    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def read_multiple_files_tool(
            args: models.ReadMultipleFilesArgs,
        ) -> List[models.FileContentResult]:
            return await self.read_multiple_files(args)


class WriteFileTool(base.BaseTool):
    """Tool for writing to a file."""

    async def execute(self, args: models.WriteFileArgs) -> TextContent:
        """Execute the file write operation.

        Args:
            args: The arguments for writing to a file, including the file path and content.

        Returns:
            TextContent: A success message after writing to the file.
        """
        return await self.write_file(args)

    @flat_args(models.WriteFileArgs)
    async def write_file(self, args: models.WriteFileArgs) -> TextContent:
        valid_path = await self.fs_context.validate_path(
            args.path, check_existence=(args.mode == "append"), is_for_write=True
        )

        # Create parent directories if they don't exist
        if not valid_path.parent.exists():
            await self.fs_context._mkdir_async(
                valid_path.parent, parents=True, exist_ok=True
            )

        # Handle append mode
        if args.mode == "append" and valid_path.exists():
            # Read existing content and append new content
            existing_content = await self.fs_context._read_file_async(valid_path)
            new_content = existing_content + args.content
        else:
            # Overwrite mode or new file
            new_content = args.content

        # Write the content
        await self.fs_context._write_file_async(valid_path, new_content)

        # Determine the action for the success message
        file_exists = (
            await asyncio.to_thread(lambda: valid_path.exists())
            if hasattr(valid_path, "exists")
            else False
        )
        action = "appended to" if args.mode == "append" and file_exists else "wrote to"
        return TextContent(type="text", text=f"Successfully {action} {args.path}")

    # Register the tool with the MCP server
    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def write_file_tool(args: models.WriteFileArgs) -> TextContent:
            return await self.write_file(args)


class EditFileTool(base.BaseTool):
    """Tool for editing a file with multiple operations."""

    async def execute(self, args: models.EditFileArgs) -> TextContent:
        """Execute the file edit operation.

        Args:
            args: The arguments for editing a file, including the file path and edit operations.

        Returns:
            TextContent: A success message after applying the edits.
        """
        return await self.edit_file(args)

    @flat_args(models.EditFileArgs)
    async def edit_file(self, args: models.EditFileArgs) -> TextContent:
        valid_path = await self.fs_context.validate_path(
            args.path, is_for_write=True, check_existence=True
        )
        original_content = await self.fs_context._read_file_async(valid_path)
        original_content_norm = original_content.replace("\r\n", "\n")
        modified_content_norm = original_content_norm

        for edit in args.edits:
            old_text_norm = edit.oldText.replace("\r\n", "\n")
            new_text_norm = edit.newText.replace("\r\n", "\n")
            if old_text_norm in modified_content_norm:
                modified_content_norm = modified_content_norm.replace(
                    old_text_norm, new_text_norm
                )
            else:
                logger.warning(
                    f"Edit 'oldText' not found for exact replacement: '{edit.oldText[:50]}...'"
                )

        # Return appropriate message based on dryRun flag
        if getattr(args, "dryRun", False):
            return TextContent(type="text", text=f"Would edit {args.path} (dry run)")
        else:
            # Only write back if content was actually modified
            if modified_content_norm != original_content_norm:
                await self.fs_context._write_file_async(
                    valid_path, modified_content_norm
                )
            return TextContent(type="text", text=f"Successfully edited {args.path}")

    # Register the tool with the MCP server
    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def edit_file_tool(args: models.EditFileArgs) -> TextContent:
            return await self.edit_file(args)
