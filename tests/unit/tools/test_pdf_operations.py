from pathlib import Path

import fitz  # type: ignore # PyMuPDF
import pytest
import pytest_mock
from mcp import McpError
from mcp.server.fastmcp import FastMCP

from filesystem.context.filesystem import FilesystemContext
from filesystem.models import schemas
from filesystem.tools import pdf_operations


class TestReadPDFFileTool:
    @pytest.fixture
    def sample_pdf(self, temp_dir: Path) -> Path:
        """Create a sample PDF file for testing."""
        pdf_path = temp_dir / "test.pdf"

        # Create a simple PDF with 3 pages
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text(
                point=(72, 72),  # 1 inch from top-left
                text=f"Page {i + 1} content",
                fontsize=12,
            )
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    @pytest.fixture
    def corrupted_pdf(self, temp_dir: Path) -> Path:
        """Create a corrupted PDF file for testing error handling."""
        pdf_path = temp_dir / "corrupted.pdf"
        pdf_path.write_bytes(b"Not a valid PDF content")
        return pdf_path

    async def test_read_pdf_all_pages(
        self,
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_pdf: Path,
    ) -> None:
        # Setup
        tool = pdf_operations.ReadPDFFileTool(mcp_server, fs_context)
        args = schemas.ReadPdfFileArgs(path=str(sample_pdf))

        # Execute
        result = await tool.read_pdf_file(args)

        # Verify
        assert isinstance(result, schemas.PdfContent)
        # Resolve paths to handle symlinks (e.g., /private/var vs /var on macOS)
        assert Path(result.path).resolve() == sample_pdf.resolve()
        assert result.total_pages == 3
        assert len(result.pages) == 3
        for i, page in enumerate(result.pages, 1):
            assert page.page_number == i
            assert f"Page {i} content" in page.text_content

    async def test_read_pdf_specific_pages(
        self,
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_pdf: Path,
    ) -> None:
        # Setup
        tool = pdf_operations.ReadPDFFileTool(mcp_server, fs_context)
        args = schemas.ReadPdfFileArgs(path=str(sample_pdf), page_numbers=[1, 3])

        # Execute
        result = await tool.read_pdf_file(args)

        # Verify
        assert len(result.pages) == 2
        assert result.pages[0].page_number == 1
        assert "Page 1 content" in result.pages[0].text_content
        assert result.pages[1].page_number == 3
        assert "Page 3 content" in result.pages[1].text_content

    async def test_read_pdf_invalid_page_number(
        self,
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        sample_pdf: Path,
    ) -> None:
        # Setup
        tool = pdf_operations.ReadPDFFileTool(mcp_server, fs_context)
        args = schemas.ReadPdfFileArgs(path=str(sample_pdf), page_numbers=[1, 99])

        # Execute & Verify
        with pytest.raises(RuntimeError) as exc_info:
            await tool.read_pdf_file(args)
        assert "Invalid page numbers: [99]" in str(exc_info.value)

    async def test_read_pdf_nonexistent_file(
        self,
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        temp_dir: Path,
    ) -> None:
        # Setup
        tool = pdf_operations.ReadPDFFileTool(mcp_server, fs_context)
        non_existent = temp_dir / "nonexistent.pdf"
        args = schemas.ReadPdfFileArgs(path=str(non_existent))

        # Execute & Verify
        with pytest.raises(McpError) as exc_info:
            await tool.read_pdf_file(args)
        assert "Path does not exist" in str(exc_info.value)

    async def test_read_corrupted_pdf(
        self,
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        corrupted_pdf: Path,
    ) -> None:
        # Setup
        tool = pdf_operations.ReadPDFFileTool(mcp_server, fs_context)
        args = schemas.ReadPdfFileArgs(path=str(corrupted_pdf))

        # Execute & Verify
        with pytest.raises(RuntimeError) as exc_info:
            await tool.read_pdf_file(args)
        assert "Invalid or corrupted PDF file" in str(exc_info.value)

    async def test_register_tools(
        self,
        mcp_server: FastMCP,
        fs_context: FilesystemContext,
        mocker: pytest_mock.MockerFixture,
        sample_pdf: Path,
    ) -> None:
        # Setup
        tool = pdf_operations.ReadPDFFileTool(mcp_server, fs_context)

        # Create a mock for the tool decorator
        mock_tool_decorator = mocker.MagicMock()

        # Set up the decorator chain: mock_tool_decorator() -> decorator() -> func
        mock_decorator = mocker.MagicMock()
        mock_tool_decorator.return_value = mock_decorator

        # Create a mock for the read_pdf_file method
        mock_read_pdf = mocker.patch.object(tool, "read_pdf_file")

        # Set up the return value for the read_pdf_file mock
        expected_result = schemas.PdfContent(
            path=str(sample_pdf),
            total_pages=1,
            pages=[schemas.PdfPage(page_number=1, text_content="Test content")],
        )
        mock_read_pdf.return_value = expected_result

        # Patch the mcp_instance.tool decorator
        mocker.patch.object(tool.mcp_instance, "tool", mock_tool_decorator)

        # Execute
        tool.register_tools()

        # Verify the tool decorator was called
        mock_tool_decorator.assert_called_once_with()

        # Get the registered function (the one that was decorated)
        registered_func = mock_decorator.call_args[0][0]

        # Call the registered function with test args
        test_args = schemas.ReadPdfFileArgs(path=str(sample_pdf))
        result = await registered_func(test_args)

        # Verify the result and that read_pdf_file was called with the correct args
        assert result == expected_result
        mock_read_pdf.assert_called_once_with(test_args)
