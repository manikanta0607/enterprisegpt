"""Extractive context compression.

Trims a chunk's content down to the sentences most relevant to the query,
reducing the tokens ultimately sent to an LLM in the RAG pipeline (Phase 5)
while keeping the response fast, deterministic, and free of an extra LLM
call. An LLM-based compressor could later implement the same function
signature as a drop-in upgrade.
"""

import re

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    """Lowercase and tokenize text into a set of words.

    Args:
        text: The text to tokenize.

    Returns:
        A set of lowercase tokens.
    """
    return set(_TOKEN_PATTERN.findall(text.lower()))


def compress_text(query: str, text: str, *, max_sentences: int = 3) -> str:
    """Extract the sentences most relevant to a query from a longer text.

    Args:
        query: The search query used to score sentence relevance.
        text: The full chunk content to compress.
        max_sentences: Maximum number of sentences to keep.

    Returns:
        The most relevant sentences, in their original order. Returns the
        original text unchanged if it already has `max_sentences` or fewer
        sentences.
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT_PATTERN.split(text.strip()) if s.strip()]

    if len(sentences) <= max_sentences:
        return text.strip()

    query_terms = _tokenize(query)
    scored = [
        (index, sentence, len(query_terms & _tokenize(sentence)))
        for index, sentence in enumerate(sentences)
    ]

    top_sentences = sorted(scored, key=lambda item: item[2], reverse=True)[:max_sentences]
    # Restore original sentence order for readability.
    top_sentences.sort(key=lambda item: item[0])

    return " ".join(sentence for _, sentence, _ in top_sentences)
