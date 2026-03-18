"""Pydantic schemas for the Chat API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    title: str | None = Field(None, max_length=500, description="Optional conversation title")


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000, description="The user message content")


class ConversationResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID | None
    title: str | None
    context_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}
