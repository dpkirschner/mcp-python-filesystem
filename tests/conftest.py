import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Iterator, List

import pytest
from mcp.server.fastmcp import FastMCP

from filesystem.context.filesystem import FilesystemContext


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create a temporary directory that gets cleaned up after the test."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def allowed_dirs(temp_dir: Path) -> List[str]:
    """Create a list of allowed directories for testing."""
    allowed = [str(temp_dir)]
    # Create some test directories
    (temp_dir / "test_dir1").mkdir()
    (temp_dir / "test_dir2").mkdir()
    return allowed


@pytest.fixture
async def fs_context(allowed_dirs: List[str]) -> FilesystemContext:
    """Create a FilesystemContext with test directories."""
    return FilesystemContext(allowed_dirs)


@pytest.fixture
def mcp_server() -> FastMCP:
    """Create a FastMCP instance for testing."""
    return FastMCP(name="test-filesystem-server")


@pytest.fixture
def sample_file(temp_dir: Path) -> Path:
    """Create a sample file with some content."""
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("This is a test file.")
    return file_path


@pytest.fixture
def sample_dir_structure(temp_dir: Path) -> Path:
    """Create a sample directory structure for testing."""
    # Create files
    (temp_dir / "file1.txt").write_text("File 1 content")
    (temp_dir / "file2.txt").write_text("File 2 content")

    # Create subdirectories
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("File 3 content")

    return temp_dir


# Enable asyncio for all tests
@pytest.fixture(autouse=True)
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
