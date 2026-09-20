"""Bounded short-term conversation context selection."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class MemoryMessage:
    """Provider-neutral message data used by the memory window."""

    role: str
    content: str


@dataclass(frozen=True)
class MemoryWindow:
    """Selected messages and the transparent token estimate for the window."""

    messages: tuple[MemoryMessage, ...]
    used_tokens: int


class ShortTermMemory:
    """Select the newest contiguous message window within configured bounds.

    The token estimate intentionally uses the same transparent character-based
    approach as the existing RAG ContextBuilder. The current request is kept
    outside this policy by callers so it is never silently truncated.
    """

    def __init__(self, max_messages: int, token_budget: int, chars_per_token: int = 4) -> None:
        if max_messages <= 0:
            raise ValueError("max_messages must be greater than zero")
        if token_budget <= 0:
            raise ValueError("token_budget must be greater than zero")
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be greater than zero")
        self.max_messages = max_messages
        self.token_budget = token_budget
        self.chars_per_token = chars_per_token

    def select(self, messages: Sequence[MemoryMessage]) -> MemoryWindow:
        """Return a chronological suffix bounded by count and estimated tokens."""

        selected: list[MemoryMessage] = []
        used_tokens = 0
        for message in reversed(messages[-self.max_messages :]):
            message_tokens = self.estimate_tokens(message.content)
            if selected and used_tokens + message_tokens > self.token_budget:
                break
            if not selected and message_tokens > self.token_budget:
                message = MemoryMessage(
                    role=message.role,
                    content=self._truncate(message.content, self.token_budget),
                )
                message_tokens = self.token_budget
            selected.append(message)
            used_tokens += message_tokens

        selected.reverse()
        return MemoryWindow(messages=tuple(selected), used_tokens=used_tokens)

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens without requiring a provider-specific tokenizer."""

        return max(1, ceil(len(text) / self.chars_per_token))

    def _truncate(self, text: str, token_budget: int) -> str:
        return text[: token_budget * self.chars_per_token]
