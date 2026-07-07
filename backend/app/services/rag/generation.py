"""LLM answer generation via Gemini, for both single-shot and streaming use.

Isolated behind a small class — same pattern as `EmbeddingService` and
`QueryRewriter` — so the RAG graph and its tests never touch the
`google.generativeai` SDK directly.
"""

from collections.abc import Iterator

import google.generativeai as genai

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_INSTRUCTION = (
    "You are EnterpriseGPT, an assistant that answers questions using ONLY the provided "
    "document context. If the context doesn't contain the answer, say so plainly rather "
    "than guessing. Be concise and cite specific facts from the context where relevant."
)


class GenerationService:
    """Generates RAG answers using a Gemini chat model."""

    def __init__(self) -> None:
        """Initialize the service, configuring the Google AI SDK and model."""
        settings = get_settings()
        if settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)
        self._model = genai.GenerativeModel(
            settings.generation_model, system_instruction=SYSTEM_INSTRUCTION
        )

    def generate(self, prompt: str) -> str:
        """Generate a complete answer for a prompt in one call.

        Args:
            prompt: The full prompt, including context, history, and the question.

        Returns:
            The generated answer text.

        Raises:
            ServiceUnavailableError: If the generation API call fails.
        """
        try:
            response = self._model.generate_content(prompt)
            return (response.text or "").strip()
        except Exception as exc:
            logger.exception("Answer generation failed")
            raise ServiceUnavailableError("Failed to generate an answer") from exc

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Generate an answer, yielding text incrementally as it's produced.

        Args:
            prompt: The full prompt, including context, history, and the question.

        Yields:
            Successive text chunks as they're generated.

        Raises:
            ServiceUnavailableError: If the generation API call fails.
        """
        try:
            response = self._model.generate_content(prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.exception("Streaming answer generation failed")
            raise ServiceUnavailableError("Failed to generate an answer") from exc
