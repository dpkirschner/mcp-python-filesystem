import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from mcp import McpError
from mcp.server.fastmcp import FastMCP
import pytest
from pytest_mock import MockerFixture

from filesystem.context.filesystem import FilesystemContext
from filesystem.models import schemas
from filesystem.tools.directory_operations import ListDirectoryTool


class TestListDirectoryTool:
    async def test_list_directory_success(
        self: "TestListDirectoryTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup
        tool = ListDirectoryTool(mcp_server, fs_context)

        # Create test directory structure
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        # Create test files and subdirectories
        (test_dir / "file1.txt").write_text("Test file 1")
        (test_dir / "file2.txt").write_text("Test file 2")
        (test_dir / "subdir").mkdir()

        # Execute
        args = schemas.ListDirectoryArgs(path=str(test_dir))
        result = await tool.list_directory(args)

        # Verify
        assert len(result) == 3  # 2 files + 1 directory

        # Check that all expected items are present
        names = {item.name for item in result}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

        # Check types and properties
        for item in result:
            if item.name == "subdir":
                assert item.type == "directory"
                assert item.size is None
            else:
                assert item.type == "file"
                assert isinstance(item.size, int)
                assert item.size > 0
            assert isinstance(item.name, str)
            assert item.modified_timestamp is not None

    async def test_list_directory_empty(
        self: "TestListDirectoryTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup - create empty directory
        empty_dir = temp_dir / "empty_dir"
        empty_dir.mkdir()

        tool = ListDirectoryTool(mcp_server, fs_context)
        args = schemas.ListDirectoryArgs(path=str(empty_dir))

        # Execute
        result = await tool.list_directory(args)

        # Verify
        assert result == []

    async def test_list_directory_with_error(
        self: "TestListDirectoryTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
        mocker: MockerFixture,
    ) -> None:
        # Setup - create a directory with a file we can't access
        test_dir = temp_dir / "test_error"
        test_dir.mkdir()
        (test_dir / "good_file.txt").write_text("Good file")

        # Create a file that will cause an error when accessed
        bad_file_path_obj = test_dir / "bad_file"
        bad_file_path_obj.touch()

        # Store the original asyncio.to_thread before patching
        original_asyncio_to_thread = asyncio.to_thread

        # Create a side_effect function that handles specific iterdir and stat calls
        async def to_thread_side_effect(
            func_to_run_in_thread: Callable[..., Any],
            *args_for_func: Any,
            **kwargs_for_func: Any,
        ) -> Any:
            # Handle Path.iterdir() calls
            if (
                hasattr(func_to_run_in_thread, "__name__")
                and func_to_run_in_thread.__name__ == "iterdir"
                and hasattr(func_to_run_in_thread, "__self__")
            ):
                path_instance = func_to_run_in_thread.__self__
                if path_instance == test_dir:
                    return [test_dir / "good_file.txt", bad_file_path_obj]

            # Handle Path.stat() calls
            elif (
                hasattr(func_to_run_in_thread, "__name__")
                and func_to_run_in_thread.__name__ == "stat"
                and hasattr(func_to_run_in_thread, "__self__")
            ):
                path_instance = func_to_run_in_thread.__self__
                if path_instance.resolve() == bad_file_path_obj.resolve():
                    raise PermissionError("Permission denied for bad_file")

            # Default case: call the original function
            return await original_asyncio_to_thread(func_to_run_in_thread, *args_for_func, **kwargs_for_func)

        # Patch asyncio.to_thread with our revised side_effect
        mocker.patch("asyncio.to_thread", side_effect=to_thread_side_effect)

        tool = ListDirectoryTool(mcp_server, fs_context)
        args = schemas.ListDirectoryArgs(path=str(test_dir))

        # Execute
        result = await tool.list_directory(args)

        # Verify
        assert len(result) == 2

        # Good file should be present with all details
        good_file = next(item for item in result if item.name == "good_file.txt")
        assert good_file.type == "file"
        assert good_file.size is not None
        assert good_file.error is None

        # Bad file should be present with error
        bad_item = next(item for item in result if item.name == "bad_file")
        assert bad_item.type == "unknown"
        assert bad_item.error == "Permission denied for bad_file"
        assert bad_item.size is None

    async def test_list_nonexistent_directory(
        self: "TestListDirectoryTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup
        tool = ListDirectoryTool(mcp_server, fs_context)
        non_existent_dir = temp_dir / "does_not_exist"
        args = schemas.ListDirectoryArgs(path=str(non_existent_dir))

        # Execute & Verify
        with pytest.raises(McpError) as exc_info:
            await tool.list_directory(args)
        assert "does not exist" in str(exc_info.value)

    async def test_list_hidden_files(
        self: "TestListDirectoryTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup - create test directory with hidden and non-hidden files/directories
        test_dir = temp_dir / "hidden_test"
        test_dir.mkdir()

        # Create test files and directories
        (test_dir / "visible.txt").write_text("Visible file")
        (test_dir / ".hidden_file").write_text("Hidden file")
        (test_dir / "visible_dir").mkdir()
        (test_dir / ".hidden_dir").mkdir()

        # Test with show_hidden=False (default)
        tool = ListDirectoryTool(mcp_server, fs_context)
        args = schemas.ListDirectoryArgs(path=str(test_dir))

        # Execute
        result = await tool.list_directory(args)

        # Verify only non-hidden items are returned
        assert len(result) == 2  # Only visible.txt and visible_dir
        names = {item.name for item in result}
        assert "visible.txt" in names
        assert "visible_dir" in names
        assert ".hidden_file" not in names
        assert ".hidden_dir" not in names

        # Test with show_hidden=True
        args_show_hidden = schemas.ListDirectoryArgs(path=str(test_dir), show_hidden=True)

        # Execute with show_hidden=True
        result_hidden = await tool.list_directory(args_show_hidden)

        # Verify all items are returned including hidden ones
        assert len(result_hidden) == 4
        hidden_names = {item.name for item in result_hidden}
        assert "visible.txt" in hidden_names
        assert "visible_dir" in hidden_names
        assert ".hidden_file" in hidden_names
        assert ".hidden_dir" in hidden_names

        # Verify the types are correct
        for item in result_hidden:
            if item.name in ["visible_dir", ".hidden_dir"]:
                assert item.type == "directory"
            else:
                assert item.type == "file"

    async def test_list_with_pattern(
        self: "TestListDirectoryTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup - create test directory with various file types
        test_dir = temp_dir / "pattern_test"
        test_dir.mkdir()

        # Create test files with different extensions
        (test_dir / "file1.txt").write_text("Text file 1")
        (test_dir / "file2.txt").write_text("Text file 2")
        (test_dir / "document.pdf").write_text("PDF content")
        (test_dir / "image.jpg").write_text("Image data")
        (test_dir / "notes.TXT").write_text("Uppercase extension")
        (test_dir / "config.yaml").write_text("Config data")

        tool = ListDirectoryTool(mcp_server, fs_context)

        # Test with .txt pattern (case insensitive)
        args_txt = schemas.ListDirectoryArgs(path=str(test_dir), pattern="*.txt")
        result_txt = await tool.list_directory(args_txt)
        assert len(result_txt) == 3  # file1.txt, file2.txt, notes.TXT
        names_txt = {item.name.lower() for item in result_txt}
        assert "file1.txt" in names_txt
        assert "file2.txt" in names_txt
        assert "notes.txt" in names_txt

        # Test with .pdf pattern
        args_pdf = schemas.ListDirectoryArgs(path=str(test_dir), pattern="*.pdf")
        result_pdf = await tool.list_directory(args_pdf)
        assert len(result_pdf) == 1
        assert result_pdf[0].name == "document.pdf"

        # Test with no pattern (should return all files)
        args_all = schemas.ListDirectoryArgs(path=str(test_dir))
        result_all = await tool.list_directory(args_all)
        assert len(result_all) == 6  # All files we created

        # Test with show_hidden and pattern
        (test_dir / ".hidden.txt").write_text("Hidden text file")
        args_hidden = schemas.ListDirectoryArgs(path=str(test_dir), pattern="*.txt", show_hidden=True)
        result_hidden = await tool.list_directory(args_hidden)
        assert len(result_hidden) == 4  # 3 txt files + 1 hidden txt file

        # Test with a pattern that matches no files
        args_none = schemas.ListDirectoryArgs(path=str(test_dir), pattern="*.nonexistent")
        result_none = await tool.list_directory(args_none)
        assert len(result_none) == 0

    async def test_register_tools(
        self: "TestListDirectoryTool",
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        mocker: MockerFixture,
    ) -> None:
        # Setup
        tool = ListDirectoryTool(mcp_server, fs_context)

        # Create a mock to store the decorated function
        registered_function = None

        # Create a function that will be used as the decorator
        def mock_decorator(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                nonlocal registered_function
                registered_function = func
                return func

            return decorator

        # Set up the mock to return our decorator
        mock_tool = mocker.patch.object(mcp_server, "tool", side_effect=mock_decorator)

        # Execute
        tool.register_tools()

        # Verify the tool was registered
        mock_tool.assert_called_once()

        # Make sure we captured the function
        assert registered_function is not None, "Failed to register the function"

        # Test the registered function with mock data
        mock_args = schemas.ListDirectoryArgs(path="/test")
        mock_result = [schemas.DirectoryEntryItem(name="test", type="file")]

        # Create an async mock for list_directory
        mock_list_dir = AsyncMock(return_value=mock_result)
        mocker.patch.object(tool, "list_directory", mock_list_dir)

        # Call the registered function
        result = await registered_function(mock_args)

        # Verify the registered function calls list_directory with correct args
        mock_list_dir.assert_awaited_once_with(mock_args)
        assert result == mock_result
