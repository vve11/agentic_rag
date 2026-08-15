from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchRequest(StrictRequest):
    query: str
    top_k: int = Field(8, ge=1, le=30)
    year_min: int | None = None
    year_max: int | None = None


class QaRequest(StrictRequest):
    question: str
    paper_ids: list[str] | None = None
    resolved_question: str | None = None
    top_k: int = Field(8, ge=1, le=20)


class SectionRequest(StrictRequest):
    paper_id: str
    section_name: str


class DiscoverRequest(StrictRequest):
    topic: str
    max_candidates: int = Field(10, ge=1, le=20)
    sources: list[str] | None = None


class ApprovalPayload(StrictRequest):
    approved: bool
    operation: str
    candidate_ids: list[int] = Field(default_factory=list)
    destination: str
    side_effects: list[str] = Field(default_factory=list)


class CandidateIngestRequest(StrictRequest):
    candidate_ids: list[int] = Field(..., min_length=1, max_length=5)
    force: bool = False
    approval: ApprovalPayload | None = None


McpEnvelope = dict[str, Any]
