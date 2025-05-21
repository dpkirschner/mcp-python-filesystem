import os
import stat
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from mcp import McpError
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
        file_path.write_bytes(content.encode("latin-1"))

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
        file_operations.ReadFileTool(mcp_server, fs_context)

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
        file_operations.ReadFileTool(mcp_server, fs_context)

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
        mock_read = mocker.patch.object(fs_context, "_read_file_async")

        # Create a mock for the Path object
        mock_path = mocker.MagicMock()
        mock_path.parent = mocker.MagicMock()
        mock_path.parent.exists.return_value = False

        # Mock the Path constructor to return our mock object
        original_path = Path

        def mock_path_constructor(*args: Any, **kwargs: Any) -> Any:
            if args or kwargs:
                return original_path(*args, **kwargs)
            return mock_path

        # Execute with the patched Path
        with unittest.mock.patch("pathlib.Path", side_effect=mock_path_constructor):
            args = schemas.WriteFileArgs(path=file_path, content=content)
            result = await tool.write_file(args)

            # Verify
            assert isinstance(result, TextContent)
            assert f"Successfully wrote to {file_path}" == result.text

            # Verify mocks were called correctly
            mock_validate.assert_called_once_with(
                file_path, check_existence=False, is_for_write=True
            )
            # Verify mkdir was called with the correct parent directory
            mock_mkdir.assert_called_once()
            mkdir_args, mkdir_kwargs = mock_mkdir.call_args
            assert str(mkdir_args[0]).endswith(
                "new_dir/subdir"
            )  # Check parent directory
            assert mkdir_kwargs == {"parents": True, "exist_ok": True}
            mock_read.assert_not_called()
            # Verify write was called with the correct path and content
            mock_write.assert_called_once()
            write_args = mock_write.call_args[0]
            assert str(write_args[0]) == file_path  # Check path matches
            assert write_args[1] == content  # Check content matches

    async def test_append_to_existing_file(
        self: "TestWriteFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup - append to an existing file
        tool = file_operations.WriteFileTool(mcp_server, fs_context)
        file_path = str(temp_dir / "existing_file.txt")
        existing_content = "Existing content\n"
        new_content = "New content to append"
        expected_content = existing_content + new_content

        # Create a real file for testing
        file_path_obj = Path(file_path)
        file_path_obj.parent.mkdir(parents=True, exist_ok=True)
        file_path_obj.write_text(existing_content)

        try:
            # Mock the filesystem methods
            mock_validate = mocker.patch.object(
                fs_context, "validate_path", return_value=file_path_obj
            )
            mock_mkdir = mocker.patch.object(fs_context, "_mkdir_async")
            mock_write = mocker.patch.object(fs_context, "_write_file_async")
            mock_read = mocker.patch.object(
                fs_context, "_read_file_async", return_value=existing_content
            )

            # Test append mode
            args = schemas.WriteFileArgs(
                path=file_path, content=new_content, mode="append"
            )

            # Execute
            result = await tool.write_file(args)

            # Verify
            assert isinstance(result, TextContent)
            # Check that the success message indicates the file was written to
            assert f"Successfully appended to {file_path}" == result.text

            # Verify mocks were called correctly
            mock_validate.assert_called_once_with(
                file_path, check_existence=True, is_for_write=True
            )
            mock_mkdir.assert_not_called()  # Parent dir exists
            mock_read.assert_called_once()  # Should read existing content
            mock_write.assert_called_once_with(file_path_obj, expected_content)
        finally:
            # Clean up
            if file_path_obj.exists():
                file_path_obj.unlink()

    async def test_append_to_nonexistent_file(
        self: "TestWriteFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup - append to a non-existent file (should create it)
        tool = file_operations.WriteFileTool(mcp_server, fs_context)
        file_path = str(temp_dir / "new_file.txt")
        content = "New content"

        # Mock the filesystem methods
        mock_validate = mocker.patch.object(
            fs_context, "validate_path", return_value=Path(file_path)
        )
        mock_mkdir = mocker.patch.object(fs_context, "_mkdir_async")
        mock_write = mocker.patch.object(fs_context, "_write_file_async")
        mock_read = mocker.patch.object(fs_context, "_read_file_async")

        # Create a mock for the Path object with parent that exists
        mock_path = mocker.MagicMock()
        mock_path.exists.return_value = False
        mock_path.parent = mocker.MagicMock()
        mock_path.parent.exists.return_value = True

        # Mock the Path constructor to return our mock object
        original_path = Path

        def mock_path_constructor(*args: Any, **kwargs: Any) -> Any:
            if args or kwargs:
                return original_path(*args, **kwargs)
            return mock_path

        # Test append mode with non-existent file
        with unittest.mock.patch("pathlib.Path", side_effect=mock_path_constructor):
            args = schemas.WriteFileArgs(path=file_path, content=content, mode="append")

            # Execute
            result = await tool.write_file(args)

            # Verify
            assert isinstance(result, TextContent)
            assert (
                f"Successfully wrote to {file_path}" == result.text
            )  # Should not say 'appended to'

            # Verify mocks were called correctly
            mock_validate.assert_called_once_with(
                file_path, check_existence=True, is_for_write=True
            )
            mock_mkdir.assert_not_called()  # Parent dir exists
            mock_read.assert_not_called()  # Should not try to read non-existent file
            # Check that _write_file_async was called with the correct path and content
            mock_write.assert_called_once()
            call_args = mock_write.call_args[0]
            assert str(call_args[0]) == file_path  # Check path matches
            assert call_args[1] == content  # Check content matches

    async def test_invalid_mode_raises_error(
        self: "TestWriteFileTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
    ) -> None:
        # Test that an invalid mode raises a ValueError
        with pytest.raises(
            ValueError, match="Mode must be either 'overwrite' or 'append'"
        ):
            schemas.WriteFileArgs(path="/test.txt", content="test", mode="invalid")


class TestGetFileInfoTool:
    async def test_get_file_info_success(
        self: "TestGetFileInfoTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_file: Path,
    ) -> None:
        # Setup
        tool = file_operations.GetFileInfoTool(mcp_server, fs_context)
        args = schemas.GetFileInfoArgs(path=str(sample_file))

        # Execute
        result = await tool.get_file_info(args)

        # Verify - use Path.resolve() to handle /private prefix on macOS
        assert Path(result.path).resolve() == Path(sample_file).resolve()
        assert result.size > 0
        assert isinstance(result.created, datetime)
        assert isinstance(result.modified, datetime)
        assert isinstance(result.accessed, datetime)
        assert result.isFile is True
        assert result.isDirectory is False
        assert isinstance(result.permissions, str)
        assert len(result.permissions) == 9  # rwxr-xr-x format
        assert result.mimeType != ""

    async def test_get_directory_info(
        self: "TestGetFileInfoTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup
        tool = file_operations.GetFileInfoTool(mcp_server, fs_context)
        args = schemas.GetFileInfoArgs(path=str(temp_dir))

        # Execute
        result = await tool.get_file_info(args)

        # Verify - use Path.resolve() to handle /private prefix on macOS
        assert Path(result.path).resolve() == Path(temp_dir).resolve()
        assert result.isFile is False
        assert result.isDirectory is True
        assert isinstance(result.permissions, str)
        assert len(result.permissions) == 9  # rwxr-xr-x format
        # Directories typically have 'd' as the first character in ls -l output,
        # but our permissions string only includes rwx characters
        assert result.mimeType in ["inode/directory", "application/octet-stream"]

    async def test_get_file_info_nonexistent_file(
        self: "TestGetFileInfoTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup
        tool = file_operations.GetFileInfoTool(mcp_server, fs_context)
        non_existent_file = temp_dir / "nonexistent.txt"
        args = schemas.GetFileInfoArgs(path=str(non_existent_file))

        # Execute & Verify - validate_path will raise McpError before _get_stat is called
        with pytest.raises(McpError) as exc_info:
            await tool.get_file_info(args)
        assert "Path does not exist" in str(exc_info.value)

    async def test_get_file_info_with_mock(
        self: "TestGetFileInfoTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        mocker: MockerFixture,
    ) -> None:
        # Setup mock with proper type hints and permission bits
        mock_stat = mocker.MagicMock(spec=os.stat_result)
        mock_stat.st_mode = stat.S_IFREG | 0o644
        mock_stat.st_size = 1024
        mock_stat.st_ctime = 1672531200  # 2023-01-01 00:00:00
        mock_stat.st_mtime = 1672617600  # 2023-01-02 00:00:00
        mock_stat.st_atime = 1672704000  # 2023-01-03 00:00:00
        mock_stat.st_ino = 12345  # Inode number
        mock_stat.st_dev = 1  # Device
        mock_stat.st_nlink = 1  # Number of hard links
        mock_stat.st_uid = 0  # User ID
        mock_stat.st_gid = 0  # Group ID

        # Mock the filesystem methods
        mocker.patch.object(
            fs_context, "validate_path", return_value=Path("/test/file.txt")
        )

        # Mock the _get_stat method to return our mock_stat
        async def mock_get_stat(path: Path) -> os.stat_result:
            # Create a proper os.stat_result with the required attributes
            # The order of timestamps in os.stat_result is: st_atime, st_mtime, st_ctime
            # We want created (st_ctime) <= modified (st_mtime) <= accessed (st_atime)
            stat_result = os.stat_result(
                (0o100644, 0, 0, 0, 0, 0, 1024, 1672704000, 1672617600, 1672531200)
            )
            return stat_result

        mocker.patch.object(fs_context, "_get_stat", side_effect=mock_get_stat)

        # Mock mimetypes.guess_type to return a text/plain MIME type
        mocker.patch("mimetypes.guess_type", return_value=("text/plain", None))

        tool = file_operations.GetFileInfoTool(mcp_server, fs_context)
        args = schemas.GetFileInfoArgs(path="/test/file.txt")

        # Execute
        result = await tool.get_file_info(args)

        # Verify
        assert result.path == "/test/file.txt"
        assert result.size == 1024

        # Verify the relative ordering of timestamps is correct
        assert result.created <= result.modified <= result.accessed, (
            f"Timestamps out of order: created={result.created}, modified={result.modified}, accessed={result.accessed}"
        )

        assert result.isFile is True
        assert result.isDirectory is False
        assert result.permissions == "rw-r--r--"  # 0o644 permissions
        assert result.mimeType == "text/plain"

    async def test_register_tools(
        self: "TestGetFileInfoTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        mocker: MockerFixture,
    ) -> None:
        # Setup
        tool = file_operations.GetFileInfoTool(mcp_server, fs_context)

        # Create a mock for the tool decorator
        mock_tool_decorator = mocker.MagicMock()

        # Set up the decorator chain: mock_tool_decorator() -> decorator() -> func
        mock_decorator = mocker.MagicMock()
        mock_tool_decorator.return_value = mock_decorator
        mock_decorator.side_effect = lambda func: func  # Return the function as-is

        # Patch the mcp_server.tool with our mock
        mocker.patch.object(mcp_server, "tool", mock_tool_decorator)

        # Mock the get_file_info method to return our expected result
        expected_result = mocker.MagicMock()
        mock_get_file_info = mocker.AsyncMock(return_value=expected_result)
        mocker.patch.object(tool, "get_file_info", mock_get_file_info)

        # Execute
        tool.register_tools()

        # Verify the tool decorator was called with no arguments
        mock_tool_decorator.assert_called_once_with()

        # The actual function that was decorated is the one inside register_tools
        # We'll call it directly with our test args
        mock_args = schemas.GetFileInfoArgs(path="/test/file.txt")

        # Call the registered function and await the result
        result = await tool.get_file_info(mock_args)

        # Verify the result is as expected
        assert result == expected_result
        mock_get_file_info.assert_called_once_with(mock_args)


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
