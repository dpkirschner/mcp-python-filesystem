from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import sys

try:
    import aiofiles

    HAS_AIO = True
except ImportError:
    HAS_AIO = False
    print(
        "Warning: aiofiles not installed. Some file operations might be blocking or fail.",
        file=sys.stderr,
    )

from mcp import McpError
from mcp.types import INVALID_PARAMS, ErrorData

logger = logging.getLogger(__name__)


class FilesystemContext:
    def __init__(self, allowed_dirs_str: list[str]):
        if not allowed_dirs_str:
            raise ValueError("At least one allowed directory must be specified.")

        self.allowed_directories: list[Path] = []
        for dir_str in allowed_dirs_str:
            expanded_dir = Path(dir_str).expanduser().resolve()
            if not expanded_dir.is_dir():
                raise ValueError(f"Allowed directory does not exist or is not a directory: {expanded_dir}")
            self.allowed_directories.append(expanded_dir)
        dirs_formatted = [f"{str(p)[:80]}..." if len(str(p)) > 80 else str(p) for p in self.allowed_directories]
        logger.info(f"FSContext initialized. Allowed dirs: {', '.join(dirs_formatted)}")

    async def _is_path_actually_allowed(self, path_to_check: Path) -> bool:
        """Checks if a fully resolved path is within any allowed directory."""
        for allowed_dir in self.allowed_directories:
            if path_to_check == allowed_dir or path_to_check.is_relative_to(allowed_dir):
                return True
        return False

    async def validate_path(
        self,
        requested_path_str: str,
        check_existence: bool = True,
        is_for_write: bool = False,
    ) -> Path:
        p_user = Path(requested_path_str).expanduser()

        try:
            if is_for_write and not check_existence:
                # For write operations where we don't care if the file exists,
                # find the first existing parent directory and check if it's allowed
                current = p_user.parent
                while True:
                    try:
                        resolved = current.resolve(strict=True)
                        if await self._is_path_actually_allowed(resolved):
                            # Found an existing parent that's allowed, construct the full path
                            final_resolved_path = (resolved / p_user.relative_to(current)).resolve()
                            return final_resolved_path
                        else:
                            raise McpError(
                                ErrorData(
                                    code=INVALID_PARAMS,
                                    message=f"Access denied: '{requested_path_str}' outside allowed dirs.",
                                )
                            )
                    except FileNotFoundError as e:
                        if current.parent == current:
                            # Reached root and still didn't find an existing allowed directory
                            raise McpError(
                                ErrorData(
                                    code=INVALID_PARAMS,
                                    message=f"No allowed parent for '{requested_path_str}'",
                                )
                            ) from e
                        current = current.parent
            else:
                # For read operations or when we need to check existence
                final_resolved_path = p_user.resolve(strict=check_existence)

                # Check if it's in an allowed directory
                if not await self._is_path_actually_allowed(final_resolved_path):
                    raise McpError(
                        ErrorData(
                            code=INVALID_PARAMS,
                            message=f"Access denied: Path '{requested_path_str}' is outside allowed areas.",
                        )
                    )

                return final_resolved_path

        except FileNotFoundError as e:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=f"Path does not exist: {requested_path_str}",
                )
            ) from e

        except Exception as e:
            logger.warning(f"Error resolving path '{requested_path_str}': {e}")
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=f"Access denied or invalid path: '{requested_path_str}': {str(e)}",
                )
            ) from e

    async def _read_file_async(
        self,
        path: Path,
        offset: int | None = None,
        length: int | None = None,
        encoding: str = "utf-8",
    ) -> str:
        offset = offset or 0
        if not HAS_AIO:
            with path.open("rb") as f:
                if offset > 0:
                    f.seek(offset)
                if length is not None:
                    content = f.read(length)
                else:
                    content = f.read()
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError as e:
                    logger.warning("Decoding failed: %s", e)
                    return str(content)
        else:
            async with aiofiles.open(path, "rb") as f:
                if offset > 0:
                    await f.seek(offset)
                if length is not None:
                    content = await f.read(length)
                else:
                    content = await f.read()
                try:
                    return content.decode(encoding)
                except UnicodeDecodeError as e:
                    logger.warning("Decoding failed: %s", e)
                    return str(content)

    async def _write_file_async(self, path: Path, content: str) -> int | None:
        if not HAS_AIO:
            return path.write_text(content, encoding="utf-8")
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)
            return None

    async def _mkdir_async(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)

    async def _rename_async(self, source: Path, destination: Path) -> None:
        await asyncio.to_thread(source.rename, destination)

    async def _get_stat(self, path: Path) -> os.stat_result:
        """Get file status asynchronously.

        Args:
            path: The path to get status for.

        Returns:
            os.stat_result: The file status.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        try:
            return await asyncio.to_thread(path.stat)
        except FileNotFoundError as e:
            logger.warning(f"File not found: {path}")
            raise FileNotFoundError(f"File not found: {path}") from e
