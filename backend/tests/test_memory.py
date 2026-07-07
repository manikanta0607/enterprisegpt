"""Unit tests for conversation memory assembly and summarization triggers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.domain.entities import Message
from app.domain.enums import MessageRole
from app.services.rag.memory import (
    build_history_block,
    format_transcript,
    should_summarize,
    summarize_history,
)


def _make_message(role: MessageRole, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        role=role,
        content=content,
        citations=[],
        created_at=datetime.now(timezone.utc),
    )


def test_should_summarize_below_threshold():
    """Below the threshold, summarization should not be triggered."""
    assert not should_summarize(5, summarize_after_messages=20)


def test_should_summarize_at_threshold():
    """At or above the threshold, summarization should be triggered."""
    assert should_summarize(20, summarize_after_messages=20)
    assert should_summarize(25, summarize_after_messages=20)


def test_format_transcript_capitalizes_roles():
    """Transcript formatting should produce readable 'Role: content' lines."""
    messages = [
        _make_message(MessageRole.USER, "What's our refund policy?"),
        _make_message(MessageRole.ASSISTANT, "Refunds are available within 30 days."),
    ]

    transcript = format_transcript(messages)

    assert "User: What's our refund policy?" in transcript
    assert "Assistant: Refunds are available within 30 days." in transcript


def test_build_history_block_includes_summary_and_recent_messages():
    """The history block should combine both the summary and recent turns."""
    messages = [_make_message(MessageRole.USER, "Follow-up question")]

    block = build_history_block(messages, "Earlier we discussed pricing tiers.")

    assert "Earlier we discussed pricing tiers." in block
    assert "Follow-up question" in block


def test_build_history_block_with_no_summary():
    """Without a summary, only the recent-turns section should appear."""
    messages = [_make_message(MessageRole.USER, "Hello")]

    block = build_history_block(messages, None)

    assert "Summary of earlier conversation" not in block
    assert "Hello" in block


def test_build_history_block_empty_when_nothing_to_include():
    """With no summary and no messages, the block should be an empty string."""
    assert build_history_block([], None) == ""


def test_summarize_history_calls_generation_service():
    """summarize_history should delegate to the generation service and return its output."""
    fake_generation = MagicMock()
    fake_generation.generate.return_value = "A concise summary."
    messages = [_make_message(MessageRole.USER, "Tell me about pricing")]

    result = summarize_history(fake_generation, messages)

    assert result == "A concise summary."
    fake_generation.generate.assert_called_once()
