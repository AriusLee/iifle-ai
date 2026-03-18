import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.intake_service import get_all_stages, get_stage, save_draft, submit_stage

router = APIRouter()


@router.put("/{stage}/draft")
async def save_draft_endpoint(
    company_id: uuid.UUID,
    stage: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if stage not in ("1", "2", "3"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid stage. Must be 1, 2, or 3.")
    intake = await save_draft(db, company_id, stage, data, current_user.id)
    return {
        "id": str(intake.id),
        "company_id": str(intake.company_id),
        "stage": intake.stage.value,
        "status": intake.status.value,
        "data": intake.data,
        "completed_sections": intake.completed_sections,
    }


@router.post("/{stage}/submit")
async def submit_stage_endpoint(
    company_id: uuid.UUID,
    stage: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if stage not in ("1", "2", "3"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid stage. Must be 1, 2, or 3.")
    intake = await submit_stage(db, company_id, stage, data, current_user.id)
    return {
        "id": str(intake.id),
        "company_id": str(intake.company_id),
        "stage": intake.stage.value,
        "status": intake.status.value,
        "data": intake.data,
        "submitted_at": intake.submitted_at.isoformat() if intake.submitted_at else None,
    }


@router.get("/{stage}")
async def get_stage_endpoint(
    company_id: uuid.UUID,
    stage: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if stage not in ("1", "2", "3"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid stage. Must be 1, 2, or 3.")
    intake = await get_stage(db, company_id, stage)
    if not intake:
        return {
            "company_id": str(company_id),
            "stage": stage,
            "status": "not_started",
            "data": {},
            "completed_sections": [],
        }
    return {
        "id": str(intake.id),
        "company_id": str(intake.company_id),
        "stage": intake.stage.value,
        "status": intake.status.value,
        "data": intake.data,
        "completed_sections": intake.completed_sections,
    }


@router.get("")
async def get_all_stages_endpoint(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stages = await get_all_stages(db, company_id)
    return [
        {
            "id": str(s.id),
            "company_id": str(s.company_id),
            "stage": s.stage.value,
            "status": s.status.value,
            "data": s.data,
            "completed_sections": s.completed_sections,
        }
        for s in stages
    ]
