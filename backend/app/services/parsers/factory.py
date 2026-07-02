"""Selects the appropriate document parser for a given MIME content type."""

from app.services.parsers.base import DocumentParser, UnsupportedFileTypeError
from app.services.parsers.docx_parser import DocxParser
from app.services.parsers.ocr_parser import OcrParser
from app.services.parsers.pdf_parser import PdfParser
from app.services.parsers.pptx_parser import PptxParser

_PARSERS_BY_CONTENT_TYPE: dict[str, type[DocumentParser]] = {
    "application/pdf": PdfParser,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxParser,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": PptxParser,
    "image/png": OcrParser,
    "image/jpeg": OcrParser,
    "image/jpg": OcrParser,
}

SUPPORTED_CONTENT_TYPES = frozenset(_PARSERS_BY_CONTENT_TYPE.keys())


def get_parser_for_content_type(content_type: str) -> DocumentParser:
    """Return a parser instance for the given MIME content type.

    Args:
        content_type: The MIME type of the uploaded file, e.g. `application/pdf`.

    Returns:
        A `DocumentParser` capable of handling that content type.

    Raises:
        UnsupportedFileTypeError: If no parser is registered for the type.
    """
    parser_class = _PARSERS_BY_CONTENT_TYPE.get(content_type)
    if parser_class is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{content_type}'. "
            f"Supported types: {', '.join(sorted(SUPPORTED_CONTENT_TYPES))}"
        )
    return parser_class()
