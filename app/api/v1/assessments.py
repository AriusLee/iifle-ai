"""
Assessment API endpoints — trigger scoring, list and retrieve assessments.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db, require_role
from app.models.assessment import Assessment, AutoFlag, ModuleScore
from app.models.company import Company
from app.models.intake import IntakeStage, IntakeStageNumber
from app.models.user import User
from app.schemas.assessment import (
    AssessmentDetailResponse,
    AssessmentResponse,
    AutoFlagResponse,
    DimensionScoreResponse,
    ModuleScoreResponse,
    TriggerAssessmentRequest,
)
from app.services.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_company_or_404(
    company_id: uuid.UUID,
    db: AsyncSession,
) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def _get_assessment_or_404(
    assessment_id: uuid.UUID,
    company_id: uuid.UUID,
    db: AsyncSession,
) -> Assessment:
    result = await db.execute(
        select(Assessment)
        .options(
            selectinload(Assessment.module_scores).selectinload(ModuleScore.dimension_scores),
            selectinload(Assessment.auto_flags),
        )
        .where(Assessment.id == assessment_id, Assessment.company_id == company_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return assessment


def _build_detail_response(assessment: Assessment) -> AssessmentDetailResponse:
    """Build a fully nested response from ORM objects."""
    modules = []
    for ms in sorted(assessment.module_scores, key=lambda m: m.module_number):
        dims = [
            DimensionScoreResponse(
                dimension_number=ds.dimension_number,
                dimension_name=ds.dimension_name,
                score=float(ds.score) if ds.score is not None else None,
                weight=float(ds.weight),
                scoring_method=ds.scoring_method,
                calculation_detail=ds.calculation_detail,
                ai_reasoning=ds.ai_reasoning,
            )
            for ds in sorted(ms.dimension_scores, key=lambda d: d.dimension_number)
        ]
        modules.append(
            ModuleScoreResponse(
                module_number=ms.module_number,
                module_name=ms.module_name,
                total_score=float(ms.total_score) if ms.total_score is not None else None,
                rating=ms.rating,
                weight=float(ms.weight),
                dimensions=dims,
            )
        )

    flags = [
        AutoFlagResponse(
            flag_type=f.flag_type,
            severity=f.severity.value,
            description=f.description,
            source_field=f.source_field,
            source_value=f.source_value,
            is_resolved=f.is_resolved,
        )
        for f in assessment.auto_flags
    ]

    return AssessmentDetailResponse(
        id=assessment.id,
        company_id=assessment.company_id,
        status=assessment.status.value,
        overall_score=float(assessment.overall_score) if assessment.overall_score is not None else None,
        overall_rating=assessment.overall_rating,
        enterprise_stage_classification=assessment.enterprise_stage_classification,
        capital_readiness=assessment.capital_readiness.value if assessment.capital_readiness else None,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at,
        modules=modules,
        flags=flags,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger company scoring (background)",
)
async def trigger_assessment(
    company_id: uuid.UUID,
    body: TriggerAssessmentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Trigger scoring in background — returns immediately with assessment ID."""
    company = await _get_company_or_404(company_id, db)

    # Gather intake data now (while we have the session)
    intake_data = await _load_intake_data(company_id, body.stage, db)
    intake_data.setdefault("company_name", company.legal_name)
    intake_data.setdefault("primary_industry", company.primary_industry)
    intake_data.setdefault("industry", company.primary_industry)
    intake_data.setdefault("enterprise_stage", company.enterprise_stage or "1.0")
    intake_data.setdefault("country", company.country)

    # Create assessment record NOW so frontend can track it
    from app.models.assessment import Assessment as AssessmentModel, AssessmentStatus
    assessment = AssessmentModel(
        id=uuid.uuid4(),
        company_id=company_id,
        trigger_stage=body.stage,
        status=AssessmentStatus.scoring,
    )
    db.add(assessment)
    await db.commit()
    assessment_id = assessment.id

    # Load Stage 1 data too (for Stage 2 scoring context)
    stage1_data = None
    if body.stage == "2":
        stage1_data = await _load_intake_data(company_id, "1", db)
        if stage1_data:
            stage1_data.setdefault("company_name", company.legal_name)
            stage1_data.setdefault("primary_industry", company.primary_industry)

    trigger_stage = body.stage

    async def _run_scoring():
        from app.database import async_session_factory
        from sqlalchemy import update as sql_update
        try:
            async with async_session_factory() as session:
                engine = ScoringEngine()
                if trigger_stage == "2":
                    await engine.score_stage2(
                        company_id, intake_data, session,
                        assessment_id=assessment_id,
                        stage1_data=stage1_data,
                    )
                else:
                    await engine.score_stage1(
                        company_id, intake_data, session,
                        assessment_id=assessment_id,
                    )
                await session.commit()
                logger.info("Scoring (stage %s) completed for company %s", trigger_stage, company_id)
        except Exception as exc:
            logger.exception("Background scoring failed for %s: %s", company_id, exc)
            try:
                async with async_session_factory() as err_session:
                    await err_session.execute(
                        sql_update(AssessmentModel)
                        .where(AssessmentModel.id == assessment_id)
                        .values(status=AssessmentStatus.failed, error_message=str(exc)[:1000])
                    )
                    await err_session.commit()
            except Exception:
                logger.exception("Failed to save error status for assessment %s", assessment_id)

    background_tasks.add_task(_run_scoring)

    return {"status": "scoring", "assessment_id": str(assessment_id), "company_id": str(company_id)}


