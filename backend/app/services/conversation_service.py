"""Conversation service: orchestrates a chat turn end-to-end.

Coordinates the LangGraph RAG pipeline, message persistence, and the
short-term/long-term memory strategy from `app.services.rag.memory`.
"""

import uuid
from collections.abc import AsyncIterator

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.domain.entities import Citation, Conversation, Message
from app.domain.enums import MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.rag.generation import GenerationService
from app.services.rag.graph import build_answer_prompt, build_rag_graph, citations_from_results
from app.services.rag.memory import build_history_block, should_summarize, summarize_history
from app.services.search.search_service import SearchService


class ConversationService:
    """Coordinates conversations, messages, and the RAG pipeline that answers them."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        search_service: SearchService,
        generation_service: GenerationService,
    ) -> None:
        """Initialize the service with its collaborators.

        Args:
            conversation_repository: Repository for conversation persistence.
            message_repository: Repository for message persistence.
            search_service: Used by the RAG graph's retrieve node.
            generation_service: Used by the RAG graph's generate node, and for summarization.
        """
        self._conversations = conversation_repository
        self._messages = message_repository
        self._search = search_service
        self._generation = generation_service

    async def create_conversation(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation:
        """Start a new, empty conversation.

        Args:
            organization_id: The caller's organization.
            user_id: The user starting the conversation.

        Returns:
            The newly created `Conversation`.
        """
        return await self._conversations.create(organization_id=organization_id, user_id=user_id)

    async def list_conversations(self, user_id: uuid.UUID) -> list[Conversation]:
        """List all conversations started by a user.

        Args:
            user_id: The user's UUID.

        Returns:
            The user's conversations, newest first.
        """
        return await self._conversations.list_by_user(user_id)

    async def get_messages(
        self, conversation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[Message]:
        """List all messages in a conversation, scoped to the caller's organization.

        Args:
            conversation_id: The conversation's UUID.
            organization_id: The caller's organization, for tenant isolation.

        Returns:
            The conversation's messages, oldest first.

        Raises:
            NotFoundError: If the conversation doesn't exist or belongs to another organization.
        """
        conversation = await self._get_owned_conversation(conversation_id, organization_id)
        return await self._messages.list_by_conversation(conversation.id)

    async def send_message(
        self, *, conversation_id: uuid.UUID, organization_id: uuid.UUID, content: str
    ) -> Message:
        """Send a user message and return the generated assistant reply.

        Persists the user message, runs the RAG graph (retrieve + generate),
        persists the assistant reply with citations, and triggers history
        summarization if the conversation has grown long enough.

        Args:
            conversation_id: The conversation to post to.
            organization_id: The caller's organization, for tenant isolation.
            content: The user's message text.

        Returns:
            The assistant's reply `Message`, including citations.

        Raises:
            NotFoundError: If the conversation doesn't exist or belongs to another organization.
        """
        conversation = await self._get_owned_conversation(conversation_id, organization_id)

        await self._messages.create(
            conversation_id=conversation.id, role=MessageRole.USER, content=content
        )

        history_block = await self._build_history_block(conversation)

        settings = get_settings()
        graph = build_rag_graph(self._search, self._generation)
        result = await graph.ainvoke(
            {
                "query": content,
                "organization_id": organization_id,
                "history_block": history_block,
                "top_k": settings.search_top_k,
                "search_results": [],
                "answer": "",
            }
        )

        citations = citations_from_results(result["search_results"])
        assistant_message = await self._messages.create(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=result["answer"],
            citations=citations,
        )

        await self._maybe_summarize(conversation)

        return assistant_message

    async def stream_message(
        self, *, conversation_id: uuid.UUID, organization_id: uuid.UUID, content: str
    ) -> AsyncIterator[str]:
        """Send a user message and stream the assistant's reply incrementally.

        Persists the user message and retrieved context up front (same as
        `send_message`), then yields answer text as it's generated. The full
        assistant message (with citations) is persisted only after the
        stream completes, once the complete answer text is known.

        Args:
            conversation_id: The conversation to post to.
            organization_id: The caller's organization, for tenant isolation.
            content: The user's message text.

        Yields:
            Successive text chunks of the generated answer.

        Raises:
            NotFoundError: If the conversation doesn't exist or belongs to another organization.
        """
        conversation = await self._get_owned_conversation(conversation_id, organization_id)

        await self._messages.create(
            conversation_id=conversation.id, role=MessageRole.USER, content=content
        )

        history_block = await self._build_history_block(conversation)
        settings = get_settings()
        results = await self._search.search(
            organization_id=organization_id, query=content, top_k=settings.search_top_k
        )
        prompt = build_answer_prompt(history_block, results, content)

        full_answer_parts: list[str] = []
        for text_chunk in self._generation.generate_stream(prompt):
            full_answer_parts.append(text_chunk)
            yield text_chunk

        citations = citations_from_results(results)
        await self._messages.create(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="".join(full_answer_parts),
            citations=citations,
        )

        await self._maybe_summarize(conversation)

    async def _get_owned_conversation(
        self, conversation_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Conversation:
        """Fetch a conversation, raising if it's missing or in another organization.

        Args:
            conversation_id: The conversation's UUID.
            organization_id: The caller's organization.

        Returns:
            The matching `Conversation`.

        Raises:
            NotFoundError: If not found or owned by a different organization.
        """
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None or conversation.organization_id != organization_id:
            raise NotFoundError("Conversation not found")
        return conversation

    async def _build_history_block(self, conversation: Conversation) -> str:
        """Assemble the memory block (summary + recent turns) for the prompt.

        Args:
            conversation: The conversation being replied to.

        Returns:
            The formatted history block, per `app.services.rag.memory.build_history_block`.
        """
        settings = get_settings()
        recent = await self._messages.list_by_conversation(
            conversation.id, limit=settings.max_history_messages
        )
        return build_history_block(recent, conversation.summary)

    async def _maybe_summarize(self, conversation: Conversation) -> None:
        """Compress conversation history into a summary once it grows long enough.

        Args:
            conversation: The conversation to check and possibly summarize.
        """
        settings = get_settings()
        message_count = await self._messages.count_by_conversation(conversation.id)

        if should_summarize(
            message_count, summarize_after_messages=settings.summarize_after_messages
        ):
            all_messages = await self._messages.list_by_conversation(conversation.id)
            summary = summarize_history(self._generation, all_messages)
            await self._conversations.update_summary(conversation.id, summary)
