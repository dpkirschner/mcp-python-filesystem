import asyncio
import logging
from datetime import datetime
from typing import List

from .. import models
from ..tools import base

logger = logging.getLogger(__name__)


class ListDirectoryTool(base.BaseTool):
    """Tool for listing directory contents."""

    async def execute(
        self, args: models.ListDirectoryArgs
    ) -> List[models.DirectoryEntryItem]:
        """Execute the directory listing operation.

        Args:
            args: The arguments for listing a directory, including the directory path.

        Returns:
            List[DirectoryEntryItem]: A list of directory entries with their details.
        """
        return await self.list_directory(args)

    async def list_directory(
        self, args: models.ListDirectoryArgs
    ) -> List[models.DirectoryEntryItem]:
        """List the contents of a directory.

        Args:
            args: The arguments containing the directory path to list.

        Returns:
            List[DirectoryEntryItem]: A list of directory entries with their details.

        Raises:
            NotADirectoryError: If the path exists but is not a directory.
            McpError: If the directory does not exist or is not accessible.
        """
        # First validate the path is allowed
        valid_path = await self.fs_context.validate_path(
            args.path, check_existence=True
        )

        # Then check if it's actually a directory
        stat = await asyncio.to_thread(valid_path.stat)
        if not stat.st_mode & 0o040000:  # Check if it's a directory using st_mode
            raise NotADirectoryError(f"Path is not a directory: {args.path}")

        entries = []
        try:
            # List all items in the directory
            for item in await asyncio.to_thread(valid_path.iterdir):
                # Skip hidden files if show_hidden is False
                if not args.show_hidden and item.name.startswith("."):
                    continue

                # Skip if pattern is provided and doesn't match
                if args.pattern is not None and not item.name.lower().endswith(
                    args.pattern.lower().lstrip("*")
                ):
                    continue

                try:
                    item_path = valid_path / item.name
                    stat = await asyncio.to_thread(item_path.stat)

                    is_directory = bool(
                        stat.st_mode & 0o040000
                    )  # Check if it's a directory using st_mode
                    modified_timestamp = (
                        datetime.fromtimestamp(stat.st_mtime) if stat.st_mtime else None
                    )
                    entry = models.DirectoryEntryItem(
                        name=item.name,
                        type="directory" if is_directory else "file",
                        size=stat.st_size if not is_directory else None,
                        modified_timestamp=modified_timestamp,
                    )
                    entries.append(entry)
                except Exception as e:
                    logger.warning(f"Error getting info for {item.name}: {str(e)}")
                    # Still add the entry with minimal info
                    entries.append(
                        models.DirectoryEntryItem(
                            name=item.name, type="unknown", error=str(e)
                        )
                    )
        except Exception as e:
            logger.error(f"Error listing directory {args.path}: {str(e)}")
            raise

        return entries

    # Register the tool with the MCP server
    def register_tools(self) -> None:
        @self.mcp_instance.tool()
        async def list_directory_tool(
            args: models.ListDirectoryArgs,
        ) -> List[models.DirectoryEntryItem]:
            return await self.list_directory(args)
