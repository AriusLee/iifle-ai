"""
Auto-Intake API — triggers AI-powered automatic Stage 1 data extraction
from uploaded documents + web research.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.database import async_session_factory
from app.models.company import Company
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_auto_intake(company_id: uuid.UUID) -> None:
    """Background task: run auto-intake processing for a company."""
    import asyncio
    from app.services.ai.auto_intake import AutoIntakeService

    # Small delay to ensure documents are committed
    await asyncio.sleep(2)

    try:
        async with async_session_factory() as db:
            service = AutoIntakeService(db)
            result = await service.process_company(company_id)
            await db.commit()
            sections_filled = [k for k, v in result.items() if v] if isinstance(result, dict) else []
            logger.info(
                "Auto-intake completed for %s — filled sections: %s",
                company_id,
                ", ".join(sections_filled) if sections_filled else "unknown",
            )
    except Exception as exc:
        logger.exception("Auto-intake background task failed for %s: %s", company_id, exc)
        # Save error to intake stage so frontend can display it
        try:
            async with async_session_factory() as err_db:
                from app.models.intake import IntakeStage, IntakeStageNumber
                from sqlalchemy import select as sa_select, update as sa_update
                result = await err_db.execute(
                    sa_select(IntakeStage).where(
                        IntakeStage.company_id == company_id,
                        IntakeStage.stage == IntakeStageNumber.stage_1,
                    )
                )
                intake = result.scalar_one_or_none()
                if intake:
                    intake.data = {**(intake.data or {}), "_error": str(exc)[:500]}
                    intake.status = "not_started"
                else:
                    from app.services.intake_service import save_draft
                    await save_draft(err_db, company_id, "1", {"_error": str(exc)[:500]}, uuid.UUID("00000000-0000-0000-0000-000000000000"))
                await err_db.commit()
        except Exception:
            logger.exception("Failed to save auto-intake error for %s", company_id)


@router.post("/process")
async def trigger_auto_intake(
    company_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger AI auto-intake processing for a company.

    Extracts data from uploaded files + web research to fill Stage 1.
    Processing runs in the background — returns immediately with status.
    """
    # Check company exists
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # Check API key configured
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured — ANTHROPIC_API_KEY is not set",
        )

    # Run in background (uses its own DB session)
    background_tasks.add_task(_run_auto_intake, company_id)

    return {
        "status": "processing",
        "message": f"Auto-intake started for {company.legal_name}. Stage 1 data will be filled automatically.",
        "company_id": str(company_id),
    }
