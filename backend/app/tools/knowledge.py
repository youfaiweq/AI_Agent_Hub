"""Knowledge-base search tool backed by a Retriever contract."""

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.agents.state import JSONValue
from app.observability import ObservabilityAdapter, ObservationEvent, new_trace_id, safe_emit
from app.rag.retrievers.base import Retriever
from app.tools.registry import BaseTool, ToolContext, ToolError


class KnowledgeSearchTool(BaseTool):
    """Search the current knowledge base using an injected retriever."""

    def __init__(
        self,
        retriever: Retriever,
        *,
        default_top_k: int = 5,
        max_top_k: int = 20,
        observability: ObservabilityAdapter | None = None,
    ) -> None:
        if default_top_k <= 0 or max_top_k < default_top_k:
            raise ValueError("Knowledge search top-k limits are invalid")
        self.retriever = retriever
        self.default_top_k = default_top_k
        self.max_top_k = max_top_k
        self.observability = observability

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "Search the current knowledge base and return traceable source chunks."

    @property
    def input_schema(self) -> dict[str, JSONValue]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer"},
            },
            "required": ["query"],
        }

    async def execute(
        self,
        arguments: dict[str, JSONValue],
        context: ToolContext,
    ) -> JSONValue:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ToolError("KNOWLEDGE_SEARCH_INVALID_INPUT", "Knowledge search query is required")
        if context.knowledge_base_id is None:
            raise ToolError("KNOWLEDGE_BASE_REQUIRED", "Knowledge search requires a knowledge base")
        top_k = arguments.get("top_k", self.default_top_k)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= self.max_top_k:
            raise ToolError("KNOWLEDGE_SEARCH_INVALID_INPUT", "Knowledge search top_k is invalid")
        started = perf_counter()
        try:
            chunks = await self.retriever.retrieve(context.knowledge_base_id, query, top_k=top_k)
        except Exception as exc:
            await self._emit_retrieval(context, top_k, started, "failed", "KNOWLEDGE_SEARCH_FAILED")
            raise ToolError("KNOWLEDGE_SEARCH_FAILED", "Knowledge search failed") from exc
        await self._emit_retrieval(context, top_k, started, "completed", None, len(chunks))
        return {
            "query": query.strip(),
            "results": [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "filename": chunk.filename,
                    "page_number": chunk.page_number,
                    "snippet": chunk.text,
                    "score": chunk.score,
                }
                for chunk in chunks
            ],
        }

    async def _emit_retrieval(
        self,
        context: ToolContext,
        top_k: int,
        started: float,
        status: str,
        error_code: str | None,
        result_count: int = 0,
    ) -> None:
        if self.observability is None:
            return
        trace_id = context.metadata.get("trace_id")
        await safe_emit(
            self.observability,
            ObservationEvent(
                kind="retrieval",
                name="knowledge_search",
                trace_id=trace_id if isinstance(trace_id, str) else new_trace_id(),
                observation_id=uuid4().hex,
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                latency_ms=round((perf_counter() - started) * 1000, 2),
                status=status,
                error_code=error_code,
                metadata={"top_k": top_k, "result_count": result_count},
            ),
        )
