"""Conservative extraction of explicitly requested memories."""

import re
from dataclasses import dataclass

from app.models.long_term_memory import MemorySource, MemoryType


@dataclass(frozen=True)
class ExtractedMemory:
    """A candidate that still requires a save or confirmation action."""

    content: str
    memory_type: str = MemoryType.FACT
    source: str = MemorySource.EXPLICIT_USER
    confidence: float = 1.0


class ExplicitMemoryExtractor:
    """Extract only lines with an unambiguous remember instruction."""

    _patterns = (
        re.compile(
            r"^\s*(?:please\s+)?remember(?:\s+that)?\s*:?[ \t]+(?P<content>.+?)\s*$",
            re.IGNORECASE,
        ),
        re.compile(r"^\s*(?:请你?|请)??记住(?:我)?\s*[:：,，]?\s*(?P<content>.+?)\s*$"),
    )

    def extract(self, text: str) -> list[ExtractedMemory]:
        """Return candidates without persisting anything."""

        candidates: list[ExtractedMemory] = []
        for line in text.splitlines():
            content = self._match(line)
            if content:
                candidates.append(ExtractedMemory(content=content))
        return candidates

    def _match(self, line: str) -> str | None:
        for pattern in self._patterns:
            match = pattern.match(line)
            if match:
                content = match.group("content").strip()
                if content:
                    return content
        return None
