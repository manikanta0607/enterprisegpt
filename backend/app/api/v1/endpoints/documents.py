"""Document ingestion endpoints: upload, list, retrieve, and view chunks."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile

from app.api.deps import (
    get_chunk_repository,
    get_current_user,
    get_document_repository,
)
from app.core.rbac import require_role
from app.domain.entities import User
from app.domain.enums import Role
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import ChunkResponse, DocumentResponse
from app.services.document_service import DocumentService, process_document

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_document_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
) -> DocumentService:
    """Provide a `DocumentService` bound to the request's repositories."""
    return DocumentService(document_repository)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=201,
    summary="Upload a document",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    current_user: User = Depends(require_role(Role.MEMBER)),
    document_service: DocumentService = Depends(_get_document_service),
) -> DocumentResponse:
    """Upload a document for ingestion. Requires the MEMBER role or higher.

    The file is stored immediately and the document row is created with
    status `pending`. Parsing and chunking run in the background — poll
    `GET /documents/{id}` to see the status move to `completed` or `failed`.
    """
    data = await file.read()

    document = await document_service.upload_document(
        organization_id=current_user.organization_id,
        uploaded_by_user_id=current_user.id,
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )

    background_tasks.add_task(process_document, document.id)

    return DocumentResponse.model_validate(document)


@router.get("", response_model=list[DocumentResponse], summary="List documents")
async def list_documents(
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(_get_document_service),
) -> list[DocumentResponse]:
    """List all documents uploaded within the caller's organization."""
    documents = await document_service.list_documents(current_user.organization_id)
    return [DocumentResponse.model_validate(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentResponse, summary="Get a document")
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(_get_document_service),
) -> DocumentResponse:
    """Fetch a single document's metadata and ingestion status."""
    document = await document_service.get_document(document_id, current_user.organization_id)
    return DocumentResponse.model_validate(document)


@router.get(
    "/{document_id}/chunks",
    response_model=list[ChunkResponse],
    summary="Get a document's chunks",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(_get_document_service),
    chunk_repository: ChunkRepository = Depends(get_chunk_repository),
) -> list[ChunkResponse]:
    """List all chunks produced from a document, in document order.

    Returns an empty list if the document is still `pending`/`processing`,
    or if extraction produced no chunks.
    """
    await document_service.get_document(document_id, current_user.organization_id)
    chunks = await chunk_repository.list_by_document(document_id)
    return [ChunkResponse.model_validate(chunk) for chunk in chunks]
