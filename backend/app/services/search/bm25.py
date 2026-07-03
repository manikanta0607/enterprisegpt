"""BM25 keyword search.

Scores a corpus of chunks against a query using the BM25 ranking function.
This is a pure, dependency-free-of-DB function so it can be unit tested
directly — the caller (SearchService) is responsible for fetching the
corpus from the database first.
"""

import re
import uuid

from rank_bm25 import BM25Okapi

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase and split text into alphanumeric tokens.

    Args:
        text: The text to tokenize.

    Returns:
        A list of lowercase tokens.
    """
    return _TOKEN_PATTERN.findall(text.lower())


def bm25_rank(
    query: str, corpus: list[tuple[uuid.UUID, str]], top_k: int = 20
) -> list[tuple[uuid.UUID, float]]:
    """Rank a corpus of chunks by BM25 relevance to a query.

    Args:
        query: The search query text.
        corpus: A list of (chunk_id, content) tuples to search over.
        top_k: Maximum number of results to return.

    Returns:
        A list of (chunk_id, bm25_score) tuples, highest score first.
        Returns an empty list if the corpus or query is empty.
    """
    if not corpus or not query.strip():
        return []

    tokenized_corpus = [_tokenize(content) for _, content in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))

    ranked = sorted(
        ((chunk_id, float(score)) for (chunk_id, _), score in zip(corpus, scores)),
        key=lambda pair: pair[1],
        reverse=True,
    )
    return [pair for pair in ranked if pair[1] > 0][:top_k]
