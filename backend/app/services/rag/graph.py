"""LangGraph-based RAG pipeline: retrieve -> generate.

Structured as an explicit graph (rather than a plain function call chain) so
later phases can extend it with additional nodes — e.g. a "decide whether to
search at all" router, or additional tools — without restructuring the core
flow. Each node is a small, independently testable function; the graph just
wires them together.
"""

import uuid
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.domain.entities import Citation
from app.services.rag.generation import GenerationService
from app.services.search.search_service import SearchResult, SearchService

_ANSWER_PROMPT = (
    "{history_block}\n\n"
    "Use the following document excerpts to answer the question. If they don't contain "
    "the answer, say you don't have enough information rather than guessing.\n\n"
    "Context:\n{context}\n\n"
    "Question: {query}\n\nAnswer:"
)


class RAGState(TypedDict):
    """State threaded through the RAG graph's nodes."""

    query: str
    organization_id: uuid.UUID
    history_block: str
    top_k: int
    search_results: list[SearchResult]
    answer: str


def _format_context(results: list[SearchResult]) -> str:
    """Format retrieved chunks into a numbered context block for the prompt.

    Args:
        results: The retrieved, ranked search results.

    Returns:
        A numbered list of excerpts, each tagged with its source filename,
        so the model can naturally refer to "[1]", "[2]", etc.
    """
    if not results:
        return "(No relevant documents were found.)"
    return "\n\n".join(
        f"[{i}] (from {result.filename}) {result.content}" for i, result in enumerate(results, 1)
    )


def build_answer_prompt(history_block: str, results: list[SearchResult], query: str) -> str:
    """Build the full generation prompt from history, retrieved context, and the query.

    Exposed as a public function (rather than only living inside the graph's
    `generate` node) so the streaming chat path can reuse identical prompt
    construction without going through the graph, since streaming needs a
    generator rather than a single return value.

    Args:
        history_block: The formatted memory block (summary + recent turns).
        results: The retrieved search results to ground the answer in.
        query: The user's question.

    Returns:
        The fully assembled prompt string.
    """
    return _ANSWER_PROMPT.format(
        history_block=history_block, context=_format_context(results), query=query
    )


def build_rag_graph(search_service: SearchService, generation_service: GenerationService):
    """Construct and compile the retrieve -> generate LangGraph pipeline.

    Args:
        search_service: Used by the retrieve node to fetch relevant chunks.
        generation_service: Used by the generate node to produce the answer.

    Returns:
        A compiled LangGraph graph, invocable with `.ainvoke(initial_state)`.
    """

    async def retrieve(state: RAGState) -> RAGState:
        """Retrieve the most relevant chunks for the query via hybrid search."""
        results = await search_service.search(
            organization_id=state["organization_id"], query=state["query"], top_k=state["top_k"]
        )
        return {**state, "search_results": results}

    def generate(state: RAGState) -> RAGState:
        """Generate an answer grounded in the retrieved context and history."""
        prompt = build_answer_prompt(
            state["history_block"], state["search_results"], state["query"]
        )
        answer = generation_service.generate(prompt)
        return {**state, "answer": answer}

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def citations_from_results(results: list[SearchResult]) -> list[Citation]:
    """Convert retrieved search results into citations for the assistant message.

    Args:
        results: The search results used to ground the generated answer.

    Returns:
        A `Citation` for each retrieved result, preserving rank order.
    """
    return [
        Citation(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            filename=result.filename,
            excerpt=result.content,
        )
        for result in results
    ]
