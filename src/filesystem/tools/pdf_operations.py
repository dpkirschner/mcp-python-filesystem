import asyncio
import logging

import fitz  # type: ignore # PyMuPDF
from mcp import McpError

from .. import flat_args
from ..models.schemas import PdfContent, PdfPage, ReadPdfFileArgs
from ..tools import base

logger = logging.getLogger(__name__)


class ReadPDFFileTool(base.BaseTool):
    """Tool for reading content from PDF files with page-level access."""

    async def execute(self, args: ReadPdfFileArgs) -> PdfContent:
        """Execute the PDF file read operation.

        Args:
            args: The arguments for reading a PDF file, including the file path
                  and optional page numbers.

        Returns:
            PdfContent: Structured content of the PDF with page-wise text extraction.
        """
        return await self.read_pdf_file(args)

    @flat_args(ReadPdfFileArgs)
    async def read_pdf_file(self, args: ReadPdfFileArgs) -> PdfContent:
        """Read and extract text from a PDF file with page-level access.

        Args:
            path: The path to the PDF file to read.
            page_numbers: Optional list of 1-based page numbers to extract.

        Returns:
            PdfContent: Structured content of the PDF with page-wise text extraction.

        Raises:
            McpError: If the PDF file does not exist or is not accessible.
            RuntimeError: If the PDF is corrupted or invalid.
            ValueError: If any page number is out of range.
        """
        try:
            resolved_path = await self.fs_context.validate_path(
                args.path, check_existence=True
            )
            result = await asyncio.get_running_loop().run_in_executor(
                None, self._process_pdf_sync, str(resolved_path), args.page_numbers
            )

            if not isinstance(result, tuple) or len(result) != 3:
                raise RuntimeError(
                    f"Unexpected result format from PDF processing: {result}"
                )

            file_path, total_pages, pages = result
            return PdfContent(path=file_path, total_pages=total_pages, pages=pages)

        except McpError:
            raise
        except fitz.FileDataError as e:
            raise RuntimeError(f"Invalid or corrupted PDF file: {args.path}") from e
        except ValueError as e:
            raise ValueError(f"Invalid page numbers: {str(e)}") from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to process PDF file {args.path}: {str(e)}"
            ) from e

    def _process_pdf_sync(
        self, file_path: str, page_numbers: list[int] | None = None
    ) -> tuple[str, int, list[PdfPage]]:
        """Synchronously process a PDF file and extract text from specified pages.

        Args:
            file_path: Path to the PDF file.
            page_numbers: Optional list of 1-based page numbers to extract.

        Returns:
            A tuple containing (file_path, total_pages, list_of_pdf_pages)

        Raises:
            fitz.FileDataError: If the PDF is corrupted or invalid.
            ValueError: If any page number is out of range.
            Exception: For other errors during PDF processing.
        """
        with fitz.open(file_path) as doc:
            total_pages = len(doc)

            # Validate page numbers if specified
            if page_numbers is not None:
                invalid_pages = [p for p in page_numbers if p < 1 or p > total_pages]
                if invalid_pages:
                    raise ValueError(
                        f"Invalid page numbers: {invalid_pages}. "
                        f"Valid range is 1-{total_pages}."
                    )
                pages_to_read = page_numbers
            else:
                pages_to_read = list(range(1, total_pages + 1))

            # Extract text from specified pages
            pdf_pages: list[PdfPage] = []
            for page_num in pages_to_read:
                page = doc[page_num - 1]  # Convert to 0-based index
                text = page.get_text()
                pdf_pages.append(
                    PdfPage(
                        page_number=page_num,
                        text_content=text.strip() if text is not None else "",
                    )
                )

            return str(file_path), total_pages, pdf_pages

    def register_tools(self) -> None:
        """Register the PDF file reading tool with the MCP server."""

        @self.mcp_instance.tool()
        async def read_pdf_file_tool(args: ReadPdfFileArgs) -> PdfContent:
            result = await self.read_pdf_file(args)
            return result
