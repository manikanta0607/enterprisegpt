"""OCR text extraction from images using pytesseract (Tesseract OCR).

Requires the `tesseract-ocr` system package to be installed (handled in the
backend Dockerfile). Used both for standalone image uploads (PNG/JPEG) and
can be extended in a later phase to run per-page on scanned PDFs.
"""

import io

import pytesseract
from PIL import Image

from app.core.exceptions import ValidationError
from app.services.parsers.base import DocumentParser


class OcrParser(DocumentParser):
    """Extracts text from images via Tesseract OCR."""

    def extract_text(self, data: bytes) -> str:
        """Run OCR on an image and return the recognized text.

        Args:
            data: The raw image file bytes (PNG, JPEG, etc).

        Returns:
            The recognized text, stripped of leading/trailing whitespace.

        Raises:
            ValidationError: If the file cannot be read as a valid image.
        """
        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except Exception as exc:
            raise ValidationError("File could not be read as a valid image") from exc

        return pytesseract.image_to_string(image).strip()
