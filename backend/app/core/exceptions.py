"""Application-wide exception hierarchy.

Domain and service layers should raise these exceptions instead of generic
`Exception` or framework-specific errors, keeping the core business logic
decoupled from FastAPI/HTTP concerns. The API layer translates these into
appropriate HTTP responses (see `app.core.error_handlers`).
"""


class EnterpriseGPTError(Exception):
    """Base class for all application-specific errors."""

    def __init__(self, message: str) -> None:
        """Initialize the error.

        Args:
            message: Human-readable description of the error.
        """
        self.message = message
        super().__init__(message)


class NotFoundError(EnterpriseGPTError):
    """Raised when a requested resource does not exist."""


class ValidationError(EnterpriseGPTError):
    """Raised when input fails domain-level validation rules."""


class ServiceUnavailableError(EnterpriseGPTError):
    """Raised when a downstream dependency (DB, cache, storage) is unreachable."""


class ConflictError(EnterpriseGPTError):
    """Raised when an operation conflicts with the current state of a resource."""
