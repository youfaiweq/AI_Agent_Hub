"""Initial retrieval recall and citation correctness metrics."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CaseEvaluation:
    """Metrics for one expected-source question."""

    retrieved_chunk_ids: tuple[str, ...]
    retrieval_hit: bool
    citation_correctness: float


def evaluate_case(expected_chunk_ids: Sequence[str], retrieved_chunk_ids: Sequence[str]) -> CaseEvaluation:
    """Score source recall and returned-citation precision for one case."""

    expected = {chunk_id for chunk_id in expected_chunk_ids if chunk_id}
    retrieved = tuple(dict.fromkeys(chunk_id for chunk_id in retrieved_chunk_ids if chunk_id))
    retrieved_set = set(retrieved)
    correct = len(expected & retrieved_set)
    citation_correctness = correct / len(retrieved_set) if retrieved_set else 0.0
    return CaseEvaluation(
        retrieved_chunk_ids=retrieved,
        retrieval_hit=bool(expected & retrieved_set),
        citation_correctness=citation_correctness,
    )


def summarize_cases(cases: Sequence[CaseEvaluation]) -> tuple[float, float]:
    """Return binary retrieval recall and mean citation correctness."""

    if not cases:
        return 0.0, 0.0
    retrieval_recall = sum(case.retrieval_hit for case in cases) / len(cases)
    citation_correctness = sum(case.citation_correctness for case in cases) / len(cases)
    return retrieval_recall, citation_correctness
