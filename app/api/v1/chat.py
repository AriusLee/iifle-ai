"""
Chat API endpoints — create conversations, list them, get history,
and stream AI responses via Server-Sent Events.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db, require_role
from app.models.chat import ChatConversation
from app.models.company import Company
from app.models.user import User
from app.schemas.chat import (
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    SendMessageRequest,
)
from app.services.chat.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_company_or_404(company_id: uuid.UUID, db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def _get_conversation_or_404(
    conversation_id: uuid.UUID,
    company_id: uuid.UUID,
    db: AsyncSession,
) -> ChatConversation:
    result = await db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.company_id == company_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat conversation",
)
async def create_conversation(
    company_id: uuid.UUID,
    body: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Create a new AI chat conversation for a company."""
    await _get_company_or_404(company_id, db)

    service = ChatService(db)
    conversation = await service.create_conversation(
        company_id=company_id,
        user_id=current_user.id,
        title=body.title,
    )

    return ConversationResponse(
        id=conversation.id,
        company_id=conversation.company_id,
        title=conversation.title,
        context_type=conversation.context_type.value,
        is_active=conversation.is_active,
        created_at=conversation.created_at,
    )


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="List chat conversations",
)
async def list_conversations(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """List all chat conversations for a company, newest first."""
    await _get_company_or_404(company_id, db)

    service = ChatService(db)
    conversations = await service.list_conversations(company_id, current_user.id)

    return [
        ConversationResponse(
            id=c.id,
            company_id=c.company_id,
            title=c.title,
            context_type=c.context_type.value,
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in conversations
    ]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="Get conversation message history",
)
async def get_messages(
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """Get all messages in a conversation, ordered chronologically."""
    await _get_company_or_404(company_id, db)
    await _get_conversation_or_404(conversation_id, company_id, db)

    service = ChatService(db)
    messages = await service.get_conversation_history(conversation_id)

    return [
        MessageResponse(
            id=m.id,
            role=m.role.value,
            content=m.content,
            metadata=m.metadata_ or {},
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="Send a message and stream AI response (SSE)",
)
async def send_message(
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Send a message to the AI assistant and receive a streaming SSE response.

    Each server-sent event contains a text delta from the AI response.
    The stream ends when the full response is complete.
    """
    await _get_company_or_404(company_id, db)
    await _get_conversation_or_404(conversation_id, company_id, db)

    service = ChatService(db)

    async def event_generator():
        try:
            async for chunk in service.send_message(
                conversation_id=conversation_id,
                user_message=body.content,
                company_id=company_id,
            ):
                yield {"event": "message", "data": chunk}

            # Signal completion
            yield {"event": "done", "data": "[DONE]"}

        except Exception as exc:
            logger.exception(
                "Streaming error for conversation %s: %s",
                conversation_id,
                exc,
            )
            yield {"event": "error", "data": str(exc)}

    return EventSourceResponse(event_generator())
