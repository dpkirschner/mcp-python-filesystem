from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
import pytest

from filesystem.context.filesystem import FilesystemContext
from filesystem.models import schemas
from filesystem.tools import file_operations


class TestReadFileToolIntegration:
    """Integration tests for ReadFileTool with actual filesystem operations."""

    @pytest.mark.asyncio
    async def test_read_file_integration(self, mcp_server: FastMCP, fs_context: FilesystemContext, temp_dir: Path) -> None:
        # Setup - create a test file
        test_file = temp_dir / "test_read.txt"
        test_content = "This is a test file for integration testing"
        test_file.write_text(test_content)

        # Initialize the tool
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        args = schemas.ReadFileArgs(path=str(test_file))

        # Execute
        result = await tool.read_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert test_content in result.text


class TestReadMultipleFilesToolIntegration:
    """Integration tests for ReadMultipleFilesTool with actual filesystem operations."""

    @pytest.mark.asyncio
    async def test_read_multiple_files_integration(
        self, mcp_server: FastMCP, fs_context: FilesystemContext, temp_dir: Path
    ) -> None:
        # Setup - create test files
        file1 = temp_dir / "file1.txt"
        file1_content = "First file content"
        file1.write_text(file1_content)

        file2 = temp_dir / "file2.txt"
        file2_content = "Second file content"
        file2.write_text(file2_content)

        non_existent_file = str(temp_dir / "nonexistent.txt")

        # Initialize the tool
        tool = file_operations.ReadMultipleFilesTool(mcp_server, fs_context)
        args = schemas.ReadMultipleFilesArgs(paths=[str(file1), str(file2), non_existent_file])

        # Execute
        results = await tool.read_multiple_files(args)

        # Verify
        assert len(results) == 3

        # First file
        assert results[0].path == str(file1)
        assert results[0].content == file1_content
        assert results[0].error is None

        # Second file
        assert results[1].path == str(file2)
        assert results[1].content == file2_content
        assert results[1].error is None

        # Non-existent file
        assert results[2].path == non_existent_file
        assert results[2].content is None
        assert results[2].error is not None


class TestWriteFileToolIntegration:
    """Integration tests for WriteFileTool with actual filesystem operations."""

    @pytest.mark.asyncio
    async def test_write_file_integration(self, mcp_server: FastMCP, fs_context: FilesystemContext, temp_dir: Path) -> None:
        # Setup
        tool = file_operations.WriteFileTool(mcp_server, fs_context)
        file_path = str(temp_dir / "new_file.txt")
        content = "This is a test content for write operation"

        args = schemas.WriteFileArgs(path=file_path, content=content)

        # Execute
        result = await tool.write_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert f"Successfully wrote to {file_path}" == result.text

        # Verify file was actually written
        assert Path(file_path).exists()
        assert Path(file_path).read_text() == content

    @pytest.mark.asyncio
    async def test_write_file_creates_directories_integration(
        self, mcp_server: FastMCP, fs_context: FilesystemContext, temp_dir: Path
    ) -> None:
        # Setup - write to a path with non-existent parent directories
        tool = file_operations.WriteFileTool(mcp_server, fs_context)
        new_dir = temp_dir / "new_dir" / "subdir"
        file_path = str(new_dir / "new_file.txt")
        content = "Test content in new directory structure"

        args = schemas.WriteFileArgs(path=file_path, content=content)

        # Verify parent directory doesn't exist yet
        assert not new_dir.exists()

        # Execute
        result = await tool.write_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert f"Successfully wrote to {file_path}" == result.text

        # Verify file and directories were created
        assert Path(file_path).exists()
        assert Path(file_path).read_text() == content


class TestEditFileToolIntegration:
    """Integration tests for EditFileTool with actual filesystem operations."""

    @pytest.mark.asyncio
    async def test_edit_file_integration(self, mcp_server: FastMCP, fs_context: FilesystemContext, temp_dir: Path) -> None:
        # Setup - create a test file
        test_file = temp_dir / "test_edit.txt"
        original_content = "Line 1\nLine 2\nLine 3"
        test_file.write_text(original_content)

        # Initialize the tool
        tool = file_operations.EditFileTool(mcp_server, fs_context)

        # Define edit operations
        args = schemas.EditFileArgs(
            path=str(test_file),
            edits=[
                schemas.EditOperation(oldText="Line 2", newText="Modified Line 2"),
                schemas.EditOperation(oldText="Line 3", newText="Line 3 modified"),
            ],
        )

        # Execute
        result = await tool.edit_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert result.text == f"Successfully edited {test_file}"

        # Verify file was actually modified
        modified_content = test_file.read_text()
        assert "Modified Line 2" in modified_content
        assert "Line 3 modified" in modified_content
        assert "Line 1" in modified_content  # This line should remain unchanged

    @pytest.mark.asyncio
    async def test_edit_file_dry_run(self, mcp_server: FastMCP, fs_context: FilesystemContext, temp_dir: Path) -> None:
        # Setup - create a test file
        test_file = temp_dir / "test_dry_run.txt"
        original_content = "Original content"
        test_file.write_text(original_content)

        # Initialize the tool
        tool = file_operations.EditFileTool(mcp_server, fs_context)

        # Define edit operations with dryRun=True
        args = schemas.EditFileArgs(
            path=str(test_file),
            edits=[schemas.EditOperation(oldText="Original", newText="Modified")],
            dryRun=True,
        )

        # Execute
        result = await tool.edit_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert "dry run" in result.text.lower()

        # Verify file was not actually modified
        assert test_file.read_text() == original_content
