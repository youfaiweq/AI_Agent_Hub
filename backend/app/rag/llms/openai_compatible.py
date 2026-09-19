"""OpenAI-compatible chat-completions provider."""

from collections.abc import Sequence

import httpx

from app.core.config import Settings, get_settings
from app.rag.llms.base import LLMError, LLMMessage, LLMProvider, LLMResponse


class OpenAICompatibleLLMProvider(LLMProvider):
    """Call a provider exposing the `/chat/completions` contract."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client

    async def generate(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        api_key = self.settings.llm_api_key.get_secret_value()
        if not api_key:
            raise LLMError("LLM_NOT_CONFIGURED", "LLM API key is not configured")
        if not messages:
            raise LLMError("LLM_EMPTY_PROMPT", "LLM prompt must contain at least one message")

        payload = {
            "model": self.settings.llm_model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "temperature": self.settings.llm_temperature,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds)
        try:
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            if response.status_code >= 400:
                raise LLMError("LLM_REQUEST_FAILED", "LLM provider returned an error")
            try:
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                model = str(body.get("model", self.settings.llm_model))
                usage = body.get("usage")
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise LLMError("LLM_INVALID_RESPONSE", "LLM provider returned an invalid response") from exc
            if not isinstance(content, str) or not content.strip():
                raise LLMError("LLM_EMPTY_RESPONSE", "LLM provider returned an empty response")
            return LLMResponse(content=content.strip(), model=model, usage=usage)
        except httpx.TimeoutException as exc:
            raise LLMError("LLM_TIMEOUT", "LLM provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError("LLM_REQUEST_FAILED", "LLM provider request failed") from exc
        finally:
            if owns_client:
                await client.aclose()
