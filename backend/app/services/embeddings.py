"""Embedding generation via the Google Generative AI Embeddings API.

Isolated behind a small class so the ingestion pipeline and search service
depend on this interface rather than the `google.generativeai` SDK
directly — tests substitute a fake client instead of hitting the network.
"""

import google.generativeai as genai

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Generates embedding vectors for text using Google's embedding model."""

    def __init__(self) -> None:
        """Initialize the service, configuring the Google AI SDK with the API key."""
        settings = get_settings()
        self._model = settings.embedding_model
        if settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)

    def embed_text(self, text: str, *, task_type: str = "retrieval_document") -> list[float]:
        """Generate an embedding vector for a single piece of text.

        Args:
            text: The text to embed.
            task_type: Google's embedding task hint — `retrieval_document`
                for content being indexed, `retrieval_query` for search
                queries (asymmetric embeddings improve retrieval quality).

        Returns:
            The embedding vector.

        Raises:
            ServiceUnavailableError: If the embedding API call fails.
        """
        try:
            result = genai.embed_content(model=self._model, content=text, task_type=task_type)
            return result["embedding"]
        except Exception as exc:
            logger.exception("Embedding generation failed")
            raise ServiceUnavailableError("Failed to generate embedding") from exc

    def embed_texts(
        self, texts: list[str], *, task_type: str = "retrieval_document"
    ) -> list[list[float]]:
        """Generate embedding vectors for multiple texts.

        Args:
            texts: The texts to embed.
            task_type: See `embed_text`.

        Returns:
            A list of embedding vectors, in the same order as `texts`.

        Raises:
            ServiceUnavailableError: If any embedding API call fails.
        """
        return [self.embed_text(text, task_type=task_type) for text in texts]
