"""Web search Tool and provider adapter contracts."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from app.agents.state import JSONValue
from app.core.config import Settings, get_settings
from app.tools.registry import BaseTool, ToolContext, ToolError


class WebSearchProviderError(RuntimeError):
    """Normalized Web Search provider error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


class WebSearchProvider(ABC):
    """Provider adapter contract independent from the Agent Tool."""

    @abstractmethod
    async def search(self, query: str, *, max_results: int) -> Sequence[WebSearchResult]:
        """Return bounded web search results."""


class TavilyWebSearchProvider(WebSearchProvider):
    """Call the Tavily-compatible search API."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    async def search(self, query: str, *, max_results: int) -> Sequence[WebSearchResult]:
        api_key = self.settings.web_search_api_key.get_secret_value()
        if not api_key:
            raise WebSearchProviderError("WEB_SEARCH_NOT_CONFIGURED", "Web Search API key is not configured")
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self.settings.web_search_timeout_seconds)
        try:
            response = await client.post(
                f"{self.settings.web_search_base_url.rstrip('/')}/search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "query": query,
                    "max_results": max_results,
                    "include_answer": False,
                    "search_depth": "basic",
                },
            )
            if response.status_code >= 400:
                raise WebSearchProviderError("WEB_SEARCH_REQUEST_FAILED", "Web Search provider returned an error")
            body = response.json()
            raw_results = body.get("results") if isinstance(body, dict) else None
            if not isinstance(raw_results, list):
                raise WebSearchProviderError("WEB_SEARCH_INVALID_RESPONSE", "Web Search provider returned an invalid response")
            results: list[WebSearchResult] = []
            for item in raw_results[:max_results]:
                if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                    raise WebSearchProviderError("WEB_SEARCH_INVALID_RESPONSE", "Web Search result is invalid")
                results.append(
                    WebSearchResult(
                        title=str(item.get("title", "")),
                        url=item["url"],
                        snippet=str(item.get("content", "")),
                    )
                )
            return results
        except httpx.TimeoutException as exc:
            raise WebSearchProviderError("WEB_SEARCH_TIMEOUT", "Web Search provider timed out") from exc
        except httpx.HTTPError as exc:
            raise WebSearchProviderError("WEB_SEARCH_REQUEST_FAILED", "Web Search provider request failed") from exc
        finally:
            if owns_client:
                await client.aclose()


def create_web_search_provider(settings: Settings | None = None) -> WebSearchProvider:
    """Build the configured Web Search provider adapter."""

    resolved = settings or get_settings()
    if resolved.web_search_provider == "tavily":
        return TavilyWebSearchProvider(resolved)
    raise WebSearchProviderError(
        "WEB_SEARCH_PROVIDER_UNSUPPORTED",
        f"Unsupported Web Search provider: {resolved.web_search_provider}",
    )


class WebSearchTool(BaseTool):
    """Use an injected Web Search provider through the common Tool contract."""

    def __init__(self, provider: WebSearchProvider, *, default_max_results: int = 5, max_results: int = 10) -> None:
        if default_max_results <= 0 or max_results < default_max_results:
            raise ValueError("Web Search result limits are invalid")
        self.provider = provider
        self.default_max_results = default_max_results
        self.max_results = max_results

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web through the configured Web Search provider."

    @property
    def input_schema(self) -> dict[str, JSONValue]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
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
            raise ToolError("WEB_SEARCH_INVALID_INPUT", "Web Search query is required")
        max_results = arguments.get("max_results", self.default_max_results)
        if not isinstance(max_results, int) or isinstance(max_results, bool) or not 1 <= max_results <= self.max_results:
            raise ToolError("WEB_SEARCH_INVALID_INPUT", "Web Search max_results is invalid")
        try:
            results = await self.provider.search(query.strip(), max_results=max_results)
        except WebSearchProviderError as exc:
            raise ToolError(exc.code, exc.message) from exc
        return {
            "query": query.strip(),
            "results": [
                {"title": item.title, "url": item.url, "snippet": item.snippet}
                for item in results
            ],
        }
