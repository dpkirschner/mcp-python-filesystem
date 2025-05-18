from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from pytest_mock import MockerFixture

from filesystem.context.filesystem import FilesystemContext
from filesystem.models import schemas
from filesystem.tools import file_operations


class TestReadFileTool:
    async def test_read_file_success(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_file: Path,
    ) -> None:
        # Setup
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        args = schemas.ReadFileArgs(path=str(sample_file))

        # Execute
        result = await tool.read_file(args)


        # Verify
        assert isinstance(result, TextContent)
        assert "This is a test file" in result.text

    async def test_read_file_with_offset(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_file: Path,
    ) -> None:
        # Setup - write known content
        content = "0123456789"
        sample_file.write_text(content)
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        
        # Test reading from offset 5
        args = schemas.ReadFileArgs(path=str(sample_file), offset=5)
        result = await tool.read_file(args)
        assert result.text == "56789"

    async def test_read_file_with_length(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_file: Path,
    ) -> None:
        # Setup - write known content
        content = "0123456789"
        sample_file.write_text(content)
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        
        # Test reading first 3 bytes
        args = schemas.ReadFileArgs(path=str(sample_file), length=3)
        result = await tool.read_file(args)
        assert result.text == "012"

    async def test_read_file_with_offset_and_length(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_file: Path,
    ) -> None:
        # Setup - write known content
        content = "0123456789"
        sample_file.write_text(content)
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        
        # Test reading 3 bytes starting from offset 2
        args = schemas.ReadFileArgs(path=str(sample_file), offset=2, length=3)
        result = await tool.read_file(args)
        assert result.text == "234"

    async def test_read_file_with_encoding(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup - create a file with non-UTF-8 encoding
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        file_path = temp_dir / "latin1.txt"
        content = "café"  # 'é' is a non-ASCII character
        file_path.write_bytes(content.encode('latin-1'))
        
        # Test reading with correct encoding
        args = schemas.ReadFileArgs(path=str(file_path), encoding="latin-1")
        result = await tool.read_file(args)
        assert result.text == content
        
        # Test reading with wrong encoding (should still work but might show replacement chars)
        args.encoding = "utf-8"
        result = await tool.read_file(args)
        assert "caf" in result.text  # First part should be readable

    async def test_read_file_not_found(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        args = schemas.ReadFileArgs(path=str(temp_dir / "nonexistent.txt"))

        # Execute & Verify
        with pytest.raises(Exception) as exc_info:
            await tool.read_file(args)
        assert "does not exist" in str(exc_info.value)
        
    async def test_read_file_invalid_offset(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_file: Path,
    ) -> None:
        # Setup
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        
        # Test negative offset (should be validated by Pydantic)
        with pytest.raises(ValueError):
            schemas.ReadFileArgs(path=str(sample_file), offset=-1)
            
    async def test_read_file_invalid_length(
        self: "TestReadFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_file: Path,
    ) -> None:
        # Setup
        tool = file_operations.ReadFileTool(mcp_server, fs_context)
        
        # Test zero or negative length (should be validated by Pydantic)
        with pytest.raises(ValueError):
            schemas.ReadFileArgs(path=str(sample_file), length=0)
        with pytest.raises(ValueError):
            schemas.ReadFileArgs(path=str(sample_file), length=-1)


class TestReadMultipleFilesTool:
    async def test_read_multiple_files_success(
        self: "TestReadMultipleFilesTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup - create test files
        file1 = temp_dir / "file1.txt"
        file1.write_text("Content 1")

        file2 = temp_dir / "file2.txt"
        file2.write_text("Content 2")

        tool = file_operations.ReadMultipleFilesTool(mcp_server, fs_context)
        args = schemas.ReadMultipleFilesArgs(
            paths=[str(file1), str(file2), str(temp_dir / "nonexistent.txt")]
        )

        # Execute
        results = await tool.read_multiple_files(args)

        # Verify
        assert len(results) == 3

        # First file
        assert results[0].path == str(file1)
        assert results[0].content == "Content 1"
        assert results[0].error is None

        # Second file
        assert results[1].path == str(file2)
        assert results[1].content == "Content 2"
        assert results[1].error is None

        # Non-existent file
        assert "nonexistent.txt" in results[2].path
        assert results[2].content is None
        assert results[2].error is not None


class TestWriteFileTool:
    async def test_write_file_success(
        self: "TestWriteFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup
        tool = file_operations.WriteFileTool(mcp_server, fs_context)
        file_path = str(temp_dir / "new_file.txt")
        content = "New file content"

        # Mock the filesystem methods
        mock_validate = mocker.patch.object(
            fs_context, "validate_path", return_value=Path(file_path)
        )
        mock_mkdir = mocker.patch.object(fs_context, "_mkdir_async")
        mock_write = mocker.patch.object(fs_context, "_write_file_async")

        args = schemas.WriteFileArgs(path=file_path, content=content)

        # Execute
        result = await tool.write_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert f"Successfully wrote to {file_path}" == result.text

        # Verify mocks were called correctly
        mock_validate.assert_called_once_with(
            file_path, check_existence=False, is_for_write=True
        )
        mock_mkdir.assert_not_called()  # Parent dir exists, so mkdir shouldn't be called
        mock_write.assert_called_once_with(Path(file_path), content)

    async def test_write_file_creates_directories(
        self: "TestWriteFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup - write to a path with non-existent parent directories
        tool = file_operations.WriteFileTool(mcp_server, fs_context)
        file_path = str(temp_dir / "new_dir" / "subdir" / "new_file.txt")
        content = "New file in new directory"

        # Mock the filesystem methods
        mock_validate = mocker.patch.object(
            fs_context, "validate_path", return_value=Path(file_path)
        )
        mock_mkdir = mocker.patch.object(fs_context, "_mkdir_async")
        mock_write = mocker.patch.object(fs_context, "_write_file_async")

        # Make parent directory not exist
        mock_parent = mocker.MagicMock()
        mock_parent.exists.return_value = False
        mocker.patch(
            "pathlib.Path.parent",
            new_callable=mocker.PropertyMock(return_value=mock_parent),
        )

        args = schemas.WriteFileArgs(path=file_path, content=content)

        # Execute
        result = await tool.write_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert f"Successfully wrote to {file_path}" == result.text

        # Verify mocks were called correctly
        mock_validate.assert_called_once_with(
            file_path, check_existence=False, is_for_write=True
        )
        mock_mkdir.assert_called_once_with(mock_parent, parents=True, exist_ok=True)
        mock_write.assert_called_once_with(Path(file_path), content)


class TestEditFileTool:
    async def test_edit_file_success(
        self: "TestEditFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup
        tool = file_operations.EditFileTool(mcp_server, fs_context)
        file_path = str(temp_dir / "test_edit.txt")
        original_content = "Line 1\nLine 2\nLine 3"

        # Mock the filesystem methods
        mock_validate = mocker.patch.object(
            fs_context, "validate_path", return_value=Path(file_path)
        )
        mock_read = mocker.patch.object(
            fs_context, "_read_file_async", return_value=original_content
        )

        # Replace "Line 2" with "Modified Line 2"
        args = schemas.EditFileArgs(
            path=file_path,
            edits=[schemas.EditOperation(oldText="Line 2", newText="Modified Line 2")],
        )

        # Execute
        result = await tool.edit_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert result.text == f"Successfully edited {file_path}"

        # Verify mocks were called correctly
        mock_validate.assert_called_once_with(
            file_path, is_for_write=True, check_existence=True
        )
        mock_read.assert_called_once_with(Path(file_path))

    async def test_edit_file_with_dry_run(
        self: "TestEditFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup
        tool = file_operations.EditFileTool(mcp_server, fs_context)
        file_path = str(temp_dir / "test_edit.txt")
        original_content = "Line 1\nLine 2\nLine 3"

        # Mock the filesystem methods
        mock_validate = mocker.patch.object(
            fs_context, "validate_path", return_value=Path(file_path)
        )
        mock_read = mocker.patch.object(
            fs_context, "_read_file_async", return_value=original_content
        )

        # Set up the test edit
        args = schemas.EditFileArgs(
            path=file_path,
            edits=[schemas.EditOperation(oldText="Line 2", newText="Modified Line 2")],
            dryRun=True,
        )

        # Execute
        result = await tool.edit_file(args)

        # Verify
        assert isinstance(result, TextContent)
        assert "Would edit" in result.text

        # Verify mocks were called correctly
        mock_validate.assert_called_once_with(
            file_path, is_for_write=True, check_existence=True
        )
        mock_read.assert_called_once_with(Path(file_path))
