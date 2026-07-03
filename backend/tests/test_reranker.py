"""Unit tests for term-overlap re-ranking."""

import uuid

from app.services.search.reranker import rerank_by_term_overlap


def test_exact_term_match_boosts_ranking():
    """A chunk with high fused score but no term overlap can be overtaken by
    one with exact query term matches, given a strong overlap weight."""
    high_fused_no_overlap = uuid.uuid4()
    low_fused_exact_overlap = uuid.uuid4()

    fused = [(high_fused_no_overlap, 1.0), (low_fused_exact_overlap, 0.1)]
    contents = {
        high_fused_no_overlap: "completely unrelated content about gardening",
        low_fused_exact_overlap: "quarterly revenue report Q3 earnings",
    }

    reranked = rerank_by_term_overlap(
        "quarterly revenue report", fused, contents, overlap_weight=0.9
    )

    assert reranked[0][0] == low_fused_exact_overlap


def test_no_overlap_preserves_fused_order_when_weight_is_zero():
    """With overlap_weight=0, the original fused order should be preserved."""
    a, b = uuid.uuid4(), uuid.uuid4()
    fused = [(a, 1.0), (b, 0.5)]
    contents = {a: "irrelevant text", b: "also irrelevant text"}

    reranked = rerank_by_term_overlap("query terms", fused, contents, overlap_weight=0.0)

    assert [item_id for item_id, _ in reranked] == [a, b]


def test_empty_fused_results_returns_empty():
    """Re-ranking an empty result list should return an empty list."""
    assert rerank_by_term_overlap("query", [], {}) == []


def test_missing_content_defaults_to_zero_overlap():
    """A chunk_id missing from contents_by_id should not raise, just score 0 overlap."""
    a = uuid.uuid4()
    reranked = rerank_by_term_overlap("query", [(a, 1.0)], {})

    assert len(reranked) == 1
