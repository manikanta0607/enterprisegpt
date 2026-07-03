"""Unit tests for extractive context compression."""

from app.services.context_compression import compress_text


def test_short_text_returned_unchanged():
    """Text with fewer sentences than max_sentences should pass through unchanged."""
    text = "This is one sentence. This is another."

    result = compress_text("query", text, max_sentences=3)

    assert result == text


def test_long_text_is_compressed_to_relevant_sentences():
    """Compression should select the sentences most relevant to the query."""
    text = (
        "The company was founded in 2010. "
        "Quarterly revenue grew by twenty percent this year. "
        "The office recently adopted a new coffee machine. "
        "Revenue growth was driven primarily by the enterprise segment. "
        "Employees enjoyed a team offsite in the mountains."
    )

    result = compress_text("revenue growth", text, max_sentences=2)

    assert "revenue" in result.lower()
    assert "coffee machine" not in result


def test_compression_preserves_original_sentence_order():
    """Selected sentences should appear in their original document order,
    not sorted by relevance score."""
    text = (
        "Revenue grew substantially. "
        "The weather was nice that quarter. "
        "Revenue growth continued into the next quarter too."
    )

    result = compress_text("revenue", text, max_sentences=2)

    first_index = result.index("Revenue grew substantially")
    second_index = result.index("Revenue growth continued")
    assert first_index < second_index


def test_empty_text_returns_empty():
    """Empty input should return empty output without raising."""
    assert compress_text("query", "", max_sentences=3) == ""
