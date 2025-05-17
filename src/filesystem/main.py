#!/usr/bin/env python3

import argparse
import asyncio
import difflib
import fnmatch
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import mcp.types as types
from mcp.server.fastmcp import FastMCP  # Primary class for the server
from mcp.shared.exceptions import McpError
from pydantic import BaseModel, Field, RootModel

try:
    import aiofiles
    HAS_AIO = True
except ImportError:
    HAS_AIO = False
    print("Warning: aiofiles not installed. Some file operations might be blocking or fail.", file=sys.stderr)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Pydantic Schemas for Tool Arguments ---

class ReadFileArgs(BaseModel):
    path: str

class ReadMultipleFilesArgs(BaseModel):
    paths: List[str]

class WriteFileArgs(BaseModel):
    path: str
    content: str

class EditOperation(BaseModel):
    oldText: str = Field(description="Text to search for - must match exactly")
    newText: str = Field(description="Text to replace with")

class EditFileArgs(BaseModel):
    path: str
    edits: List[EditOperation]
    dryRun: bool = Field(default=False, description="Preview changes using git-style diff format")

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
    excludePatterns: Optional[List[str]] = Field(default_factory=list)

class GetFileInfoArgs(BaseModel):
    path: str

# --- Output Schemas ---
class FileInfo(BaseModel):
    size: int
    created: datetime
    modified: datetime
    accessed: datetime
    isDirectory: bool
    isFile: bool
    permissions: str

# --- New Pydantic Models for Structured Output ---
class DirectoryEntryItem(BaseModel):
    name: str
    type: str  # "file" or "directory"
    size: Optional[int] = None
    modified_timestamp: Optional[datetime] = None

class FileContentResult(BaseModel):
    path: str
    content: Optional[str] = None
    error: Optional[str] = None

class TreeEntry(BaseModel):
    name: str
    type: str # "file" or "directory"
    children: Optional[List['TreeEntry']] = None

TreeEntry.model_rebuild()


# --- Filesystem Context and Path Validation ---
class FilesystemContext:
    def __init__(self, allowed_dirs_str: List[str]):
        if not allowed_dirs_str:
            # Fallback to CWD if no dirs are explicitly given, or raise error.
            # For this server, let's require at least one.
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
        # path_to_check is assumed to be already resolved (e.g., via .resolve() or os.path.realpath)
        for allowed_dir in self.allowed_directories:
            if path_to_check == allowed_dir or path_to_check.is_relative_to(allowed_dir):
                return True
        return False

    async def validate_path(self, requested_path_str: str, check_existence: bool = True, is_for_write: bool = False) -> Path:
        p_user = Path(requested_path_str).expanduser()
        
        # Attempt to resolve the path. This handles '..' and symlinks.
        try:
            # strict=True would fail if any part of the path doesn't exist.
            # For writing, the final component might not exist.
            if is_for_write and not p_user.exists() and p_user.parent.exists():
                 # If writing a new file, resolve the parent, then append the name
                 resolved_base = p_user.parent.resolve(strict=True)
                 final_resolved_path = resolved_base / p_user.name
            else:
                 final_resolved_path = p_user.resolve(strict=True if check_existence and not is_for_write else False)

        except FileNotFoundError:
            # This can happen if strict=True and path doesn't exist, or if a part of p_user doesn't exist.
            # If it's for writing, and the target doesn't exist, this is okay if the parent is valid.
            if is_for_write:
                # Try to resolve the parent path and ensure it's allowed
                parent_path = p_user.parent
                try:
                    resolved_parent = parent_path.resolve(strict=True)
                    if not await self._is_path_actually_allowed(resolved_parent):
                        raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied: Parent directory of '{requested_path_str}' is outside allowed areas."))
                    # The final path is the resolved parent + the non-existing file/dir name
                    final_resolved_path = resolved_parent / p_user.name
                    # We don't check existence of final_resolved_path here because it's for write
                except FileNotFoundError:
                    raise McpError(types.ErrorData(code=types.RESOURCE_NOT_FOUND, message=f"Parent directory does not exist: {parent_path}"))
                except Exception as e_parent: # Other resolution errors for parent
                    logger.warning(f"Error resolving parent of '{requested_path_str}': {e_parent}")
                    raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied or invalid path: '{requested_path_str}' due to parent directory issue."))
            else: # Not for write, and path doesn't exist
                raise McpError(types.ErrorData(code=types.RESOURCE_NOT_FOUND, message=f"Path does not exist: {requested_path_str}"))
        except Exception as e_resolve: # Other resolution errors (e.g., permission denied during resolve)
            logger.warning(f"Error resolving path '{requested_path_str}': {e_resolve}")
            raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied or invalid path: '{requested_path_str}'."))


        if not await self._is_path_actually_allowed(final_resolved_path):
            logger.warning(f"Access Denied: '{final_resolved_path}' (from '{requested_path_str}') is outside allowed directories: {[str(d) for d in self.allowed_directories]}")
            raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Access denied: Path '{requested_path_str}' is outside allowed areas."))

        # Additional check for check_existence if it wasn't covered by strict resolving
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


