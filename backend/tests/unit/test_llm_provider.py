"""Unit tests for the OpenAI-compatible LLM adapter."""

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.rag.llms.base import LLMError, LLMMessage
from app.rag.llms.openai_compatible import OpenAICompatibleLLMProvider


@pytest.mark.asyncio
async def test_openai_compatible_provider_parses_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"content": " grounded answer "}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleLLMProvider(
            Settings(
                llm_api_key=SecretStr("x"),
                llm_base_url="https://example.test/v1",
                llm_model="test-model",
            ),
            client=client,
        )
        response = await provider.generate([LLMMessage(role="user", content="Question")])

    assert response.content == "grounded answer"
    assert response.model == "test-model"
    assert response.usage == {"prompt_tokens": 3, "completion_tokens": 2}


@pytest.mark.asyncio
async def test_openai_compatible_provider_normalizes_http_timeout_and_empty_errors() -> None:
    def error_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(error_handler)) as client:
        provider = OpenAICompatibleLLMProvider(
            Settings(llm_api_key=SecretStr("x"), llm_base_url="https://example.test/v1"),
            client=client,
        )
        with pytest.raises(LLMError, match="provider returned an error") as error_info:
            await provider.generate([LLMMessage(role="user", content="Question")])
        assert error_info.value.code == "LLM_REQUEST_FAILED"

    def timeout_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("test timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        provider = OpenAICompatibleLLMProvider(
            Settings(llm_api_key=SecretStr("x"), llm_base_url="https://example.test/v1"),
            client=client,
        )
        with pytest.raises(LLMError) as error_info:
            await provider.generate([LLMMessage(role="user", content="Question")])
        assert error_info.value.code == "LLM_TIMEOUT"

    def empty_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(empty_handler)) as client:
        provider = OpenAICompatibleLLMProvider(
            Settings(llm_api_key=SecretStr("x"), llm_base_url="https://example.test/v1"),
            client=client,
        )
        with pytest.raises(LLMError) as error_info:
            await provider.generate([LLMMessage(role="user", content="Question")])
        assert error_info.value.code == "LLM_EMPTY_RESPONSE"
