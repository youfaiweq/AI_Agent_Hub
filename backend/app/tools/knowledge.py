"""Knowledge-base search tool backed by a Retriever contract."""

from app.agents.state import JSONValue
from app.rag.retrievers.base import Retriever
from app.tools.registry import BaseTool, ToolContext, ToolError


class KnowledgeSearchTool(BaseTool):
    """Search the current knowledge base using an injected retriever."""

    def __init__(self, retriever: Retriever, *, default_top_k: int = 5, max_top_k: int = 20) -> None:
        if default_top_k <= 0 or max_top_k < default_top_k:
            raise ValueError("Knowledge search top-k limits are invalid")
        self.retriever = retriever
        self.default_top_k = default_top_k
        self.max_top_k = max_top_k

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
        try:
            chunks = await self.retriever.retrieve(context.knowledge_base_id, query, top_k=top_k)
        except Exception as exc:
            raise ToolError("KNOWLEDGE_SEARCH_FAILED", "Knowledge search failed") from exc
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
