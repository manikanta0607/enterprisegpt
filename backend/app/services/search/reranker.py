"""Re-ranking: a lightweight second pass over fused search results.

Boosts results whose content contains query terms verbatim, which RRF alone
can miss — a chunk ranked #1 in vector similarity but with zero literal
term overlap is often a false positive (semantically adjacent, not
actually relevant). This is a heuristic, not a learned cross-encoder;
swapping in a real cross-encoder model is a natural future upgrade behind
this same function signature.
"""

import re
import uuid

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _term_overlap_ratio(query_terms: set[str], content: str) -> float:
    """Compute the fraction of query terms that appear literally in content.

    Args:
        query_terms: Lowercased, tokenized query terms.
        content: The candidate chunk's text content.

    Returns:
        A ratio in [0, 1]: the fraction of query terms found in the content.
    """
    if not query_terms:
        return 0.0
    content_terms = set(_TOKEN_PATTERN.findall(content.lower()))
    return len(query_terms & content_terms) / len(query_terms)


def rerank_by_term_overlap(
    query: str,
    fused_results: list[tuple[uuid.UUID, float]],
    contents_by_id: dict[uuid.UUID, str],
    *,
    overlap_weight: float = 0.3,
) -> list[tuple[uuid.UUID, float]]:
    """Re-rank fused search results with a literal term-overlap boost.

    Args:
        query: The original search query.
        fused_results: (chunk_id, fused_score) pairs from `reciprocal_rank_fusion`,
            already sorted best-first.
        contents_by_id: Chunk content keyed by chunk_id, used to compute overlap.
        overlap_weight: How much weight the term-overlap boost carries relative
            to the original fused score (both are normalized to [0, 1] first).

    Returns:
        A re-sorted list of (chunk_id, final_score) tuples, highest first.
    """
    if not fused_results:
        return []

    query_terms = set(_TOKEN_PATTERN.findall(query.lower()))
    max_fused_score = max(score for _, score in fused_results) or 1.0

    rescored = []
    for chunk_id, fused_score in fused_results:
        normalized_fused = fused_score / max_fused_score
        overlap = _term_overlap_ratio(query_terms, contents_by_id.get(chunk_id, ""))
        final_score = (1 - overlap_weight) * normalized_fused + overlap_weight * overlap
        rescored.append((chunk_id, final_score))

    return sorted(rescored, key=lambda pair: pair[1], reverse=True)
