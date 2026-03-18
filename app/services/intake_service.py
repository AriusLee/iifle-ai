import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intake import IntakeStage, IntakeStageNumber, IntakeStatus
from app.schemas.intake.stage_1 import Stage1Data

STAGE_VALIDATORS = {
    IntakeStageNumber.stage_1: Stage1Data,
}


async def save_draft(
    db: AsyncSession,
    company_id: uuid.UUID,
    stage: str,
    data: dict,
    user_id: uuid.UUID,
) -> IntakeStage:
    stage_enum = IntakeStageNumber(stage)

    result = await db.execute(
        select(IntakeStage).where(
            IntakeStage.company_id == company_id,
            IntakeStage.stage == stage_enum,
        )
    )
    intake = result.scalar_one_or_none()

    if intake:
        intake.data = data
        intake.status = IntakeStatus.in_progress
    else:
        intake = IntakeStage(
            company_id=company_id,
            stage=stage_enum,
            status=IntakeStatus.in_progress,
            data=data,
        )
        db.add(intake)

    await db.flush()
    return intake


async def submit_stage(
    db: AsyncSession,
    company_id: uuid.UUID,
    stage: str,
    data: dict,
    user_id: uuid.UUID,
) -> IntakeStage:
    stage_enum = IntakeStageNumber(stage)

    validator = STAGE_VALIDATORS.get(stage_enum)
    if validator:
        try:
            validator.model_validate(data)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=e.errors(),
            )

    result = await db.execute(
        select(IntakeStage).where(
            IntakeStage.company_id == company_id,
            IntakeStage.stage == stage_enum,
        )
    )
    intake = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if intake:
        intake.data = data
        intake.status = IntakeStatus.submitted
        intake.submitted_by = user_id
        intake.submitted_at = now
    else:
        intake = IntakeStage(
            company_id=company_id,
            stage=stage_enum,
            status=IntakeStatus.submitted,
            data=data,
            submitted_by=user_id,
            submitted_at=now,
        )
        db.add(intake)

    await db.flush()
    return intake


async def get_stage(db: AsyncSession, company_id: uuid.UUID, stage: str) -> IntakeStage | None:
    stage_enum = IntakeStageNumber(stage)
    result = await db.execute(
        select(IntakeStage).where(
            IntakeStage.company_id == company_id,
            IntakeStage.stage == stage_enum,
        )
    )
    return result.scalar_one_or_none()


async def get_all_stages(db: AsyncSession, company_id: uuid.UUID) -> list[IntakeStage]:
    result = await db.execute(
        select(IntakeStage)
        .where(IntakeStage.company_id == company_id)
        .order_by(IntakeStage.stage)
    )
    return list(result.scalars().all())
