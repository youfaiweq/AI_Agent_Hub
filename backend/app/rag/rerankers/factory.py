"""Reranker provider construction."""

from app.core.config import Settings, get_settings
from app.rag.rerankers.base import BaseReranker, RerankerError
from app.rag.rerankers.cohere import CohereReranker


def create_reranker(settings: Settings | None = None) -> BaseReranker:
    """Build the configured reranker adapter without binding callers to a vendor."""

    resolved = settings or get_settings()
    if resolved.reranker_provider == "cohere":
        return CohereReranker(resolved)
    raise RerankerError(
        "RERANKER_PROVIDER_UNSUPPORTED",
        f"Unsupported reranker provider: {resolved.reranker_provider}",
    )
