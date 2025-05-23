import argparse
import asyncio
import logging
import sys

from mcp.server.fastmcp import FastMCP

from ..context import context
from ..tools import directory_operations, file_operations, pdf_operations

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def run_server_logic(allowed_dirs_str: list[str], verbose: bool) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")

    try:
        fs_context = context.FilesystemContext(allowed_dirs_str)
    except ValueError as e:
        logger.critical(f"Failed to initialize FilesystemContext: {e}")
        sys.exit(1)

    # Instantiate FastMCP directly
    mcp = FastMCP(
        name="secure-filesystem-server-py",
    )
    logger.info(f"FastMCP server '{mcp.name}' created.")

    # Register file system tools
    file_operations.ReadFileTool(mcp, fs_context)
    file_operations.ReadMultipleFilesTool(mcp, fs_context)
    file_operations.WriteFileTool(mcp, fs_context)
    file_operations.EditFileTool(mcp, fs_context)
    file_operations.GetFileInfoTool(mcp, fs_context)
    directory_operations.ListDirectoryTool(mcp, fs_context)
    logger.info("file system support enabled")

    # Register PDF operations
    pdf_operations.ReadPDFFileTool(mcp, fs_context)
    logger.info("PDF support enabled")

    logger.info(f"Starting MCP Filesystem Server. Name: '{mcp.name}', Allowed Dirs: {allowed_dirs_str}")
    await mcp.run_stdio_async()
    logger.info("Python MCP Filesystem Server stopped.")


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="Python MCP Filesystem Server (FastMCP)")
    parser.add_argument(
        "allowed_directory",
        nargs="+",
        help="Root directory (or directories) that the server is allowed to access",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()
    asyncio.run(run_server_logic(args.allowed_directory, args.verbose))


if __name__ == "__main__":
    main_cli()
