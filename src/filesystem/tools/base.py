from abc import ABC, abstractmethod
from typing import Any

import mcp
from mcp.server.fastmcp import FastMCP

from ..context.filesystem import FilesystemContext


class BaseTool(ABC):
    """Base class for all filesystem tools."""

    # Expose the mcp module as a class attribute
    mcp = mcp

    def __init__(self, mcp_instance: FastMCP, fs_context: FilesystemContext):
        self.mcp_instance = mcp_instance
        self.fs_context = fs_context
        # Register tools when the instance is created
        self.register_tools()

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool's functionality."""
        pass

    def register_tools(self) -> None:
        """Register tools with the MCP server.

        Subclasses should override this method to register their tools using the
        @self.mcp_instance.tool() decorator.
        """
        pass
