"""Document service: upload orchestration and the ingestion pipeline.

`upload_document` runs synchronously within the request (store raw bytes,
create the DB row) and returns immediately with status PENDING. The actual
parse/chunk work happens in `process_document`, invoked as a FastAPI
`BackgroundTask` so uploads don't block on parsing large files.

Note: FastAPI `BackgroundTasks` run in the same process after the response
is sent — adequate for Phase 3. A dedicated worker queue (Celery/RQ backed
by Redis) is the natural upgrade path once ingestion volume or parsing time
grows, and is planned as part of Phase 8 (scaling & background workers).
"""

import uuid

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.entities import Document
from app.domain.enums import DocumentStatus
from app.infrastructure.database.session import get_session_factory
from app.infrastructure.storage.document_storage import (
    build_storage_key,
    download_document_bytes,
    upload_document_bytes,
)
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.chunking import chunk_text
from app.services.embeddings import EmbeddingService
from app.services.parsers.factory import SUPPORTED_CONTENT_TYPES, get_parser_for_content_type

logger = get_logger(__name__)

MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class DocumentService:
    """Coordinates document upload, storage, and the ingestion pipeline."""

    def __init__(self, document_repository: DocumentRepository) -> None:
        """Initialize the service with a document repository.

        Args:
            document_repository: Repository bound to the current request's DB session.
        """
        self._documents = document_repository

    async def upload_document(
        self,
        *,
        organization_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> Document:
        """Validate, store, and register a new document upload.

        Args:
            organization_id: The uploading user's organization.
            uploaded_by_user_id: The user performing the upload.
            filename: The original filename.
            content_type: The MIME type of the uploaded file.
            data: The raw file bytes.

        Returns:
            The newly created `Document` entity, with status PENDING.

        Raises:
            ValidationError: If the file is empty, too large, or an
                unsupported type.
        """
        if not data:
            raise ValidationError("Uploaded file is empty")
        if len(data) > MAX_UPLOAD_SIZE_BYTES:
            raise ValidationError(
                f"File exceeds the maximum upload size of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB"
            )
        if content_type not in SUPPORTED_CONTENT_TYPES:
            raise ValidationError(
                f"Unsupported file type '{content_type}'. "
                f"Supported types: {', '.join(sorted(SUPPORTED_CONTENT_TYPES))}"
            )

        storage_key = build_storage_key(organization_id, filename)
        upload_document_bytes(storage_key, data, content_type)

        document = await self._documents.create(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            content_type=content_type,
            storage_key=storage_key,
        )
        logger.info("Document %s uploaded and queued for processing", document.id)
        return document

    async def get_document(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> Document:
        """Fetch a document, scoped to the caller's organization.

        Args:
            document_id: The document's UUID.
            organization_id: The caller's organization, for tenant isolation.

        Returns:
            The matching `Document` entity.

        Raises:
            NotFoundError: If the document doesn't exist or belongs to another organization.
        """
        document = await self._documents.get_by_id(document_id)
        if document is None or document.organization_id != organization_id:
            raise NotFoundError("Document not found")
        return document

    async def list_documents(self, organization_id: uuid.UUID) -> list[Document]:
        """List all documents in the caller's organization.

        Args:
            organization_id: The caller's organization.

        Returns:
            A list of `Document` entities, newest first.
        """
        return await self._documents.list_by_organization(organization_id)


async def _embed_chunks(chunk_repo: ChunkRepository, chunks: list) -> None:
    """Generate and persist embeddings for a batch of newly created chunks.

    Skips embedding generation entirely (logging a warning once) if no
    Google API key is configured, so the ingestion pipeline still completes
    successfully in that case — chunks simply remain searchable via BM25
    only until embeddings are backfilled.

    Args:
        chunk_repo: Repository used to persist computed embeddings.
        chunks: The `Chunk` entities just created for this document.
    """
    settings = get_settings()
    if not settings.google_api_key:
        logger.warning(
            "GOOGLE_API_KEY not configured; skipping embedding generation for %d chunks",
            len(chunks),
        )
        return

    embedding_service = EmbeddingService()
    for chunk in chunks:
        try:
            vector = embedding_service.embed_text(chunk.content, task_type="retrieval_document")
            await chunk_repo.update_embedding(chunk.id, vector)
        except Exception:
            logger.exception("Failed to embed chunk %s; leaving unembedded", chunk.id)


async def process_document(document_id: uuid.UUID) -> None:
    """Background pipeline: download, parse, chunk, and persist a document.

    Opens its own DB session since it runs after the request session has
    already been closed (this is a `BackgroundTask`, not part of the request
    lifecycle).

    Args:
        document_id: The document to process.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        document_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)

        document = await document_repo.get_by_id(document_id)
        if document is None:
            logger.error("process_document called for unknown document %s", document_id)
            return

        await document_repo.update_status(document_id, DocumentStatus.PROCESSING)

        try:
            raw_bytes = download_document_bytes(document.storage_key)
            parser = get_parser_for_content_type(document.content_type)
            extracted_text = parser.extract_text(raw_bytes)

            if not extracted_text.strip():
                raise ValidationError("No extractable text was found in this document")

            text_chunks = chunk_text(extracted_text)
            created_chunks = await chunk_repo.bulk_create(
                document_id,
                [(c.index, c.content, c.token_count) for c in text_chunks],
            )

            await _embed_chunks(chunk_repo, created_chunks)

            await document_repo.update_status(document_id, DocumentStatus.COMPLETED)
            logger.info(
                "Document %s processed successfully: %d chunks", document_id, len(text_chunks)
            )
        except Exception as exc:
            logger.exception("Document %s processing failed", document_id)
            await document_repo.update_status(document_id, DocumentStatus.FAILED, str(exc))
