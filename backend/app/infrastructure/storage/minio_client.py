"""MinIO (S3-compatible) object storage client.

Owns the connection to MinIO and ensures the default document bucket
exists. Phase 3 (Document Ingestion) will add upload/download service
methods on top of this client; Phase 1 only wires the connection and
exposes a health check.
"""

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_minio_client: Minio | None = None


def get_minio_client() -> Minio:
    """Return the singleton MinIO client, creating it if needed.

    Returns:
        A configured `Minio` client instance.
    """
    global _minio_client
    if _minio_client is None:
        settings = get_settings()
        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        logger.info("MinIO client created for endpoint=%s", settings.minio_endpoint)
    return _minio_client


def ensure_default_bucket() -> None:
    """Create the default document bucket if it does not already exist.

    Safe to call multiple times; this is idempotent and typically invoked
    once during application startup.
    """
    settings = get_settings()
    client = get_minio_client()
    try:
        if not client.bucket_exists(settings.minio_bucket_name):
            client.make_bucket(settings.minio_bucket_name)
            logger.info("Created MinIO bucket: %s", settings.minio_bucket_name)
    except S3Error:
        logger.exception("Failed to ensure MinIO bucket exists")
        raise


def check_minio_connection() -> bool:
    """Verify MinIO connectivity for health checks.

    Returns:
        True if the bucket existence check succeeds, False otherwise.
    """
    try:
        settings = get_settings()
        client = get_minio_client()
        client.bucket_exists(settings.minio_bucket_name)
        return True
    except Exception:
        logger.exception("MinIO health check failed")
        return False
