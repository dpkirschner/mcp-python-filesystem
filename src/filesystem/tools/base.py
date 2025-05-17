from abc import ABC, abstractmethod
from typing import Any, Optional, List, Dict
from mcp.server.fastmcp import FastMCP
from mcp.types import types
from mcp.shared.exceptions import McpError
from ..models import models
from ..context import context

class BaseTool(ABC):
    """Base class for all filesystem tools."""
    
    def __init__(self, mcp: FastMCP, fs_context: context.FilesystemContext):
        self.mcp = mcp
        self.fs_context = fs_context

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool's functionality."""
        pass
