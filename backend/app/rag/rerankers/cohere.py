"""Cohere-compatible reranker adapter."""

import logging
from collections.abc import Sequence
from math import isfinite

import httpx

from app.core.config import Settings, get_settings
from app.rag.rerankers.base import BaseReranker, RerankedChunk, RerankerError
from app.rag.retrievers.base import RetrievedChunk

logger = logging.getLogger(__name__)


class CohereReranker(BaseReranker):
    """Call a Cohere-compatible ``/rerank`` endpoint."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    async def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        *,
        top_k: int | None = None,
    ) -> list[RerankedChunk]:
        effective_top_k = top_k if top_k is not None else self.settings.reranker_top_k
        self._validate_input(query, chunks, effective_top_k)
        candidates = list(chunks)
        if not candidates:
            return []

        api_key = self.settings.reranker_api_key.get_secret_value()
        if not api_key:
            error = RerankerError(
                "RERANKER_NOT_CONFIGURED",
                "Reranker API key is not configured",
            )
            return self._fallback_or_raise(error, candidates, effective_top_k)

        payload = {
            "model": self.settings.reranker_model_name,
            "query": query.strip(),
            "documents": [chunk.text for chunk in candidates],
            "top_n": min(effective_top_k, len(candidates)),
            "return_documents": False,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self.settings.reranker_timeout_seconds)
        try:
            response = await client.post(
                f"{self.settings.reranker_base_url.rstrip('/')}/rerank",
                headers=headers,
                json=payload,
            )
            if response.status_code >= 400:
                raise RerankerError(
                    "RERANKER_REQUEST_FAILED",
                    "Reranker provider returned an error",
                )
            reranked = self._parse_response(response.json(), candidates, effective_top_k)
            return reranked
        except httpx.TimeoutException as exc:
            return self._fallback_or_raise(
                RerankerError("RERANKER_TIMEOUT", "Reranker provider request timed out"),
                candidates,
                effective_top_k,
                cause=exc,
            )
        except httpx.HTTPError as exc:
            return self._fallback_or_raise(
                RerankerError("RERANKER_REQUEST_FAILED", "Reranker provider request failed"),
                candidates,
                effective_top_k,
                cause=exc,
            )
        except (RerankerError, ValueError, TypeError, KeyError, IndexError) as exc:
            error = exc if isinstance(exc, RerankerError) else RerankerError(
                "RERANKER_INVALID_RESPONSE",
                "Reranker provider returned an invalid response",
            )
            return self._fallback_or_raise(error, candidates, effective_top_k, cause=exc)
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _validate_input(query: str, chunks: Sequence[RetrievedChunk], top_k: int) -> None:
        if not query.strip():
            raise RerankerError("RERANKER_EMPTY_QUERY", "Reranker query must not be empty")
        if top_k <= 0:
            raise RerankerError("RERANKER_INVALID_TOP_K", "Reranker top_k must be greater than zero")
        if any(not chunk.text.strip() for chunk in chunks):
            raise RerankerError(
                "RERANKER_EMPTY_DOCUMENT",
                "Reranker documents must not be empty",
            )

    @classmethod
    def _parse_response(
        cls,
        body: object,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RerankedChunk]:
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise RerankerError(
                "RERANKER_INVALID_RESPONSE",
                "Reranker provider returned an invalid response",
            )
        results = body["results"]
        reranked: list[RerankedChunk] = []
        seen_indexes: set[int] = set()
        for item in results:
            if not isinstance(item, dict):
                raise RerankerError(
                    "RERANKER_INVALID_RESPONSE",
                    "Reranker result must be an object",
                )
            index = item.get("index")
            score = item.get("relevance_score")
            if (
                not isinstance(index, int)
                or index < 0
                or index >= len(chunks)
                or index in seen_indexes
                or not isinstance(score, (int, float))
                or not isfinite(float(score))
            ):
                raise RerankerError(
                    "RERANKER_INVALID_RESPONSE",
                    "Reranker provider returned invalid result fields",
                )
            seen_indexes.add(index)
            chunk = chunks[index]
            rerank_score = float(score)
            reranked.append(
                RerankedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    score=rerank_score,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    rerank_score=rerank_score,
                    original_score=chunk.score,
                    used_fallback=False,
                )
            )
            if len(reranked) >= top_k:
                break
        return reranked

    def _fallback_or_raise(
        self,
        error: RerankerError,
        chunks: list[RetrievedChunk],
        top_k: int,
        *,
        cause: BaseException | None = None,
    ) -> list[RerankedChunk]:
        if not self.settings.reranker_fallback_enabled:
            if cause is not None and error.__cause__ is None:
                raise error from cause
            raise error
        logger.warning(
            "Reranker unavailable; preserving retrieval order",
            extra={"error_code": error.code},
        )
        return [
            RerankedChunk(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                filename=chunk.filename,
                page_number=chunk.page_number,
                text=chunk.text,
                score=chunk.score,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                rerank_score=None,
                original_score=chunk.score,
                used_fallback=True,
            )
            for chunk in chunks[:top_k]
        ]
