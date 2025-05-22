import logging
from typing import List

import fitz  # type: ignore # PyMuPDF

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

    async def read_pdf_file(self, args: ReadPdfFileArgs) -> PdfContent:
        """Read text content from a PDF file with page-level access.

        Args:
            args: The arguments containing the PDF file path and optional page numbers.

        Returns:
            PdfContent: Structured content of the PDF with page-wise text extraction.

        Raises:
            FileNotFoundError: If the specified PDF file does not exist.
            RuntimeError: If there is an error reading or processing the PDF.
            ValueError: If any specified page number is invalid.
        """
        valid_path = await self.fs_context.validate_path(args.path)

        try:
            with fitz.open(valid_path) as doc:
                total_pages = len(doc)

                # Validate page numbers if specified
                if args.page_numbers is not None:
                    invalid_pages = [
                        p for p in args.page_numbers if p < 1 or p > total_pages
                    ]
                    if invalid_pages:
                        raise ValueError(
                            f"Invalid page numbers: {invalid_pages}. "
                            f"Valid range is 1-{total_pages}."
                        )
                    pages_to_read = args.page_numbers
                else:
                    pages_to_read = list(range(1, total_pages + 1))

                # Extract text from specified pages
                pdf_pages: List[PdfPage] = []
                for page_num in pages_to_read:
                    page = doc[page_num - 1]  # Convert to 0-based index
                    text = page.get_text()
                    pdf_pages.append(
                        PdfPage(
                            page_number=page_num,
                            text_content=text.strip() if text else "",
                        )
                    )

                return PdfContent(
                    path=str(valid_path), total_pages=total_pages, pages=pdf_pages
                )

        except fitz.FileDataError as e:
            error_msg = f"Invalid or corrupted PDF file: {valid_path}"
            logger.error(f"{error_msg}: {e}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Error reading PDF file {valid_path}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def register_tools(self) -> None:
        """Register the PDF file reading tool with the MCP server."""

        @self.mcp_instance.tool()
        async def read_pdf_file_tool(args: ReadPdfFileArgs) -> PdfContent:
            return await self.read_pdf_file(args)