# --- Main Application Logic ---
async def run_server_logic(allowed_dirs_str: List[str], verbose: bool):
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")

    try:
        fs_context = FilesystemContext(allowed_dirs_str)
    except ValueError as e:
        logger.critical(f"Failed to initialize FilesystemContext: {e}")
        sys.exit(1)

    # Instantiate FastMCP directly
    mcp = FastMCP(
        name="secure-filesystem-server-py",
        # version="0.2.0", # FastMCP takes name, instructions, lifespan, tags, settings, dependencies
                         # The server_version for the protocol is part of InitializationOptions
        # dependencies=[], # Optional: if your server needs specific deps when deployed by mcp tools
    )
    logger.info(f"FastMCP server '{mcp.name}' created.")

    # --- Tool Implementations (defined inside to capture mcp and fs_context) ---
    @mcp.tool()
    async def read_file(args: ReadFileArgs) -> types.TextContent:
        valid_path = await fs_context.validate_path(args.path)
        content = await fs_context._read_file_async(valid_path)
        return types.TextContent(text=content)

    @mcp.tool()
    async def read_multiple_files(args: ReadMultipleFilesArgs) -> List[FileContentResult]:
        results = []
        for file_path_str in args.paths:
            try:
                valid_path = await fs_context.validate_path(file_path_str)
                content = await fs_context._read_file_async(valid_path)
                result = FileContentResult(
                    path=file_path_str,
                    content=content,
                    error=None
                )
            except Exception as e:
                result = FileContentResult(
                    path=file_path_str,
                    content=None,
                    error=str(e)
                )
            results.append(result)
        return results

    @mcp.tool()
    async def write_file(args: WriteFileArgs) -> types.TextContent:
        valid_path = await fs_context.validate_path(args.path, check_existence=False, is_for_write=True)
        if not valid_path.parent.exists():
             await fs_context._mkdir_async(valid_path.parent, parents=True, exist_ok=True)
        await fs_context._write_file_async(valid_path, args.content)
        return types.TextContent(text=f"Successfully wrote to {args.path}")

    @mcp.tool()
    async def edit_file(args: EditFileArgs) -> types.TextContent:
        valid_path = await fs_context.validate_path(args.path, is_for_write=True, check_existence=True)
        original_content = await fs_context._read_file_async(valid_path)
        original_content_norm = original_content.replace('\r\n', '\n')
        modified_content_norm = original_content_norm

        for edit in args.edits:
            old_text_norm = edit.oldText.replace('\r\n', '\n')
            new_text_norm = edit.newText.replace('\r\n', '\n')
            if old_text_norm in modified_content_norm:
                 modified_content_norm = modified_content_norm.replace(old_text_norm, new_text_norm)
            else:
                logger.warning(f"Edit 'oldText' not found for exact replacement: '{edit.oldText[:50]}...'")

        diff_lines = list(difflib.unified_diff(
            original_content_norm.splitlines(keepends=True),
            modified_content_norm.splitlines(keepends=True),
            fromfile=str(valid_path), # Use string path for diff header
            tofile=str(valid_path),   # Use string path for diff header
            lineterm='\n'
        ))
        diff_output = "".join(diff_lines)
        
        num_backticks = 3
        while '`' * num_backticks in diff_output: num_backticks += 1
        formatted_diff = f"{'`' * num_backticks}diff\n{diff_output}{'`' * num_backticks}\n\n"

        if not args.dryRun:
            await fs_context._write_file_async(valid_path, modified_content_norm)
            return types.TextContent(text=f"File edited. Changes:\n{formatted_diff}")
        else:
            return types.TextContent(text=f"Dry run. Proposed changes:\n{formatted_diff}")

    @mcp.tool()
    async def create_directory(args: CreateDirectoryArgs) -> types.TextContent:
        valid_path = await fs_context.validate_path(args.path, check_existence=False, is_for_write=True)
        await fs_context._mkdir_async(valid_path, parents=True, exist_ok=True)
        return types.TextContent(text=f"Successfully created directory {args.path} (or it already existed).")

    @mcp.tool()
    async def list_directory(args: ListDirectoryArgs) -> RootModel[List[DirectoryEntryItem]]:
        valid_path = await fs_context.validate_path(args.path)
        if not valid_path.is_dir():
            raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Path is not a directory: {args.path}"))
        
        entries = []
        for entry in await asyncio.to_thread(list, valid_path.iterdir()):
            entry_type = "directory" if entry.is_dir() else "file"
            entry_stat = await asyncio.to_thread(entry.stat)
            entry_item = DirectoryEntryItem(
                name=entry.name,
                type=entry_type,
                size=entry_stat.st_size if entry_type == "file" else None,
                modified_timestamp=datetime.fromtimestamp(entry_stat.st_mtime, tz=timezone.utc)
            )
            entries.append(entry_item)
        return RootModel[List[DirectoryEntryItem]](root=entries)

    @mcp.tool()
    async def directory_tree(args: DirectoryTreeArgs) -> RootModel[List[TreeEntry]]:
        async def build_tree_recursive(current_path_obj: Path) -> List[TreeEntry]:
            tree_entries: List[TreeEntry] = []
            for entry_path in await asyncio.to_thread(list, current_path_obj.iterdir()):
                # Validate each sub-entry before processing further
                try:
                    # This re-validation is important for symlinks within the tree
                    validated_entry_path = await fs_context.validate_path(str(entry_path), check_existence=False) # check_existence can be tricky for symlinks to dirs
                except McpError:
                    logger.warning(f"Skipping '{entry_path}' in directory tree: path not allowed or invalid.")
                    continue # Skip items that don't pass validation

                entry_type = "directory" if validated_entry_path.is_dir() else "file"
                entry_data = TreeEntry(name=validated_entry_path.name, type=entry_type)
                if entry_type == "directory":
                    entry_data.children = await build_tree_recursive(validated_entry_path)
                tree_entries.append(entry_data)
            return tree_entries

        top_valid_path = await fs_context.validate_path(args.path)
        if not top_valid_path.is_dir():
             raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Path is not a directory: {args.path}"))
        tree_data = await build_tree_recursive(top_valid_path)
        return RootModel[List[TreeEntry]](root=tree_data)

    @mcp.tool()
    async def move_file(args: MoveFileArgs) -> types.TextContent:
        valid_source = await fs_context.validate_path(args.source, check_existence=True) # Source must exist
        valid_destination = await fs_context.validate_path(args.destination, check_existence=False, is_for_write=True)

        if valid_destination.exists():
             raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Destination path already exists: {args.destination}"))
        if not valid_destination.parent.exists(): # Ensure destination parent exists
            await fs_context._mkdir_async(valid_destination.parent, parents=True, exist_ok=True)
        
        await fs_context._rename_async(valid_source, valid_destination)
        return types.TextContent(text=f"Successfully moved {args.source} to {args.destination}")

    @mcp.tool()
    async def search_files(args: SearchFilesArgs) -> types.TextContent:
        base_search_path = await fs_context.validate_path(args.path)
        if not base_search_path.is_dir():
            raise McpError(types.ErrorData(code=types.INVALID_PARAMS, message=f"Search path is not a directory: {args.path}"))

        results: List[str] = []
        search_pattern_lower = args.pattern.lower()

        for item_path_obj in base_search_path.rglob("*"):
            item_path_str = str(item_path_obj)
            try:
                relative_to_search_base = item_path_obj.relative_to(base_search_path)
                excluded = False
                if args.excludePatterns:
                    for ex_pattern in args.excludePatterns:
                        if fnmatch.fnmatchcase(item_path_obj.name, ex_pattern) or \
                           fnmatch.fnmatchcase(str(relative_to_search_base), ex_pattern):
                            excluded = True
                            break
                if excluded:
                    continue
                
                if search_pattern_lower in item_path_obj.name.lower(): # Case-insensitive name match
                    results.append(item_path_str)
            except Exception as e:
                logger.debug(f"Error processing {item_path_str} during search: {e}")

        if not results: return types.TextContent(text="No matches found")
        return types.TextContent(text="\n".join(results))

    @mcp.tool()
    async def get_file_info(args: GetFileInfoArgs) -> FileInfo:
        valid_path = await fs_context.validate_path(args.path)
        stat_result = await asyncio.to_thread(valid_path.stat)
        
        created_time_ts = stat_result.st_birthtime if hasattr(stat_result, 'st_birthtime') else stat_result.st_ctime

        return FileInfo(
            size=stat_result.st_size,
            created=datetime.fromtimestamp(created_time_ts, tz=timezone.utc),
            modified=datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc),
            accessed=datetime.fromtimestamp(stat_result.st_atime, tz=timezone.utc),
            isDirectory=valid_path.is_dir(),
            isFile=valid_path.is_file(),
            permissions=oct(stat_result.st_mode)[-3:]
        )

    @mcp.tool()
    async def list_allowed_directories(params: BaseModel = Field(default_factory=BaseModel)) -> types.TextContent:
        dirs_str = "\n".join(str(p) for p in fs_context.allowed_directories)
        return types.TextContent(text=f"Allowed directories:\n{dirs_str}")

    logger.info(f"Starting Python MCP Filesystem Server. Name: '{mcp.name}', Allowed Dirs: {allowed_dirs_str}")
    await mcp.run_stdio_async()
    logger.info("Python MCP Filesystem Server stopped.")


# --- CLI Entry Point ---
def main_cli():
    parser = argparse.ArgumentParser(description="Python MCP Filesystem Server (FastMCP)")
    parser.add_argument(
        "allowed_directory",
        nargs='+',
        help="Root directory (or directories) that the server is allowed to access."
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG level) logging."
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_server_logic(args.allowed_directory, args.verbose))
    except KeyboardInterrupt:
        logger.info("Server shut down by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Server failed to run: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main_cli()