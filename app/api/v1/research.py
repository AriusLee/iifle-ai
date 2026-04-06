"""Research API endpoints — view and trigger due diligence research."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.database import async_session_factory
from app.models.research import CompanyResearch
from app.models.user import User

router = APIRouter()


@router.get("")
async def get_research(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the latest research for a company."""
    result = await db.execute(
        select(CompanyResearch)
        .where(CompanyResearch.company_id == company_id)
        .order_by(CompanyResearch.created_at.desc())
        .limit(1)
    )
    research = result.scalar_one_or_none()
    if not research:
        return {"status": "none", "data": None}

    return {
        "id": str(research.id),
        "status": research.status,
        "research_type": research.research_type,
        "company_data": research.company_data or {},
        "industry_data": research.industry_data or {},
        "peer_data": research.peer_data or {},
        "sources": research.sources or [],
        "research_date": research.research_date.isoformat() if research.research_date else None,
        "created_at": research.created_at.isoformat() if research.created_at else None,
    }


@router.post("/trigger")
async def trigger_research(
    company_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger DD research for a company."""
    from app.config import settings

    if not settings.GROQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No API key configured. Go to Settings to add your Groq API key.",
        )

    # Mark the latest research as in_progress so the frontend sees immediate feedback
    result = await db.execute(
        select(CompanyResearch)
        .where(CompanyResearch.company_id == company_id)
        .order_by(CompanyResearch.created_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = "in_progress"
        existing.company_data = {}
        existing.industry_data = {}
        existing.peer_data = {}

    async def _run(cid: uuid.UUID):
        from app.services.ai.research import ResearchService
        async with async_session_factory() as session:
            service = ResearchService(session)
            await service.run_full_research(cid, force=True)
            await session.commit()

    background_tasks.add_task(_run, company_id)

    return {"status": "triggered", "message": "Research started in background"}
