"""
Assessment API endpoints — trigger scoring, list and retrieve assessments.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
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
    response_model=AssessmentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger company scoring",
)
async def trigger_assessment(
    company_id: uuid.UUID,
    body: TriggerAssessmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Trigger a new Stage 1 assessment for the company.

    This runs the full scoring pipeline: auto-flag detection, Gene Structure,
    and Business Model scoring (with parallel AI calls).
    """
    company = await _get_company_or_404(company_id, db)

    # Gather intake data for the requested stage
    intake_data = await _load_intake_data(company_id, body.stage, db)

    # Enrich with company-level info
    intake_data.setdefault("company_name", company.legal_name)
    intake_data.setdefault("primary_industry", company.primary_industry)
    intake_data.setdefault("industry", company.primary_industry)
    intake_data.setdefault("enterprise_stage", company.enterprise_stage or "1.0")
    intake_data.setdefault("country", company.country)

    engine = ScoringEngine()

    try:
        assessment = await engine.score_stage1(company_id, intake_data, db)
    except Exception as exc:
        logger.exception("Scoring engine failed for company %s", company_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring failed: {exc}",
        ) from exc

    # Reload with relationships
    assessment = await _get_assessment_or_404(assessment.id, company_id, db)
    return _build_detail_response(assessment)


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
