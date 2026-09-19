"""Unit tests for the F4-T3 read-only tool contracts."""

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.tools.calculator import CalculatorTool
from app.tools.knowledge import KnowledgeSearchTool
from app.tools.registry import ToolContext, ToolError
from app.tools.sql import SqlQueryTool
from app.tools.web_search import (
    TavilyWebSearchProvider,
    WebSearchProvider,
    WebSearchProviderError,
    WebSearchResult,
    WebSearchTool,
)


def tool_context():
    return ToolContext(uuid4(), uuid4(), uuid4(), uuid4(), {})


@pytest.mark.asyncio
async def test_calculator_uses_ast_allowlist() -> None:
    tool = CalculatorTool()

    result = await tool.execute({"expression": "(2 + 3) * 4 ** 2"}, tool_context())

    assert result["result"] == 80
    with pytest.raises(ToolError) as error_info:
        await tool.execute({"expression": "__import__('os').getcwd()"}, tool_context())
    assert error_info.value.code == "CALCULATOR_INVALID_EXPRESSION"


class FakeRetriever:
    async def retrieve(self, knowledge_base_id, query, *, top_k=5, score_threshold=None):
        return [
            type(
                "Chunk",
                (),
                {
                    "chunk_id": "chunk-1",
                    "document_id": "document-1",
                    "filename": "guide.md",
                    "page_number": 1,
                    "text": query,
                    "score": 0.9,
                },
            )()
        ][:top_k]


@pytest.mark.asyncio
async def test_knowledge_search_requires_context_and_returns_sources() -> None:
    tool = KnowledgeSearchTool(FakeRetriever())
    result = await tool.execute({"query": "setup"}, tool_context())

    assert result["results"][0]["chunk_id"] == "chunk-1"
    with pytest.raises(ToolError) as error_info:
        await tool.execute({"query": "setup"}, ToolContext(None, None, None, None, {}))
    assert error_info.value.code == "KNOWLEDGE_BASE_REQUIRED"


class FakeMappings:
    def all(self):
        return [{"id": 1, "name": "AgentHub"}]


class FakeResult:
    def mappings(self):
        return FakeMappings()


class FakeSession:
    async def execute(self, statement):
        self.statement = str(statement)
        return FakeResult()


@pytest.mark.asyncio
async def test_sql_tool_allows_whitelisted_select_and_limits_rows() -> None:
    session = FakeSession()
    tool = SqlQueryTool(session, allowed_tables={"users"}, row_limit=10)

    result = await tool.execute({"query": "SELECT id, name FROM users"}, tool_context())

    assert result["rows"] == [{"id": 1, "name": "AgentHub"}]
    assert "LIMIT 10" in session.statement.upper()
    with pytest.raises(ToolError) as error_info:
        await tool.execute({"query": "SELECT * FROM secrets"}, tool_context())
    assert error_info.value.code == "SQL_TABLE_NOT_ALLOWED"
    with pytest.raises(ToolError) as error_info:
        await tool.execute({"query": "DROP TABLE users"}, tool_context())
    assert error_info.value.code == "SQL_FORBIDDEN"


class FakeWebProvider(WebSearchProvider):
    async def search(self, query: str, *, max_results: int):
        return [WebSearchResult("Result", "https://example.test", query)][:max_results]


@pytest.mark.asyncio
async def test_web_search_tool_uses_provider_contract() -> None:
    tool = WebSearchTool(FakeWebProvider())

    result = await tool.execute({"query": "AgentHub"}, tool_context())

    assert result["results"][0]["url"] == "https://example.test"


@pytest.mark.asyncio
async def test_tavily_provider_normalizes_http_response_and_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert json.loads(request.content)["query"] == "AgentHub"
        return httpx.Response(
            200,
            json={"results": [{"title": "AgentHub", "url": "https://example.test", "content": "Docs"}]},
        )

    settings = Settings(
        web_search_api_key=SecretStr("test-key"),
        web_search_base_url="https://search.example.test",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await TavilyWebSearchProvider(settings, client=client).search(
            "AgentHub", max_results=1
        )
    assert results[0].title == "AgentHub"

    def timeout_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("test timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
        provider = TavilyWebSearchProvider(settings, client=client)
        with pytest.raises(WebSearchProviderError) as error_info:
            await provider.search("AgentHub", max_results=1)
    assert error_info.value.code == "WEB_SEARCH_TIMEOUT"
