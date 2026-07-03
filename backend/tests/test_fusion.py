"""Unit tests for Reciprocal Rank Fusion."""

import uuid

from app.services.search.fusion import reciprocal_rank_fusion


def test_item_ranked_first_in_both_lists_wins():
    """An ID at rank 0 in both lists should score highest in the fusion."""
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    fused = reciprocal_rank_fusion([[a, b, c], [a, c, b]], top_k=5)

    assert fused[0][0] == a


def test_item_only_in_one_list_still_included():
    """An ID appearing in only one ranking should still be included, ranked lower."""
    a, b = uuid.uuid4(), uuid.uuid4()

    fused = reciprocal_rank_fusion([[a], []], top_k=5)

    fused_ids = [item_id for item_id, _ in fused]
    assert a in fused_ids
    assert b not in fused_ids


def test_appearing_in_multiple_lists_outranks_appearing_in_one():
    """An item present in both lists (even at a worse rank) should generally
    outrank an item present in only one list at the top rank, given enough
    overlap — this is the core value proposition of RRF over any single ranking."""
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    # 'a' is rank 0 only in list 1. 'b' is rank 1 in both lists.
    fused = reciprocal_rank_fusion([[a, b], [c, b]], top_k=5)

    scores = dict(fused)
    assert scores[b] > scores[c]


def test_respects_top_k():
    """The fused result list should never exceed top_k entries."""
    ids = [uuid.uuid4() for _ in range(10)]

    fused = reciprocal_rank_fusion([ids], top_k=3)

    assert len(fused) == 3


def test_empty_rankings_return_empty_result():
    """Fusing empty ranking lists should return an empty result, not raise."""
    assert reciprocal_rank_fusion([[], []], top_k=5) == []