@router.get(
    "",
    response_model=list[AssessmentResponse],
    summary="List assessments for a company",
)
async def list_assessments(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """List all assessments for a company, ordered newest first."""
    await _get_company_or_404(company_id, db)

    result = await db.execute(
        select(Assessment)
        .where(Assessment.company_id == company_id)
        .order_by(Assessment.created_at.desc())
    )
    assessments = result.scalars().all()

    return [
        AssessmentResponse(
            id=a.id,
            company_id=a.company_id,
            status=a.status.value,
            overall_score=float(a.overall_score) if a.overall_score is not None else None,
            overall_rating=a.overall_rating,
            enterprise_stage_classification=a.enterprise_stage_classification,
            capital_readiness=a.capital_readiness.value if a.capital_readiness else None,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in assessments
    ]


@router.get(
    "/{assessment_id}",
    response_model=AssessmentDetailResponse,
    summary="Get assessment with all scores",
)
async def get_assessment(
    company_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """Get a single assessment with all module scores, dimension scores, and flags."""
    assessment = await _get_assessment_or_404(assessment_id, company_id, db)
    return _build_detail_response(assessment)


@router.get(
    "/{assessment_id}/flags",
    response_model=list[AutoFlagResponse],
    summary="Get auto-flags for an assessment",
)
async def get_assessment_flags(
    company_id: uuid.UUID,
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """Get all auto-detected flags for an assessment."""
    result = await db.execute(
        select(AutoFlag).where(
            AutoFlag.assessment_id == assessment_id,
            AutoFlag.company_id == company_id,
        )
    )
    flags = result.scalars().all()

    if not flags:
        # Verify assessment exists
        await _get_assessment_or_404(assessment_id, company_id, db)

    return [
        AutoFlagResponse(
            flag_type=f.flag_type,
            severity=f.severity.value,
            description=f.description,
            source_field=f.source_field,
            source_value=f.source_value,
            is_resolved=f.is_resolved,
        )
        for f in flags
    ]


# ---------------------------------------------------------------------------
# Intake data loader
# ---------------------------------------------------------------------------

async def _load_intake_data(
    company_id: uuid.UUID,
    stage: str,
    db: AsyncSession,
) -> dict:
    """Load and flatten intake data for the requested stage."""
    # Map stage string to enum
    try:
        stage_enum = IntakeStageNumber(stage)
    except ValueError:
        stage_enum = IntakeStageNumber.stage_1

    result = await db.execute(
        select(IntakeStage).where(
            IntakeStage.company_id == company_id,
            IntakeStage.stage == stage_enum,
        )
    )
    intake = result.scalar_one_or_none()

    if not intake:
        logger.warning(
            "No intake data found for company %s stage %s — scoring with empty data",
            company_id,
            stage,
        )
        return {}

    # The intake record stores structured JSON data
    data: dict = {}
    if hasattr(intake, "data") and intake.data:
        if isinstance(intake.data, dict):
            data = dict(intake.data)
        else:
            data = {}

    # Also check for section-based storage
    if hasattr(intake, "sections") and intake.sections:
        for section in intake.sections:
            if hasattr(section, "data") and section.data:
                data.update(section.data)

    return data
