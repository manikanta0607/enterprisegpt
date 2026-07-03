"""Query rewriting: expands a user's search query for better retrieval.

A short, informally-phrased query ("pricing tiers?") often retrieves worse
than an expanded one ("what are the pricing tiers and their costs"). This
step is best-effort: if it fails or no API key is configured, the original
query is used unchanged rather than blocking the search.
"""

from abc import ABC, abstractmethod

import google.generativeai as genai

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_REWRITE_PROMPT = (
    "Rewrite the following search query to be more explicit and detailed for "
    "a document search engine, expanding abbreviations and vague phrasing. "
    "Return ONLY the rewritten query, no explanation, no quotes.\n\nQuery: {query}"
)


class QueryRewriter(ABC):
    """Interface for query rewriting strategies."""

    @abstractmethod
    def rewrite(self, query: str) -> str:
        """Rewrite a search query to improve retrieval quality.

        Args:
            query: The original user-provided search query.

        Returns:
            The rewritten query, or the original if rewriting is unavailable.
        """
        raise NotImplementedError


class NoOpQueryRewriter(QueryRewriter):
    """Returns the query unchanged. Used when no Google API key is configured."""

    def rewrite(self, query: str) -> str:
        """Return the query unchanged.

        Args:
            query: The original query.

        Returns:
            The same query, unmodified.
        """
        return query


class GeminiQueryRewriter(QueryRewriter):
    """Rewrites queries using a lightweight Gemini model."""

    def __init__(self) -> None:
        """Initialize the rewriter, configuring the Google AI SDK."""
        settings = get_settings()
        genai.configure(api_key=settings.google_api_key)
        self._model = genai.GenerativeModel(settings.query_rewrite_model)

    def rewrite(self, query: str) -> str:
        """Rewrite the query via Gemini, falling back to the original on failure.

        Args:
            query: The original user-provided search query.

        Returns:
            The rewritten query, or the original query if the API call fails
            or returns an empty response.
        """
        try:
            response = self._model.generate_content(_REWRITE_PROMPT.format(query=query))
            rewritten = (response.text or "").strip()
            return rewritten if rewritten else query
        except Exception:
            logger.warning("Query rewriting failed; falling back to original query")
            return query


def get_query_rewriter() -> QueryRewriter:
    """Select a query rewriter based on whether a Google API key is configured.

    Returns:
        A `GeminiQueryRewriter` if `GOOGLE_API_KEY` is set, otherwise a
        `NoOpQueryRewriter` so search keeps working without it.
    """
    settings = get_settings()
    if settings.google_api_key:
        return GeminiQueryRewriter()
    return NoOpQueryRewriter()
