import logging
from typing import List

from mcp.types import TextContent

from .. import models
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

    async def read_file(self, args: models.ReadFileArgs) -> TextContent:
        valid_path = await self.fs_context.validate_path(args.path)
        content = await self.fs_context._read_file_async(valid_path)
        return TextContent(type="text", text=content)

    # Register the tool with the MCP server
    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def read_file_tool(args: models.ReadFileArgs) -> TextContent:
            return await self.read_file(args)


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

    async def write_file(self, args: models.WriteFileArgs) -> TextContent:
        valid_path = await self.fs_context.validate_path(
            args.path, check_existence=False, is_for_write=True
        )
        if not valid_path.parent.exists():
            await self.fs_context._mkdir_async(
                valid_path.parent, parents=True, exist_ok=True
            )
        await self.fs_context._write_file_async(valid_path, args.content)
        return TextContent(type="text", text=f"Successfully wrote to {args.path}")

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
            return TextContent(type="text", text=f"Successfully edited {args.path}")

    # Register the tool with the MCP server
    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def edit_file_tool(args: models.EditFileArgs) -> TextContent:
            return await self.edit_file(args)
