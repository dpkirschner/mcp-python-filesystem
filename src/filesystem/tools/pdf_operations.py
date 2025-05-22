import asyncio
import logging
from typing import List, Tuple

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

    def _process_pdf_sync(
        self, file_path: str, page_numbers: List[int] | None = None
    ) -> Tuple[str, int, List[PdfPage]]:
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
            pdf_pages: List[PdfPage] = []
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
            # Process the PDF in a separate thread to avoid blocking the event loop
            file_path, total_pages, pdf_pages = await asyncio.to_thread(
                self._process_pdf_sync, str(valid_path), args.page_numbers
            )

            return PdfContent(
                path=file_path,
                total_pages=total_pages,
                pages=pdf_pages,
            )

        except FileNotFoundError:
            raise
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
