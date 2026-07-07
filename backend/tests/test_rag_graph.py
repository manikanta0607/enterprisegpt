"""Tests for the LangGraph RAG pipeline, with search and generation mocked."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.rag.graph import build_answer_prompt, build_rag_graph, citations_from_results
from app.services.search.search_service import SearchResult


def _make_result(content: str, filename: str = "doc.pdf") -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        filename=filename,
        content=content,
        score=0.9,
    )


@pytest.mark.asyncio
async def test_graph_retrieves_then_generates():
    """The compiled graph should call retrieve, then generate, in order."""
    result = _make_result("Refunds are processed within 30 days.")

    search_service = AsyncMock()
    search_service.search.return_value = [result]

    generation_service = MagicMock()
    generation_service.generate.return_value = "You can get a refund within 30 days."

    graph = build_rag_graph(search_service, generation_service)

    final_state = await graph.ainvoke(
        {
            "query": "What is the refund policy?",
            "organization_id": uuid.uuid4(),
            "history_block": "",
            "top_k": 5,
            "search_results": [],
            "answer": "",
        }
    )

    assert final_state["answer"] == "You can get a refund within 30 days."
    assert final_state["search_results"] == [result]
    search_service.search.assert_called_once()
    generation_service.generate.assert_called_once()


@pytest.mark.asyncio
async def test_graph_passes_retrieved_context_into_generation_prompt():
    """The prompt sent to generation should include the retrieved chunk content."""
    result = _make_result("The API rate limit is 100 requests per minute.")

    search_service = AsyncMock()
    search_service.search.return_value = [result]

    generation_service = MagicMock()
    generation_service.generate.return_value = "answer"

    graph = build_rag_graph(search_service, generation_service)

    await graph.ainvoke(
        {
            "query": "What is the rate limit?",
            "organization_id": uuid.uuid4(),
            "history_block": "",
            "top_k": 5,
            "search_results": [],
            "answer": "",
        }
    )

    sent_prompt = generation_service.generate.call_args[0][0]
    assert "100 requests per minute" in sent_prompt
    assert "What is the rate limit?" in sent_prompt


@pytest.mark.asyncio
async def test_graph_handles_no_search_results():
    """With no retrieved chunks, the prompt should note that plainly, not error."""
    search_service = AsyncMock()
    search_service.search.return_value = []

    generation_service = MagicMock()
    generation_service.generate.return_value = "I don't have enough information."

    graph = build_rag_graph(search_service, generation_service)

    final_state = await graph.ainvoke(
        {
            "query": "Anything about quantum computing?",
            "organization_id": uuid.uuid4(),
            "history_block": "",
            "top_k": 5,
            "search_results": [],
            "answer": "",
        }
    )

    sent_prompt = generation_service.generate.call_args[0][0]
    assert "No relevant documents were found" in sent_prompt
    assert final_state["answer"] == "I don't have enough information."


def test_build_answer_prompt_includes_history_block():
    """build_answer_prompt should splice in the history block verbatim."""
    result = _make_result("Some fact.")

    prompt = build_answer_prompt("Summary: prior discussion about X.", [result], "Follow-up?")

    assert "Summary: prior discussion about X." in prompt
    assert "Some fact." in prompt
    assert "Follow-up?" in prompt


def test_citations_from_results_preserves_order_and_fields():
    """citations_from_results should map each SearchResult to a Citation 1:1."""
    result_a = _make_result("Content A", filename="a.pdf")
    result_b = _make_result("Content B", filename="b.pdf")

    citations = citations_from_results([result_a, result_b])

    assert len(citations) == 2
    assert citations[0].filename == "a.pdf"
    assert citations[0].excerpt == "Content A"
    assert citations[1].filename == "b.pdf"
