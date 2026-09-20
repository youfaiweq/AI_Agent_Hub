"""Deterministic retrieval and answer evaluation metrics."""

import re
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseEvaluation:
    """Metrics for one expected-source question."""

    retrieved_chunk_ids: tuple[str, ...]
    retrieval_hit: bool
    retrieval_recall: float
    citation_correctness: float
    answer_relevance: float | None = None
    faithfulness: float | None = None


def evaluate_case(
    expected_chunk_ids: Sequence[str],
    retrieved_chunk_ids: Sequence[str],
    *,
    expected_answer: str | None = None,
    answer: str | None = None,
    context_text: str = "",
    citation_chunk_ids: Sequence[str] | None = None,
) -> CaseEvaluation:
    """Score retrieval, citations, answer relevance, and grounding deterministically."""

    expected = {chunk_id for chunk_id in expected_chunk_ids if chunk_id}
    retrieved = tuple(dict.fromkeys(chunk_id for chunk_id in retrieved_chunk_ids if chunk_id))
    retrieved_set = set(retrieved)
    correct = len(expected & retrieved_set)
    retrieval_recall = correct / len(expected) if expected else 0.0
    citations = tuple(dict.fromkeys(citation_chunk_ids or retrieved))
    citation_set = set(citations)
    citation_correctness = len(expected & citation_set) / len(citation_set) if citation_set else 0.0
    return CaseEvaluation(
        retrieved_chunk_ids=retrieved,
        retrieval_hit=bool(expected & retrieved_set),
        retrieval_recall=retrieval_recall,
        citation_correctness=citation_correctness,
        answer_relevance=_answer_relevance(expected_answer, answer),
        faithfulness=_faithfulness(answer, context_text),
    )


def summarize_cases(cases: Sequence[CaseEvaluation]) -> tuple[float, float]:
    """Return binary retrieval recall and mean citation correctness."""

    if not cases:
        return 0.0, 0.0
    retrieval_recall = sum(case.retrieval_recall for case in cases) / len(cases)
    citation_correctness = sum(case.citation_correctness for case in cases) / len(cases)
    return retrieval_recall, citation_correctness


def summarize_answer_metrics(
    cases: Sequence[CaseEvaluation],
) -> tuple[float | None, float | None, int, int]:
    """Return means only over cases that provide the relevant answer inputs."""

    relevance = [case.answer_relevance for case in cases if case.answer_relevance is not None]
    faithfulness = [case.faithfulness for case in cases if case.faithfulness is not None]
    return (
        sum(relevance) / len(relevance) if relevance else None,
        sum(faithfulness) / len(faithfulness) if faithfulness else None,
        len(relevance),
        len(faithfulness),
    )


def _answer_relevance(expected_answer: str | None, answer: str | None) -> float | None:
    if not expected_answer or not answer:
        return None
    expected = _tokens(expected_answer)
    actual = _tokens(answer)
    if not expected or not actual:
        return 0.0
    overlap = len(expected & actual)
    precision = overlap / len(actual)
    recall = overlap / len(expected)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _faithfulness(answer: str | None, context_text: str) -> float | None:
    if not answer or not context_text:
        return None
    actual = _tokens(answer)
    context = _tokens(context_text)
    if not actual:
        return 0.0
    return len(actual & context) / len(actual)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))
