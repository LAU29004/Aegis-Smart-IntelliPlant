"""
app/schemas/query_schemas.py

WHY THIS FILE EXISTS
---------------------
Defines the Pydantic models for `POST /query` - the ONE place request
validation and response serialization for the query pipeline happens.
These are deliberately SEPARATE types from the internal dataclasses
in `app/services/schemas.py`, `app/citations/schemas.py`, and
`app/confidence/schemas.py`: those are the pipeline's internal,
framework-agnostic working data; these are the FastAPI/OpenAPI-facing
contract external clients (including a future Agent Orchestrator)
actually see and depend on. Keeping them distinct means the internal
pipeline's data shapes can evolve freely (e.g. adding an internal
debugging field to `ConfidenceResult`) without silently changing the
public API contract - only `api/`'s route handlers, which explicitly
convert one to the other, need to know about both.

`QueryResponse`'s fields map 1:1 to the spec's required JSON Response
fields: answer, citations, confidence, followups, related_documents,
processing_time.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ConfidenceBand, DocumentType


class QueryRequest(BaseModel):
    """
    Request body for `POST /query`.

    WHY `query` has `min_length=1` AND a `field_validator` stripping
    whitespace: `min_length=1` alone would still accept a string of
    pure whitespace (e.g. `"   "`), which is not a real query - the
    validator normalizes and re-checks after stripping, so an
    all-whitespace request is rejected with a clear 422 rather than
    being silently passed down into `RetrievalService.retrieve(...)`,
    which would then embed a meaningless empty-ish string.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "How often should I replace the pump seal on PUMP-101?",
                "session_id": "sess-a1b2c3",
                "department": "Maintenance",
                "equipment_id": "PUMP-101",
            }
        }
    )

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to ask the RAG copilot.",
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Groups this query with prior turns for multi-turn "
        "conversational context. Omit for a stateless, one-off query.",
    )
    department: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Restrict retrieval to chunks tagged with this department.",
    )
    equipment_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Restrict retrieval to chunks tagged with this equipment id.",
    )
    document_type: Optional[DocumentType] = Field(
        default=None,
        description="Restrict retrieval to chunks from this document type.",
    )

    @field_validator("query")
    @classmethod
    def _query_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be empty or whitespace-only")
        return stripped


class CitationResponse(BaseModel):
    """One inline-cited source in the answer, per the spec's `citations` field."""

    model_config = ConfigDict(from_attributes=True)

    number: int = Field(..., description="The [n] marker number this citation corresponds to.")
    chunk_id: str
    document_name: str
    page_number: Optional[int] = None
    department: Optional[str] = None
    equipment_id: Optional[str] = None
    relevance_score: float = Field(
        ..., description="Raw cross-encoder relevance score for this source."
    )


class RelatedDocumentResponse(BaseModel):
    """One document retrieval surfaced as relevant, per the spec's `related_documents` field."""

    model_config = ConfigDict(from_attributes=True)

    document_name: str
    department: Optional[str] = None
    equipment_id: Optional[str] = None
    page_numbers: List[int] = Field(default_factory=list)
    chunk_count: int = 0


class ConfidenceResponse(BaseModel):
    """
    The spec's `confidence` field: a 0-100 score plus its Green/Amber/
    Red band.

    WHY `band` is serialized as the enum's plain string value (via
    `use_enum_values` on the internal `ConfidenceBand`, applied at
    conversion time in `api/`) rather than the Python enum object
    directly: API consumers should see `"green"`, not
    `"ConfidenceBand.GREEN"` - the value FastAPI's JSON encoder would
    otherwise produce from a raw enum member's `repr`.
    """

    score: float = Field(..., ge=0.0, le=100.0)
    band: ConfidenceBand


class QueryResponse(BaseModel):
    """
    Response body for `POST /query` - matches the spec's required
    JSON Response fields exactly: answer, citations, confidence,
    followups, related_documents, processing_time.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Replace the pump seal every 6 months to prevent leakage [1].",
                "citations": [
                    {
                        "number": 1,
                        "chunk_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "document_name": "Pump Manual.pdf",
                        "page_number": 3,
                        "department": "Maintenance",
                        "equipment_id": "PUMP-101",
                        "relevance_score": 4.12,
                    }
                ],
                "confidence": {"score": 91.4, "band": "green"},
                "followups": [
                    "How often should bearings be lubricated?",
                    "What tools are needed for seal replacement?",
                    "Who is certified to perform this maintenance?",
                ],
                "related_documents": [
                    {
                        "document_name": "Pump Manual.pdf",
                        "department": "Maintenance",
                        "equipment_id": "PUMP-101",
                        "page_numbers": [3, 4],
                        "chunk_count": 2,
                    }
                ],
                "processing_time": 1.842,
            }
        }
    )

    answer: str
    citations: List[CitationResponse] = Field(default_factory=list)
    confidence: ConfidenceResponse
    followups: List[str] = Field(default_factory=list)
    related_documents: List[RelatedDocumentResponse] = Field(default_factory=list)
    processing_time: float = Field(
        ..., description="Total pipeline wall-clock time, in seconds."
    )
