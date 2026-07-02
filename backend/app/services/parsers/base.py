"""Base interface all document parsers implement."""

from abc import ABC, abstractmethod

from app.core.exceptions import ValidationError


class UnsupportedFileTypeError(ValidationError):
    """Raised when no parser is registered for a given content type."""


class DocumentParser(ABC):
    """Interface for extracting plain text from a raw document file."""

    @abstractmethod
    def extract_text(self, data: bytes) -> str:
        """Extract plain text content from raw file bytes.

        Args:
            data: The raw bytes of the uploaded file.

        Returns:
            The extracted plain text, with pages/slides/sections joined by
            double newlines.
        """
        raise NotImplementedError
