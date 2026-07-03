"""Reciprocal Rank Fusion (RRF) — combines multiple ranked lists into one.

RRF is used here to merge vector-similarity and BM25 keyword rankings
without needing to normalize their differently-scaled scores: it only uses
each item's *rank* within each list, which sidesteps the score-comparability
problem entirely.
"""

import uuid


def reciprocal_rank_fusion(
    rankings: list[list[uuid.UUID]], *, k: int = 60, top_k: int = 10
) -> list[tuple[uuid.UUID, float]]:
    """Fuse multiple ranked lists of IDs into a single ranking.

    Each list contributes a score of `1 / (k + rank)` to every ID it
    contains (rank is 0-indexed), and scores are summed across lists. Items
    appearing near the top of multiple lists naturally rise to the top of
    the fused ranking.

    Args:
        rankings: A list of ranked ID lists (e.g. [vector_ranking, bm25_ranking]),
            each already sorted best-first.
        k: RRF's smoothing constant; higher values reduce the influence of
            rank position differences. 60 is the standard default from the
            original RRF paper.
        top_k: Maximum number of fused results to return.

    Returns:
        A list of (id, fused_score) tuples, highest score first.
    """
    scores: dict[uuid.UUID, float] = {}

    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)

    fused = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return fused[:top_k]
