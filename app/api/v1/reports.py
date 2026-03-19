"""
Report API endpoints — list, view, edit sections, approve, and reject reports.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db, require_role
from app.models.company import Company
from app.models.report import Report, ReportSection
from app.models.user import User
from app.schemas.report import (
    ReportDetailResponse,
    ReportResponse,
    ReportSectionResponse,
    ReviewRequest,
    UpdateSectionRequest,
)
from app.services.report.review_service import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas (inline — small request model)
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class GenerateReportRequest(BaseModel):
    module_number: int = Field(..., ge=1, le=6, description="Module number to generate report for")
    assessment_id: str = Field(..., description="Assessment ID to generate report from")
    tier: str = Field("standard", description="Report tier: essential, standard, or premium")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_company_or_404(company_id: uuid.UUID, db: AsyncSession) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def _get_report_or_404(
    report_id: uuid.UUID,
    company_id: uuid.UUID,
    db: AsyncSession,
) -> Report:
    result = await db.execute(
        select(Report)
        .options(selectinload(Report.sections))
        .where(Report.id == report_id, Report.company_id == company_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _report_to_response(report: Report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        assessment_id=report.assessment_id,
        company_id=report.company_id,
        report_type=report.report_type.value,
        title=report.title,
        status=report.status.value,
        language=report.language.value,
        version=report.version,
        approved_by=report.approved_by,
        approved_at=report.approved_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _section_to_response(section: ReportSection) -> ReportSectionResponse:
    return ReportSectionResponse(
        id=section.id,
        section_key=section.section_key,
        section_title=section.section_title,
        content_en=section.content_en,
        content_cn=section.content_cn,
        content_data=section.content_data,
        sort_order=section.sort_order,
        is_ai_generated=section.is_ai_generated,
        last_edited_by=section.last_edited_by,
        last_edited_at=section.last_edited_at,
    )


def _report_detail_response(report: Report) -> ReportDetailResponse:
    sections = sorted(report.sections, key=lambda s: s.sort_order)
    return ReportDetailResponse(
        id=report.id,
        assessment_id=report.assessment_id,
        company_id=report.company_id,
        report_type=report.report_type.value,
        title=report.title,
        status=report.status.value,
        language=report.language.value,
        version=report.version,
        approved_by=report.approved_by,
        approved_at=report.approved_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        sections=[_section_to_response(s) for s in sections],
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a report for a module (background)",
)
async def generate_report(
    company_id: uuid.UUID,
    body: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Trigger AI report generation for a specific module. Runs in background."""
    await _get_company_or_404(company_id, db)

    assessment_id = uuid.UUID(body.assessment_id)

    # Verify assessment exists and belongs to this company
    from app.models.assessment import Assessment as AssessmentModel

    result = await db.execute(
        select(AssessmentModel).where(
            AssessmentModel.id == assessment_id,
            AssessmentModel.company_id == company_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    module_number = body.module_number
    tier = body.tier

    async def _run_generation():
        from app.database import async_session_factory
        from app.services.report.generator import ReportGenerator

        try:
            async with async_session_factory() as session:
                generator = ReportGenerator(session)
                await generator.generate_module_report(
                    assessment_id=assessment_id,
                    module_number=module_number,
                    company_id=company_id,
                    tier=tier,
                )
                await session.commit()
                logger.info(
                    "Report generated for module %d, company %s",
                    module_number,
                    company_id,
                )
        except Exception as exc:
            logger.exception(
                "Report generation failed for module %d, company %s: %s",
                module_number,
                company_id,
                exc,
            )

    background_tasks.add_task(_run_generation)

    return {
        "status": "generating",
        "module_number": module_number,
        "assessment_id": str(assessment_id),
        "company_id": str(company_id),
    }


@router.get(
    "",
    response_model=list[ReportResponse],
    summary="List reports for a company",
)
async def list_reports(
    company_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """List all reports for a company, ordered newest first."""
    await _get_company_or_404(company_id, db)

    result = await db.execute(
        select(Report)
        .where(Report.company_id == company_id)
        .order_by(Report.created_at.desc())
    )
    reports = result.scalars().all()

    return [_report_to_response(r) for r in reports]


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    summary="Get report with all sections",
)
async def get_report(
    company_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """Get a single report with all its sections."""
    report = await _get_report_or_404(report_id, company_id, db)
    return _report_detail_response(report)


@router.get(
    "/{report_id}/export/pdf",
    summary="Export report as PDF",
)
async def export_report_pdf(
    company_id: uuid.UUID,
    report_id: uuid.UUID,
    language: str = "en",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor", "client"])),
):
    """Generate and return a PDF for the given report."""
    from fastapi.responses import Response
    from app.services.export.pdf_generator import generate_pdf

    await _get_company_or_404(company_id, db)

    try:
        pdf_bytes = await generate_pdf(report_id, company_id, db, language)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # Build filename
    report = await _get_report_or_404(report_id, company_id, db)
    safe_title = (report.title or "report").replace(" ", "_").lower()
    filename = f"{safe_title}_v{report.version}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put(
    "/{report_id}/sections/{section_id}",
    response_model=ReportSectionResponse,
    summary="Update a report section",
)
async def update_section(
    company_id: uuid.UUID,
    report_id: uuid.UUID,
    section_id: uuid.UUID,
    body: UpdateSectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Update a report section's content (advisor manual edit)."""
    # Verify report belongs to company
    await _get_report_or_404(report_id, company_id, db)

    # Verify section belongs to report
    section_result = await db.execute(
        select(ReportSection).where(
            ReportSection.id == section_id,
            ReportSection.report_id == report_id,
        )
    )
    if not section_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report section not found",
        )

    review_service = ReviewService()
    try:
        section = await review_service.update_section(
            section_id=section_id,
            content_en=body.content_en,
            content_cn=body.content_cn,
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _section_to_response(section)


@router.post(
    "/{report_id}/approve",
    response_model=ReportResponse,
    summary="Approve a report",
)
async def approve_report(
    company_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Approve a report, transitioning it to 'approved' status."""
    await _get_report_or_404(report_id, company_id, db)

    review_service = ReviewService()
    try:
        report = await review_service.approve_report(
            report_id=report_id,
            user_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _report_to_response(report)


@router.post(
    "/{report_id}/reject",
    response_model=ReportResponse,
    summary="Reject a report",
)
async def reject_report(
    company_id: uuid.UUID,
    report_id: uuid.UUID,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "advisor"])),
):
    """Reject a report, transitioning it to 'revision' status."""
    await _get_report_or_404(report_id, company_id, db)

    review_service = ReviewService()
    try:
        report = await review_service.reject_report(
            report_id=report_id,
            user_id=current_user.id,
            reason=body.reason,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _report_to_response(report)
