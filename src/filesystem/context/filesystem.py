import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import aiofiles
    HAS_AIO = True
except ImportError:
    HAS_AIO = False
    print("Warning: aiofiles not installed. Some file operations might be blocking or fail.", file=sys.stderr)

from mcp.shared.exceptions import McpError
from mcp.types import types

logger = logging.getLogger(__name__)

class FilesystemContext:
    def __init__(self, allowed_dirs_str: List[str]):
        if not allowed_dirs_str:
            raise ValueError("At least one allowed directory must be specified.")

        self.allowed_directories: List[Path] = []
        for dir_str in allowed_dirs_str:
            expanded_dir = Path(dir_str).expanduser().resolve()
            if not expanded_dir.is_dir():
                raise ValueError(f"Allowed directory does not exist or is not a directory: {expanded_dir}")
            self.allowed_directories.append(expanded_dir)
        logger.info(f"FSContext initialized. Allowed directories: {[str(p) for p in self.allowed_directories]}")

    async def _is_path_actually_allowed(self, path_to_check: Path) -> bool:
        """Checks if a fully resolved path is within any allowed directory."""
        for allowed_dir in self.allowed_directories:
            if path_to_check == allowed_dir or path_to_check.is_relative_to(allowed_dir):
                return True
        return False

    async def validate_path(self, requested_path_str: str, check_existence: bool = True, is_for_write: bool = False) -> Path:
        p_user = Path(requested_path_str).expanduser()
        
        try:
            if is_for_write and not p_user.exists() and p_user.parent.exists():
                resolved_base = p_user.parent.resolve(strict=True)
                final_resolved_path = resolved_base / p_user.name
            else:
                final_resolved_path = p_user.resolve(strict=True if check_existence and not is_for_write else False)

        except FileNotFoundError:
            if is_for_write:
                parent_path = p_user.parent
                try:
                    resolved_parent = parent_path.resolve(strict=True)
                    if not await self._is_path_actually_allowed(resolved_parent):
                        raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied: Parent directory of '{requested_path_str}' is outside allowed areas."))
                    final_resolved_path = resolved_parent / p_user.name
                except FileNotFoundError:
                    raise McpError(types.ErrorData(code=types.RESOURCE_NOT_FOUND, message=f"Parent directory does not exist: {parent_path}"))
                except Exception as e_parent:
                    logger.warning(f"Error resolving parent of '{requested_path_str}': {e_parent}")
                    raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied or invalid path: '{requested_path_str}' due to parent directory issue."))
            else:
                raise McpError(types.ErrorData(code=types.RESOURCE_NOT_FOUND, message=f"Path does not exist: {requested_path_str}"))
        except Exception as e_resolve:
            logger.warning(f"Error resolving path '{requested_path_str}': {e_resolve}")
            raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied or invalid path: '{requested_path_str}'"))

        if not await self._is_path_actually_allowed(final_resolved_path):
            logger.warning(f"Access Denied: '{final_resolved_path}' (from '{requested_path_str}') is outside allowed directories: {[str(d) for d in self.allowed_directories]}")
            raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied: Path '{requested_path_str}' is outside allowed areas."))

        if check_existence and not is_for_write and not final_resolved_path.exists():
            raise McpError(types.ErrorData(code=types.RESOURCE_NOT_FOUND, message=f"Path does not exist after validation: {final_resolved_path}"))
            
        return final_resolved_path

    async def _read_file_async(self, path: Path) -> str:
        if not HAS_AIO: return path.read_text(encoding="utf-8")
        async with aiofiles.open(path, "r", encoding="utf-8") as f: return await f.read()

    async def _write_file_async(self, path: Path, content: str):
        if not HAS_AIO: return path.write_text(content, encoding="utf-8")
        async with aiofiles.open(path, "w", encoding="utf-8") as f: await f.write(content)

    async def _mkdir_async(self, path: Path, parents: bool = False, exist_ok: bool = False):
        await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)

    async def _rename_async(self, source: Path, destination: Path):
        await asyncio.to_thread(source.rename, destination)
