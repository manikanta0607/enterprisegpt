"""Tests for ConversationService, mocking repositories, search, and generation."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.domain.entities import Conversation, Message
from app.domain.enums import MessageRole
from app.services.conversation_service import ConversationService

pytestmark = pytest.mark.asyncio


def _make_conversation(org_id: uuid.UUID, summary: str | None = None) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=uuid.uuid4(),
        title="New conversation",
        summary=summary,
        created_at=datetime.now(timezone.utc),
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


def _build_service(conversation, message_count=1, search_results=None):
    conversation_repo = AsyncMock()
    conversation_repo.get_by_id.return_value = conversation

    message_repo = AsyncMock()
    message_repo.list_by_conversation.return_value = []
    message_repo.count_by_conversation.return_value = message_count
    message_repo.create.side_effect = lambda **kwargs: _make_message(
        kwargs["role"], kwargs["content"]
    )

    search_service = AsyncMock()
    search_service.search.return_value = search_results or []

    generation_service = MagicMock()
    generation_service.generate.return_value = "Generated answer."

    service = ConversationService(
        conversation_repository=conversation_repo,
        message_repository=message_repo,
        search_service=search_service,
        generation_service=generation_service,
    )
    return service, conversation_repo, message_repo, search_service, generation_service


async def test_send_message_raises_not_found_for_other_organization():
    """send_message should raise NotFoundError if the conversation belongs to another org."""
    conversation = _make_conversation(uuid.uuid4())
    service, *_ = _build_service(conversation)

    with pytest.raises(NotFoundError):
        await service.send_message(
            conversation_id=conversation.id, organization_id=uuid.uuid4(), content="hello"
        )


async def test_send_message_persists_user_and_assistant_messages():
    """send_message should persist both the user message and the generated reply."""
    org_id = uuid.uuid4()
    conversation = _make_conversation(org_id)
    service, _, message_repo, _, _ = _build_service(conversation)

    reply = await service.send_message(
        conversation_id=conversation.id, organization_id=org_id, content="What's our SLA?"
    )

    assert reply.content == "Generated answer."
    assert message_repo.create.call_count == 2
    roles_created = [call.kwargs["role"] for call in message_repo.create.call_args_list]
    assert roles_created == [MessageRole.USER, MessageRole.ASSISTANT]


async def test_send_message_triggers_summarization_past_threshold():
    """Once the message count crosses the threshold, the conversation summary should update."""
    org_id = uuid.uuid4()
    conversation = _make_conversation(org_id)
    service, conversation_repo, message_repo, _, generation_service = _build_service(
        conversation, message_count=25
    )
    message_repo.list_by_conversation.return_value = [
        _make_message(MessageRole.USER, "earlier question")
    ]

    await service.send_message(
        conversation_id=conversation.id, organization_id=org_id, content="another question"
    )

    conversation_repo.update_summary.assert_called_once()


async def test_send_message_does_not_summarize_below_threshold():
    """Below the summarization threshold, the conversation summary should not update."""
    org_id = uuid.uuid4()
    conversation = _make_conversation(org_id)
    service, conversation_repo, _, _, _ = _build_service(conversation, message_count=3)

    await service.send_message(
        conversation_id=conversation.id, organization_id=org_id, content="hello"
    )

    conversation_repo.update_summary.assert_not_called()


async def test_get_messages_raises_not_found_for_missing_conversation():
    """get_messages should raise NotFoundError for a nonexistent conversation."""
    conversation_repo = AsyncMock()
    conversation_repo.get_by_id.return_value = None

    service = ConversationService(
        conversation_repository=conversation_repo,
        message_repository=AsyncMock(),
        search_service=AsyncMock(),
        generation_service=MagicMock(),
    )

    with pytest.raises(NotFoundError):
        await service.get_messages(uuid.uuid4(), uuid.uuid4())
