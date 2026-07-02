"""Document raw-file storage on MinIO.

Wraps the low-level MinIO client with document-specific conventions: object
keys are namespaced by organization to keep tenants' files logically
separated, and this module is the only place that constructs those keys.
"""

import io
import uuid

from minio.error import S3Error

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger
from app.infrastructure.storage.minio_client import get_minio_client

logger = get_logger(__name__)


def build_storage_key(organization_id: uuid.UUID, filename: str) -> str:
    """Build a namespaced, collision-resistant MinIO object key.

    Args:
        organization_id: The owning organization's UUID.
        filename: The original filename, used only for readability in the key.

    Returns:
        A storage key of the form `{org_id}/{uuid}_{filename}`.
    """
    safe_filename = filename.replace("/", "_")
    return f"{organization_id}/{uuid.uuid4()}_{safe_filename}"


def upload_document_bytes(storage_key: str, data: bytes, content_type: str) -> None:
    """Upload raw document bytes to the default bucket.

    Args:
        storage_key: The object key to store the file under.
        data: The raw file bytes.
        content_type: The MIME type of the file.

    Raises:
        ServiceUnavailableError: If the upload to MinIO fails.
    """
    settings = get_settings()
    client = get_minio_client()
    try:
        client.put_object(
            settings.minio_bucket_name,
            storage_key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info("Uploaded document to storage_key=%s (%d bytes)", storage_key, len(data))
    except S3Error as exc:
        logger.exception("Failed to upload document to MinIO")
        raise ServiceUnavailableError("Failed to store document") from exc


def download_document_bytes(storage_key: str) -> bytes:
    """Download raw document bytes from the default bucket.

    Args:
        storage_key: The object key to retrieve.

    Returns:
        The raw file bytes.

    Raises:
        ServiceUnavailableError: If the download from MinIO fails.
    """
    settings = get_settings()
    client = get_minio_client()
    response = None
    try:
        response = client.get_object(settings.minio_bucket_name, storage_key)
        return response.read()
    except S3Error as exc:
        logger.exception("Failed to download document from MinIO")
        raise ServiceUnavailableError("Failed to retrieve document") from exc
    finally:
        if response is not None:
            response.close()
            response.release_conn()
