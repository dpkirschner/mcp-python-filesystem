from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from mcp.shared.exceptions import McpError


class TestFilesystemContext:
    async def test_validate_path_within_allowed(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        # Create a file in the temp dir
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        # Should not raise
        result = await fs_context.validate_path(str(test_file))
        assert result == test_file.resolve()

    async def test_validate_path_outside_allowed(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        # Create a directory outside the allowed paths
        outside_dir = Path("/tmp/outside_allowed")
        outside_dir.mkdir(exist_ok=True)
        test_file = outside_dir / "test.txt"

        try:
            with pytest.raises(McpError) as exc_info:
                await fs_context.validate_path(str(test_file))
            assert "Path does not exist" in str(exc_info.value)
        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
            outside_dir.rmdir()

    async def test_validate_nonexistent_file(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        with pytest.raises(McpError) as exc_info:
            await fs_context.validate_path(str(temp_dir / "nonexistent.txt"))
        assert "does not exist" in str(exc_info.value)

    async def test_validate_path_for_nonexistent_but_creatable(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        new_file = temp_dir / "new_dir" / "new_file.txt"

        # Should not raise for a non-existent but creatable path
        result = await fs_context.validate_path(
            str(new_file), check_existence=False, is_for_write=True
        )
        assert result == new_file.resolve()

    async def test_read_write_file_async(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        test_file = temp_dir / "test_rw.txt"
        test_content = "Test content"

        # Test write
        await fs_context._write_file_async(test_file, test_content)

        # Test read
        content = await fs_context._read_file_async(test_file)
        assert content == test_content

    async def test_mkdir_async(self, fs_context: AsyncMock, temp_dir: Path) -> None:
        new_dir = temp_dir / "new_dir"

        # Should not exist initially
        assert not new_dir.exists()

        # Create directory
        await fs_context._mkdir_async(new_dir)

        # Should exist now
        assert new_dir.exists()
        assert new_dir.is_dir()

    async def test_rename_async(self, fs_context: AsyncMock, temp_dir: Path) -> None:
        # Create source file
        source = temp_dir / "source.txt"
        source.write_text("test")

        # Destination
        dest = temp_dir / "dest.txt"

        # Rename
        await fs_context._rename_async(source, dest)

        # Verify
        assert not source.exists()
        assert dest.exists()
        assert dest.read_text() == "test"

    async def test_path_validation_outside_allowed_directory(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        """Test that paths outside allowed directories are rejected."""
        # Create a file in a directory that's not in the allowed paths
        outside_dir = Path("/tmp/not_allowed_dir")
        outside_dir.mkdir(exist_ok=True)
        test_file = outside_dir / "test.txt"
        test_file.write_text("test")

        try:
            with pytest.raises(McpError) as exc_info:
                await fs_context.validate_path(str(test_file), check_existence=True)
            assert "Access denied" in str(exc_info.value)
            assert "outside allowed areas" in str(exc_info.value)
        finally:
            test_file.unlink()
            outside_dir.rmdir()

    async def test_validate_path_for_write_with_nonexistent_parents(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        """Test path validation for write operations with non-existent parent directories."""
        new_file = temp_dir / "new_dir" / "subdir" / "new_file.txt"

        # Should not raise and should return the resolved path
        result = await fs_context.validate_path(
            str(new_file), check_existence=False, is_for_write=True
        )
        assert result == new_file.resolve()

    async def test_validate_path_for_write_outside_allowed(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        """Test that write operations outside allowed directories are rejected."""
        # Try to create a file in a directory that's not in the allowed paths
        outside_dir = Path("/tmp/not_allowed_dir")
        new_file = outside_dir / "new_file.txt"

        with pytest.raises(McpError) as exc_info:
            await fs_context.validate_path(
                str(new_file), check_existence=False, is_for_write=True
            )
        assert "Access denied" in str(exc_info.value)
        assert "outside allowed areas" in str(exc_info.value)

    async def test_read_file_async_with_offset_and_length(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        """Test reading file with offset and length parameters."""
        test_file = temp_dir / "test_offset.txt"
        test_content = "Hello, this is a test file"
        test_file.write_text(test_content)

        # Read with offset and length
        content = await fs_context._read_file_async(
            test_file, offset=7, length=4, encoding="utf-8"
        )
        assert content == "this"

    @pytest.mark.parametrize("has_aiofiles", [True, False])
    async def test_read_file_async_fallback(
        self, fs_context: AsyncMock, temp_dir: Path, has_aiofiles: bool
    ) -> None:
        """Test that read_file_async falls back to sync operations when aiofiles is not available."""
        test_file = temp_dir / "test_fallback.txt"
        test_content = "Testing fallback mechanism"
        test_file.write_text(test_content)

        with patch.dict("sys.modules", {"aiofiles": None} if not has_aiofiles else {}):
            content = await fs_context._read_file_async(test_file)
            assert content == test_content

    async def test_write_file_async_fallback(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        """Test that write_file_async falls back to sync operations when aiofiles is not available."""
        test_file = temp_dir / "test_write_fallback.txt"
        test_content = "Testing write fallback"

        with patch.dict("sys.modules", {"aiofiles": None}):
            await fs_context._write_file_async(test_file, test_content)
            assert test_file.read_text() == test_content

    async def test_get_stat_success(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        """Test successful stat retrieval."""
        test_file = temp_dir / "stat_test.txt"
        test_file.write_text("test")

        stat_result = await fs_context._get_stat(test_file)
        assert stat_result is not None
        assert stat_result.st_size == 4  # Length of "test"

    async def test_get_stat_not_found(
        self, fs_context: AsyncMock, temp_dir: Path
    ) -> None:
        """Test stat retrieval for non-existent file raises FileNotFoundError."""
        non_existent = temp_dir / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            await fs_context._get_stat(non_existent)
