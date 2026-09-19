"""LLM provider contract."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


class LLMError(RuntimeError):
    """Normalized LLM configuration, timeout, request, or response error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] | None = None


class LLMProvider(ABC):
    """Provider interface for one non-streaming completion."""

    @abstractmethod
    async def generate(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        """Generate one assistant response."""
