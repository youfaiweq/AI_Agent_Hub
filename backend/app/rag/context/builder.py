"""Token-budgeted context construction."""

from dataclasses import dataclass
from math import ceil

from app.rag.retrievers.dense import RetrievedChunk


@dataclass(frozen=True)
class Citation:
    """Source metadata exposed alongside a context block."""

    citation_id: int
    document_id: str
    filename: str
    chunk_id: str
    page_number: int
    snippet: str


@dataclass(frozen=True)
class ContextResult:
    """Final context text and the citations used to build it."""

    text: str
    citations: tuple[Citation, ...]
    used_tokens: int
    truncated: bool


class ContextBuilder:
    """Build a bounded context using a transparent character/token estimate."""

    def __init__(self, token_budget: int = 2000, chars_per_token: int = 4) -> None:
        if token_budget <= 0:
            raise ValueError("token_budget must be greater than zero")
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be greater than zero")
        self.token_budget = token_budget
        self.chars_per_token = chars_per_token

    def build(self, chunks: list[RetrievedChunk]) -> ContextResult:
        entries: list[str] = []
        citations: list[Citation] = []
        used_tokens = 0
        truncated = False

        for chunk in chunks:
            if not chunk.text.strip():
                continue
            citation_id = len(citations) + 1
            header = f"[{citation_id}] {chunk.filename} (page {chunk.page_number})"
            separator_tokens = 1 if entries else 0
            header_tokens = self.estimate_tokens(header) + separator_tokens
            available_tokens = self.token_budget - used_tokens - header_tokens
            if available_tokens <= 0:
                truncated = True
                break
            max_chars = available_tokens * self.chars_per_token
            snippet = chunk.text.strip()
            if len(snippet) > max_chars:
                snippet = snippet[:max_chars].rstrip()
                truncated = True
            entry = f"{header}\n{snippet}"
            entry_tokens = self.estimate_tokens(entry) + separator_tokens
            if used_tokens + entry_tokens > self.token_budget:
                truncated = True
                break
            entries.append(entry)
            used_tokens += entry_tokens
            citations.append(
                Citation(
                    citation_id=citation_id,
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    snippet=snippet,
                )
            )

        return ContextResult(
            text="\n\n".join(entries),
            citations=tuple(citations),
            used_tokens=used_tokens,
            truncated=truncated,
        )

    def estimate_tokens(self, text: str) -> int:
        return max(1, ceil(len(text) / self.chars_per_token))
