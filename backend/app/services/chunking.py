"""Text chunking for the RAG pipeline.

Implements recursive character splitting: text is split on the largest
available separator (paragraphs, then lines, then sentences, then words)
that keeps chunks under `chunk_size`, with `chunk_overlap` characters
repeated between consecutive chunks to preserve context across boundaries.

Token counting here is a fast approximation (whitespace word count); Phase 4
(Embeddings) can swap in a model-specific tokenizer without changing this
module's public interface.
"""

from dataclasses import dataclass

_SEPARATORS = ["\n\n", "\n", ". ", " "]


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A single chunk produced by the chunking service, before persistence."""

    index: int
    content: str
    token_count: int


def _approximate_token_count(text: str) -> int:
    """Approximate the token count of a text via whitespace splitting.

    Args:
        text: The text to count.

    Returns:
        An approximate token count, adequate for chunk-size budgeting until
        a real tokenizer is wired in during the Embeddings phase.
    """
    return len(text.split())


def _split_on_separator(text: str, separator: str) -> list[str]:
    """Split text on a separator, keeping the separator's effect on parts.

    Args:
        text: The text to split.
        separator: The separator string to split on.

    Returns:
        A list of non-empty text parts.
    """
    return [part for part in text.split(separator) if part.strip()]


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Recursively split text using the separator hierarchy.

    Args:
        text: The text to split.
        chunk_size: Maximum character length per chunk.
        separators: Ordered list of separators to try, coarsest first.

    Returns:
        A list of text pieces, each at or under `chunk_size` where possible.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    if not separators:
        # Base case: no separators left, hard-split by character count.
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    separator, *rest_separators = separators
    parts = _split_on_separator(text, separator)

    if len(parts) <= 1:
        # This separator didn't help; try the next, finer-grained one.
        return _recursive_split(text, chunk_size, rest_separators)

    pieces: list[str] = []
    for part in parts:
        if len(part) <= chunk_size:
            pieces.append(part)
        else:
            pieces.extend(_recursive_split(part, chunk_size, rest_separators))
    return pieces


def _merge_with_overlap(pieces: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Merge small pieces into chunks close to `chunk_size`, with overlap.

    Args:
        pieces: Text pieces from `_recursive_split`, each under `chunk_size`.
        chunk_size: Target maximum characters per merged chunk.
        chunk_overlap: Characters of trailing context to carry into the next chunk.

    Returns:
        A list of merged chunk strings.
    """
    if not pieces:
        return []

    chunks: list[str] = []
    current = pieces[0]

    for piece in pieces[1:]:
        candidate = f"{current} {piece}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current)
            overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = f"{overlap_text} {piece}".strip()

    if current.strip():
        chunks.append(current)

    return chunks


def chunk_text(text: str, *, chunk_size: int = 1000, chunk_overlap: int = 150) -> list[TextChunk]:
    """Split text into overlapping chunks suitable for embedding and retrieval.

    Args:
        text: The full extracted document text.
        chunk_size: Target maximum characters per chunk. Defaults to 1000.
        chunk_overlap: Characters of overlap carried between consecutive
            chunks to preserve cross-boundary context. Defaults to 150.

    Returns:
        A list of `TextChunk` objects, indexed in document order. Returns an
        empty list if `text` is empty or whitespace-only.
    """
    text = text.strip()
    if not text:
        return []

    pieces = _recursive_split(text, chunk_size, _SEPARATORS)
    merged = _merge_with_overlap(pieces, chunk_size, chunk_overlap)

    return [
        TextChunk(index=i, content=chunk, token_count=_approximate_token_count(chunk))
        for i, chunk in enumerate(merged)
    ]
