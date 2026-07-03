"""Tests for query rewriting, including the no-op fallback and Gemini path (mocked)."""

from unittest.mock import MagicMock, patch

from app.services.query_rewrite import (
    GeminiQueryRewriter,
    NoOpQueryRewriter,
    get_query_rewriter,
)


def test_noop_rewriter_returns_query_unchanged():
    """NoOpQueryRewriter should return the exact input query."""
    rewriter = NoOpQueryRewriter()
    assert rewriter.rewrite("what is our refund policy") == "what is our refund policy"


def test_factory_returns_noop_when_no_api_key_configured():
    """get_query_rewriter should fall back to NoOpQueryRewriter without an API key."""
    with patch("app.services.query_rewrite.get_settings") as mock_settings:
        mock_settings.return_value.google_api_key = ""
        rewriter = get_query_rewriter()

    assert isinstance(rewriter, NoOpQueryRewriter)


def test_factory_returns_gemini_rewriter_when_api_key_configured():
    """get_query_rewriter should return GeminiQueryRewriter when a key is set."""
    with patch("app.services.query_rewrite.get_settings") as mock_settings, patch(
        "app.services.query_rewrite.genai"
    ):
        mock_settings.return_value.google_api_key = "fake-key"
        mock_settings.return_value.query_rewrite_model = "models/gemini-1.5-flash"
        rewriter = get_query_rewriter()

    assert isinstance(rewriter, GeminiQueryRewriter)


def test_gemini_rewriter_returns_model_output():
    """GeminiQueryRewriter should return the (mocked) model's rewritten text."""
    with patch("app.services.query_rewrite.get_settings") as mock_settings, patch(
        "app.services.query_rewrite.genai"
    ) as mock_genai:
        mock_settings.return_value.google_api_key = "fake-key"
        mock_settings.return_value.query_rewrite_model = "models/gemini-1.5-flash"
        mock_model = MagicMock()
        mock_model.generate_content.return_value.text = "expanded rewritten query"
        mock_genai.GenerativeModel.return_value = mock_model

        rewriter = GeminiQueryRewriter()
        result = rewriter.rewrite("short query")

    assert result == "expanded rewritten query"


def test_gemini_rewriter_falls_back_to_original_on_failure():
    """A failed Gemini call should fall back to the original query, not raise."""
    with patch("app.services.query_rewrite.get_settings") as mock_settings, patch(
        "app.services.query_rewrite.genai"
    ) as mock_genai:
        mock_settings.return_value.google_api_key = "fake-key"
        mock_settings.return_value.query_rewrite_model = "models/gemini-1.5-flash"
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = RuntimeError("API error")
        mock_genai.GenerativeModel.return_value = mock_model

        rewriter = GeminiQueryRewriter()
        result = rewriter.rewrite("original query")

    assert result == "original query"
