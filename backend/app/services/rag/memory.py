"""Conversation memory: assembling prompt context from history + summary.

Two tiers of memory:
- **Short-term**: the most recent `max_history_messages` are included verbatim.
- **Long-term**: once a conversation exceeds `summarize_after_messages`, older
  turns are compressed into a running summary (stored on the `Conversation`
  row) so context isn't lost as conversations grow beyond what fits in a
  prompt.

All functions here are pure (or take an injected `GenerationService` for the
one that needs an LLM call), so the branching logic is directly unit testable.
"""

from app.domain.entities import Message
from app.services.rag.generation import GenerationService

_SUMMARIZE_PROMPT = (
    "Summarize the key facts, decisions, and context from this conversation so far in "
    "3-5 sentences. Focus on information that would be useful to remember in later turns. "
    "Return ONLY the summary, no preamble.\n\nConversation:\n{transcript}"
)


def should_summarize(message_count: int, *, summarize_after_messages: int) -> bool:
    """Determine whether a conversation's history should be compressed.

    Args:
        message_count: Total messages currently in the conversation.
        summarize_after_messages: Threshold from settings.

    Returns:
        True if `message_count` has just crossed the summarization threshold.
    """
    return message_count >= summarize_after_messages


def format_transcript(messages: list[Message]) -> str:
    """Format a list of messages into a plain-text transcript for summarization.

    Args:
        messages: The messages to format, in chronological order.

    Returns:
        A transcript with one "Role: content" line per message.
    """
    return "\n".join(f"{message.role.value.capitalize()}: {message.content}" for message in messages)


def summarize_history(generation_service: GenerationService, messages: list[Message]) -> str:
    """Compress a list of messages into a short running summary via the LLM.

    Args:
        generation_service: The LLM service used to produce the summary.
        messages: The messages to summarize, in chronological order.

    Returns:
        A short summary of the conversation so far.
    """
    transcript = format_transcript(messages)
    return generation_service.generate(_SUMMARIZE_PROMPT.format(transcript=transcript))


def build_history_block(recent_messages: list[Message], summary: str | None) -> str:
    """Build the "memory" portion of the RAG prompt from summary + recent turns.

    Args:
        recent_messages: The most recent messages to include verbatim.
        summary: A compressed summary of older history, if one exists.

    Returns:
        A formatted block combining the summary (if any) and recent turns,
        ready to be inserted into the generation prompt. Returns an empty
        string if there's no summary and no recent messages.
    """
    parts = []
    if summary:
        parts.append(f"Summary of earlier conversation:\n{summary}")
    if recent_messages:
        parts.append(f"Recent conversation:\n{format_transcript(recent_messages)}")
    return "\n\n".join(parts)
