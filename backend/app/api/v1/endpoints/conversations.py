"""Conversation endpoints: create, list, send messages (sync + streaming)."""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_chunk_repository,
    get_conversation_repository,
    get_current_user,
    get_document_repository,
    get_message_repository,
)
from app.domain.entities import User
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.conversation import (
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.services.conversation_service import ConversationService
from app.services.query_rewrite import get_query_rewriter
from app.services.rag.generation import GenerationService
from app.services.search.search_service import SearchService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation_service(
    conversation_repository: ConversationRepository = Depends(get_conversation_repository),
    message_repository: MessageRepository = Depends(get_message_repository),
    chunk_repository: ChunkRepository = Depends(get_chunk_repository),
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> ConversationService:
    """Provide a `ConversationService` with all collaborators wired up."""
    from app.services.embeddings import EmbeddingService

    search_service = SearchService(
        chunk_repository=chunk_repository,
        document_repository=document_repository,
        embedding_service=EmbeddingService(),
        query_rewriter=get_query_rewriter(),
    )
    return ConversationService(
        conversation_repository=conversation_repository,
        message_repository=message_repository,
        search_service=search_service,
        generation_service=GenerationService(),
    )


@router.post(
    "", response_model=ConversationResponse, status_code=201, summary="Start a conversation"
)
async def create_conversation(
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(_get_conversation_service),
) -> ConversationResponse:
    """Start a new, empty conversation."""
    conversation = await conversation_service.create_conversation(
        organization_id=current_user.organization_id, user_id=current_user.id
    )
    return ConversationResponse.model_validate(conversation)


@router.get("", response_model=list[ConversationResponse], summary="List your conversations")
async def list_conversations(
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(_get_conversation_service),
) -> list[ConversationResponse]:
    """List all conversations started by the current user."""
    conversations = await conversation_service.list_conversations(current_user.id)
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="Get a conversation's message history",
)
async def get_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(_get_conversation_service),
) -> list[MessageResponse]:
    """List all messages in a conversation, oldest first."""
    messages = await conversation_service.get_messages(
        conversation_id, current_user.organization_id
    )
    return [MessageResponse.model_validate(m) for m in messages]


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    summary="Send a message and get the assistant's reply",
)
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(_get_conversation_service),
) -> MessageResponse:
    """Send a user message and receive the full assistant reply (non-streaming).

    Runs the LangGraph RAG pipeline (retrieve -> generate), grounded in the
    caller's organization's documents plus this conversation's memory.
    """
    reply = await conversation_service.send_message(
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        content=body.content,
    )
    return MessageResponse.model_validate(reply)


@router.post(
    "/{conversation_id}/messages/stream",
    summary="Send a message and stream the assistant's reply",
)
async def stream_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    conversation_service: ConversationService = Depends(_get_conversation_service),
) -> StreamingResponse:
    """Send a user message and stream the assistant's reply as plain text chunks.

    The full message (with citations) is persisted once the stream completes;
    fetch `GET /conversations/{id}/messages` afterward to see citations.
    """
    generator = conversation_service.stream_message(
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        content=body.content,
    )
    return StreamingResponse(generator, media_type="text/plain")
