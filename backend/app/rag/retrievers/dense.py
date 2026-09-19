"""Dense vector retrieval."""

from dataclasses import dataclass
from uuid import UUID

from app.rag.embeddings.base import EmbeddingProvider
from app.rag.vectorstores.qdrant import QdrantVectorStore


class RetrievalError(ValueError):
    """Invalid dense-retrieval input."""


@dataclass(frozen=True)
class RetrievedChunk:
    """A vector result normalized into a citation-ready chunk."""

    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    text: str
    score: float
    start_char: int
    end_char: int


class DenseRetriever:
    """Embed a query and retrieve unique top-K chunks from Qdrant."""

    def __init__(self, embedder: EmbeddingProvider, vector_store: QdrantVectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    async def retrieve(
        self,
        knowledge_base_id: UUID,
        query: str,
        *,
        top_k: int = 5,
        score_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            raise RetrievalError("query must not be empty")
        if top_k <= 0:
            raise RetrievalError("top_k must be greater than zero")
        if score_threshold is not None and not -1.0 <= score_threshold <= 1.0:
            raise RetrievalError("score_threshold must be between -1 and 1")

        query_vector = (await self.embedder.embed([query]))[0]
        results = await self.vector_store.search(knowledge_base_id, query_vector, limit=top_k)
        retrieved: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()
        for result in results:
            if score_threshold is not None and result.score < score_threshold:
                continue
            chunk_id = str(result.payload.get("chunk_id", result.point_id))
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)
            retrieved.append(self._normalize(result.payload, chunk_id, result.score))
            if len(retrieved) >= top_k:
                break
        return retrieved

    @staticmethod
    def _normalize(payload: dict[str, object], chunk_id: str, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk_id,
            document_id=str(payload.get("document_id", "")),
            filename=str(payload.get("filename", "")),
            page_number=int(payload.get("page_number", 1)),
            text=str(payload.get("text", "")),
            score=score,
            start_char=int(payload.get("start_char", 0)),
            end_char=int(payload.get("end_char", 0)),
        )
