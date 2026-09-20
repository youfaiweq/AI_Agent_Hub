"""Retrieval debug and evaluation API schemas."""

from typing import Literal

from pydantic import BaseModel, Field

RetrievalMode = Literal["dense", "sparse", "hybrid", "rerank"]


class RetrievalDebugRequest(BaseModel):
    """Parameters for one retrieval inspection request."""

    query: str = Field(min_length=1, max_length=20000)
    mode: RetrievalMode = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50)
    candidate_k: int = Field(default=20, ge=1, le=200)


class RetrievalDebugItem(BaseModel):
    """One traceable result row returned by retrieval debug."""

    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    snippet: str
    dense_score: float | None = None
    sparse_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    final_rank: int


class RetrievalDebugResponse(BaseModel):
    """Results and metadata for one retrieval debug request."""

    query: str
    mode: RetrievalMode
    candidate_k: int
    items: list[RetrievalDebugItem]


class EvaluationCase(BaseModel):
    """One manually curated question and its expected source chunks."""

    case_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=20000)
    expected_chunk_ids: list[str] = Field(min_length=1, max_length=50)
    expected_answer: str | None = Field(default=None, max_length=20000)
    answer: str | None = Field(default=None, max_length=20000)
    citation_chunk_ids: list[str] = Field(default_factory=list, max_length=50)


class EvaluationDataset(BaseModel):
    """Versioned, request-scoped evaluation dataset."""

    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    cases: list[EvaluationCase] = Field(min_length=1, max_length=100)


class RetrievalEvaluationRequest(BaseModel):
    """Parameters for evaluating one retrieval mode against a dataset."""

    dataset: EvaluationDataset
    mode: RetrievalMode = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50)
    candidate_k: int = Field(default=20, ge=1, le=200)


class EvaluationCaseResult(BaseModel):
    """Per-case retrieval and citation proxy metrics."""

    case_id: str
    question: str
    expected_chunk_ids: list[str]
    retrieved_chunk_ids: list[str]
    retrieval_hit: bool
    retrieval_recall: float
    citation_correctness: float
    answer_relevance: float | None = None
    faithfulness: float | None = None


class EvaluationMetrics(BaseModel):
    """Aggregate initial evaluation metrics."""

    total_cases: int
    retrieval_recall: float
    citation_correctness: float
    answer_relevance: float | None = None
    faithfulness: float | None = None
    answer_scored_cases: int = 0
    faithfulness_scored_cases: int = 0


class RetrievalEvaluationResponse(BaseModel):
    """Evaluation output with aggregate and per-case results."""

    dataset_name: str
    dataset_version: str
    dataset_fingerprint: str
    result_fingerprint: str
    mode: RetrievalMode
    metrics: EvaluationMetrics
    cases: list[EvaluationCaseResult]
