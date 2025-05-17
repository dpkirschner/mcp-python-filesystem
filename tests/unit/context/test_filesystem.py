from pathlib import Path

import pytest
from mcp.shared.exceptions import McpError


class TestFilesystemContext:
    async def test_validate_path_within_allowed(self, fs_context, temp_dir):
        # Create a file in the temp dir
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        
        # Should not raise
        result = await fs_context.validate_path(str(test_file))
        assert result == test_file.resolve()
    
    async def test_validate_path_outside_allowed(self, fs_context, temp_dir):
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
    
    async def test_validate_nonexistent_file(self, fs_context, temp_dir):
        with pytest.raises(McpError) as exc_info:
            await fs_context.validate_path(str(temp_dir / "nonexistent.txt"))
        assert "does not exist" in str(exc_info.value)
    
    async def test_validate_path_for_nonexistent_but_creatable(self, fs_context, temp_dir):
        new_file = temp_dir / "new_dir" / "new_file.txt"
        
        # Should not raise for a non-existent but creatable path
        result = await fs_context.validate_path(
            str(new_file), 
            check_existence=False, 
            is_for_write=True
        )
        assert result == new_file.resolve()
    
    async def test_read_write_file_async(self, fs_context, temp_dir):
        test_file = temp_dir / "test_rw.txt"
        test_content = "Test content"
        
        # Test write
        await fs_context._write_file_async(test_file, test_content)
        
        # Test read
        content = await fs_context._read_file_async(test_file)
        assert content == test_content
    
    async def test_mkdir_async(self, fs_context, temp_dir):
        new_dir = temp_dir / "new_dir"
        
        # Should not exist initially
        assert not new_dir.exists()
        
        # Create directory
        await fs_context._mkdir_async(new_dir)
        
        # Should exist now
        assert new_dir.exists()
        assert new_dir.is_dir()
    
    async def test_rename_async(self, fs_context, temp_dir):
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
