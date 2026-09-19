"""Unit tests for the configured reranker adapter."""

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.rag.rerankers import BaseReranker, CohereReranker, RerankerError, create_reranker
from app.rag.retrievers.base import RetrievedChunk


def make_chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=str(uuid4()),
        filename=f"{chunk_id}.md",
        page_number=1,
        text=f"candidate text {chunk_id}",
        score=score,
        start_char=0,
        end_char=20,
    )


def configured_settings(**kwargs: object) -> Settings:
    return Settings(
        reranker_api_key=SecretStr("test-key"),
        reranker_base_url="https://example.test/v2",
        reranker_model_name="test-reranker",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_cohere_reranker_sends_documents_and_parses_scores() -> None:
    chunks = [make_chunk("first", 0.2), make_chunk("second", 0.8)]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/rerank"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": "test-reranker",
            "query": "product question",
            "documents": [chunk.text for chunk in chunks],
            "top_n": 1,
            "return_documents": False,
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.12},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        reranker = CohereReranker(configured_settings(), client=client)
        results = await reranker.rerank("product question", chunks, top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "second"
    assert results[0].score == 0.91
    assert results[0].rerank_score == 0.91
    assert results[0].original_score == 0.8
    assert results[0].used_fallback is False


@pytest.mark.asyncio
async def test_cohere_reranker_normalizes_timeout_and_http_errors() -> None:
    chunks = [make_chunk("first", 0.2)]

    def timeout_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("test timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        reranker = CohereReranker(configured_settings(), client=client)
        with pytest.raises(RerankerError) as error_info:
            await reranker.rerank("question", chunks)
        assert error_info.value.code == "RERANKER_TIMEOUT"

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503))
    ) as client:
        reranker = CohereReranker(configured_settings(), client=client)
        with pytest.raises(RerankerError) as error_info:
            await reranker.rerank("question", chunks)
        assert error_info.value.code == "RERANKER_REQUEST_FAILED"


@pytest.mark.asyncio
async def test_cohere_reranker_explicitly_falls_back_without_fake_scores() -> None:
    chunks = [make_chunk("first", 0.2), make_chunk("second", 0.8)]
    settings = configured_settings(reranker_fallback_enabled=True)
    reranker = CohereReranker(settings)

    results = await reranker.rerank("question", chunks, top_k=1)

    assert [result.chunk_id for result in results] == ["first"]
    assert results[0].score == 0.2
    assert results[0].original_score == 0.2
    assert results[0].rerank_score is None
    assert results[0].used_fallback is True


@pytest.mark.asyncio
async def test_cohere_reranker_timeout_uses_explicit_fallback() -> None:
    chunks = [make_chunk("first", 0.2)]

    def timeout_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("test timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        reranker = CohereReranker(
            configured_settings(reranker_fallback_enabled=True),
            client=client,
        )
        results = await reranker.rerank("question", chunks)

    assert results[0].used_fallback is True
    assert results[0].rerank_score is None


@pytest.mark.asyncio
async def test_cohere_reranker_rejects_invalid_response_and_input() -> None:
    chunks = [make_chunk("first", 0.2)]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": [{"index": 3}]}))
    ) as client:
        reranker = CohereReranker(configured_settings(), client=client)
        with pytest.raises(RerankerError) as error_info:
            await reranker.rerank("question", chunks)
        assert error_info.value.code == "RERANKER_INVALID_RESPONSE"

    reranker = CohereReranker(configured_settings())
    with pytest.raises(RerankerError) as error_info:
        await reranker.rerank("", chunks)
    assert error_info.value.code == "RERANKER_EMPTY_QUERY"


def test_reranker_factory_is_provider_configured() -> None:
    reranker = create_reranker(configured_settings())
    assert isinstance(reranker, BaseReranker)

    with pytest.raises(RerankerError) as error_info:
        create_reranker(Settings(reranker_provider="unsupported"))
    assert error_info.value.code == "RERANKER_PROVIDER_UNSUPPORTED"
