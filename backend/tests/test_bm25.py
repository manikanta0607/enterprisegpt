"""Unit tests for BM25 keyword search."""

import uuid

from app.services.search.bm25 import bm25_rank


def test_bm25_ranks_exact_match_highest():
    """A chunk containing all query terms should rank above ones with none."""
    id_relevant = uuid.uuid4()
    corpus = [
        (id_relevant, "The quarterly revenue report shows strong growth in Q3."),
        (uuid.uuid4(), "The office cafeteria menu changed to include more vegan options."),
        (uuid.uuid4(), "Employees enjoyed a team offsite in the mountains last month."),
        (uuid.uuid4(), "The new parking policy takes effect next Monday."),
    ]

    ranked = bm25_rank("quarterly revenue report", corpus, top_k=5)

    assert ranked[0][0] == id_relevant
    assert ranked[0][1] > 0


def test_bm25_returns_empty_for_empty_corpus():
    """Searching an empty corpus should return no results, not raise."""
    assert bm25_rank("anything", [], top_k=5) == []


def test_bm25_returns_empty_for_empty_query():
    """A blank query should return no results."""
    corpus = [(uuid.uuid4(), "Some document content here.")]
    assert bm25_rank("   ", corpus, top_k=5) == []


def test_bm25_respects_top_k():
    """The result list should never exceed top_k entries."""
    corpus = [(uuid.uuid4(), f"revenue report number {i} details") for i in range(10)]

    ranked = bm25_rank("revenue report", corpus, top_k=3)

    assert len(ranked) <= 3


def test_bm25_excludes_zero_score_matches():
    """Chunks with no term overlap should be excluded, not scored zero and kept."""
    id_match = uuid.uuid4()
    id_no_match = uuid.uuid4()
    corpus = [
        (id_match, "artificial intelligence and machine learning models"),
        (id_no_match, "gardening tips for growing tomatoes at home"),
        (uuid.uuid4(), "quarterly financial results for the retail division"),
        (uuid.uuid4(), "employee onboarding checklist for new hires"),
    ]

    ranked = bm25_rank("artificial intelligence", corpus, top_k=5)

    ranked_ids = [chunk_id for chunk_id, _ in ranked]
    assert id_match in ranked_ids
    assert id_no_match not in ranked_ids
