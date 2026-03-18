"""
Pydantic response schemas for the assessment API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class TriggerAssessmentRequest(BaseModel):
    stage: str = Field(default="1", description="Stage to trigger scoring for (e.g. '1', '2')")


# ---------------------------------------------------------------------------
# Dimension
# ---------------------------------------------------------------------------

class DimensionScoreResponse(BaseModel):
    dimension_number: int
    dimension_name: str
    score: float | None
    weight: float
    scoring_method: str | None
    calculation_detail: dict[str, Any] | None
    ai_reasoning: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------

class ModuleScoreResponse(BaseModel):
    module_number: int
    module_name: str
    total_score: float | None
    rating: str | None
    weight: float
    dimensions: list[DimensionScoreResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Auto-flag
# ---------------------------------------------------------------------------

class AutoFlagResponse(BaseModel):
    flag_type: str
    severity: str
    description: str
    source_field: str | None
    source_value: str | None
    is_resolved: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

class AssessmentResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    status: str
    overall_score: float | None
    overall_rating: str | None
    enterprise_stage: str | None = Field(None, alias="enterprise_stage_classification")
    capital_readiness: str | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class AssessmentDetailResponse(AssessmentResponse):
    """Full assessment with nested module scores and flags."""
    modules: list[ModuleScoreResponse] = []
    flags: list[AutoFlagResponse] = []
