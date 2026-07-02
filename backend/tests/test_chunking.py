"""Unit tests for the text chunking service."""

from app.services.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    """Empty or whitespace-only text should produce zero chunks."""
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_returns_single_chunk():
    """Text shorter than chunk_size should come back as exactly one chunk."""
    chunks = chunk_text("This is a short piece of text.", chunk_size=1000)

    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].content == "This is a short piece of text."
    assert chunks[0].token_count == 7


def test_long_text_splits_into_multiple_chunks():
    """Text longer than chunk_size should split into multiple chunks."""
    paragraph = "Sentence number {}. " * 1
    long_text = "\n\n".join(f"Paragraph {i}. " * 20 for i in range(10))

    chunks = chunk_text(long_text, chunk_size=200, chunk_overlap=20)

    assert len(chunks) > 1
    for chunk in chunks:
        # Allow some slack since merging can slightly exceed the target due
        # to overlap being appended before the size check on the next piece.
        assert len(chunk.content) <= 250


def test_chunks_are_sequentially_indexed():
    """Chunk indices should be 0-based and strictly sequential."""
    long_text = "\n\n".join(f"Paragraph {i} with some content here." for i in range(20))

    chunks = chunk_text(long_text, chunk_size=100, chunk_overlap=10)

    indices = [c.index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_overlap_carries_context_between_chunks():
    """With overlap enabled, the tail of one chunk should reappear at the
    start of the next chunk."""
    long_text = "\n\n".join(f"Paragraph {i} filler filler filler." for i in range(15))

    chunks = chunk_text(long_text, chunk_size=80, chunk_overlap=15)

    assert len(chunks) > 1
    # The overlap text from the end of chunk 0 should appear near the start of chunk 1.
    tail_of_first = chunks[0].content[-15:]
    assert tail_of_first.strip() in chunks[1].content
