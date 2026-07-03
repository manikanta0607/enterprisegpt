"""Tests for EmbeddingService, with google.generativeai mocked (no network calls)."""

from unittest.mock import patch

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.services.embeddings import EmbeddingService


def test_embed_text_returns_vector_from_sdk():
    """embed_text should return the embedding from the (mocked) SDK response."""
    fake_vector = [0.1, 0.2, 0.3]

    with patch("app.services.embeddings.genai.embed_content") as mock_embed:
        mock_embed.return_value = {"embedding": fake_vector}
        service = EmbeddingService()
        result = service.embed_text("hello world")

    assert result == fake_vector
    mock_embed.assert_called_once()


def test_embed_text_passes_task_type_through():
    """embed_text should forward the task_type hint to the SDK call."""
    with patch("app.services.embeddings.genai.embed_content") as mock_embed:
        mock_embed.return_value = {"embedding": [0.0]}
        service = EmbeddingService()
        service.embed_text("query text", task_type="retrieval_query")

    _, kwargs = mock_embed.call_args
    assert kwargs["task_type"] == "retrieval_query"


def test_embed_text_wraps_sdk_errors():
    """A failure in the underlying SDK call should surface as ServiceUnavailableError."""
    with patch("app.services.embeddings.genai.embed_content", side_effect=RuntimeError("boom")):
        service = EmbeddingService()
        with pytest.raises(ServiceUnavailableError):
            service.embed_text("hello")


def test_embed_texts_embeds_each_item_in_order():
    """embed_texts should return one vector per input text, in order."""
    with patch("app.services.embeddings.genai.embed_content") as mock_embed:
        mock_embed.side_effect = [{"embedding": [1.0]}, {"embedding": [2.0]}]
        service = EmbeddingService()
        result = service.embed_texts(["first", "second"])

    assert result == [[1.0], [2.0]]
