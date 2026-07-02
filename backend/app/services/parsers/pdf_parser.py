"""PDF text extraction using pypdf."""

import io

from pypdf import PdfReader

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser

logger = get_logger(__name__)


class PdfParser(DocumentParser):
    """Extracts text from PDF files, page by page."""

    def extract_text(self, data: bytes) -> str:
        """Extract text from all pages of a PDF.

        Args:
            data: The raw PDF file bytes.

        Returns:
            Extracted text, with each page separated by a double newline.

        Raises:
            ValidationError: If the file cannot be parsed as a valid PDF.
        """
        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception as exc:
            raise ValidationError("File could not be read as a valid PDF") from exc

        pages_text = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                logger.warning("Failed to extract text from PDF page %d; skipping", page_number)
                pages_text.append("")

        return "\n\n".join(pages_text).strip()
