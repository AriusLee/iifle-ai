"""Pydantic schemas for the Report API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportSectionResponse(BaseModel):
    id: uuid.UUID
    section_key: str
    section_title: str
    content_en: str | None = None
    content_cn: str | None = None
    content_data: dict[str, Any] | None = None
    sort_order: int = 0
    is_ai_generated: bool = True
    last_edited_by: uuid.UUID | None = None
    last_edited_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID | None = None
    company_id: uuid.UUID
    report_type: str
    title: str
    status: str
    language: str
    version: int
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportDetailResponse(ReportResponse):
    sections: list[ReportSectionResponse] = Field(default_factory=list)


class UpdateSectionRequest(BaseModel):
    content_en: str = Field(..., min_length=1, description="English content for the section")
    content_cn: str | None = Field(None, description="Chinese content for the section (optional)")


class ReviewRequest(BaseModel):
    reason: str | None = Field(None, max_length=2000, description="Reason for rejection (optional)")
