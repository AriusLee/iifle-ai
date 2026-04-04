"""
API endpoints for the Unicorn Diagnostic Questionnaire.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.company import Company
from app.models.diagnostic import Diagnostic, DiagnosticStatus
from app.models.report import Report, ReportSection
from app.models.user import User
from app.services.diagnostic import service as diagnostic_service

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────


class CompanyBasicInfo(BaseModel):
    legal_name: str = Field(..., min_length=1, max_length=500)
    primary_industry: str | None = None
    country: str = "Malaysia"
    contact_person: str | None = None
    contact_phone: str | None = None


class DiagnosticCreateRequest(BaseModel):
    company: CompanyBasicInfo
    answers: dict = Field(default_factory=dict)
    other_answers: dict = Field(default_factory=dict)


class DiagnosticDraftRequest(BaseModel):
    answers: dict
    other_answers: dict = Field(default_factory=dict)


class ModuleScoreOut(BaseModel):
    name_zh: str
    name_en: str
    score: float
    rating: str


class SectionSubmitRequest(BaseModel):
    answers: dict
    other_answers: dict = Field(default_factory=dict)


class DiagnosticOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str | None = None
    status: str
    answers: dict | None = None
    other_answers: dict | None = None
    overall_score: float | None = None
    overall_rating: str | None = None
    enterprise_stage: str | None = None
    capital_readiness: str | None = None
    module_scores: dict | None = None
    key_findings: list | None = None
    sections_submitted: list[str] | None = None
    stage_score: float | None = None
    section_analyses: dict | None = None
    report_id: uuid.UUID | None = None
    progress_message: str | None = None
    error_message: str | None = None
    submitted_at: datetime | None = None
    scored_at: datetime | None = None
    created_at: datetime


def _diagnostic_to_out(d: Diagnostic, company_name: str | None = None) -> DiagnosticOut:
    # Extract sections_submitted and stage_score from _meta, strip _meta from module_scores output
    module_scores = d.module_scores
    sections_submitted = None
    stage_score = None
    section_analyses = None
    if module_scores and "_meta" in module_scores:
        meta = module_scores["_meta"]
        sections_submitted = meta.get("sections_submitted", [])
        stage_score = meta.get("stage_score")
        section_analyses = meta.get("section_analyses")
        # Return module_scores without _meta key
        module_scores = {k: v for k, v in module_scores.items() if k != "_meta"}

    return DiagnosticOut(
        id=d.id,
        company_id=d.company_id,
        company_name=company_name,
        status=d.status.value,
        answers=d.answers,
        other_answers=d.other_answers,
        overall_score=float(d.overall_score) if d.overall_score else None,
        overall_rating=d.overall_rating,
        enterprise_stage=d.enterprise_stage,
        capital_readiness=d.capital_readiness,
        module_scores=module_scores if module_scores else None,
        key_findings=d.key_findings,
        sections_submitted=sections_submitted,
        stage_score=stage_score,
        section_analyses=section_analyses,
        report_id=d.report_id,
        progress_message=d.progress_message,
        error_message=d.error_message,
        submitted_at=d.submitted_at,
        scored_at=d.scored_at,
        created_at=d.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("", response_model=DiagnosticOut, status_code=status.HTTP_201_CREATED)
async def create_diagnostic(
    body: DiagnosticCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new diagnostic — creates company if needed, then diagnostic record."""
    # Create company
    company = Company(
        legal_name=body.company.legal_name,
        primary_industry=body.company.primary_industry,
        country=body.company.country,
        brief_description=body.company.contact_person,
    )
    db.add(company)
    await db.flush()

    # Create diagnostic
    diagnostic = await diagnostic_service.create_diagnostic(
        db=db, user_id=current_user.id, company_id=company.id
    )

    # Save initial answers if provided
    if body.answers:
        diagnostic.answers = body.answers
        diagnostic.other_answers = body.other_answers
        await db.flush()

    return _diagnostic_to_out(diagnostic, company.legal_name)


@router.get("", response_model=list[DiagnosticOut])
async def list_diagnostics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all diagnostics (advisor sees all, client sees own)."""
    from sqlalchemy import select
    from app.models.user import UserRole, RoleType

    # Check if user is admin/advisor
    role_result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == current_user.id,
            UserRole.role.in_([RoleType.admin, RoleType.advisor]),
        )
    )
    is_advisor = role_result.first() is not None

    if is_advisor:
        diagnostics = await diagnostic_service.list_all_diagnostics(db)
    else:
        diagnostics = await diagnostic_service.list_diagnostics(
            db, user_id=current_user.id
        )

    # Fetch company names
    results = []
    for d in diagnostics:
        company_result = await db.execute(
            select(Company.legal_name).where(Company.id == d.company_id)
        )
        company_name = company_result.scalar_one_or_none()
        results.append(_diagnostic_to_out(d, company_name))

    return results


@router.get("/{diagnostic_id}", response_model=DiagnosticOut)
async def get_diagnostic(
    diagnostic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific diagnostic by ID."""
    diagnostic = await diagnostic_service.get_diagnostic(db, diagnostic_id)
    if not diagnostic:
        raise HTTPException(status_code=404, detail="Diagnostic not found")

    from sqlalchemy import select
    company_result = await db.execute(
        select(Company.legal_name).where(Company.id == diagnostic.company_id)
    )
    company_name = company_result.scalar_one_or_none()

    return _diagnostic_to_out(diagnostic, company_name)


@router.put("/{diagnostic_id}/draft", response_model=DiagnosticOut)
async def save_draft(
    diagnostic_id: uuid.UUID,
    body: DiagnosticDraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save draft answers (auto-save or manual save)."""
    diagnostic = await diagnostic_service.save_draft(
        db=db,
        diagnostic_id=diagnostic_id,
        answers=body.answers,
        other_answers=body.other_answers,
    )
    return _diagnostic_to_out(diagnostic)


@router.post("/{diagnostic_id}/sections/{section_key}/submit", response_model=DiagnosticOut)
async def submit_section(
    diagnostic_id: uuid.UUID,
    section_key: str,
    body: SectionSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit and score a single section of the questionnaire."""
    if section_key not in ("a", "b", "c", "d", "e", "f"):
        raise HTTPException(status_code=400, detail=f"Invalid section: {section_key}")

    try:
        diagnostic = await diagnostic_service.submit_section(
            db=db,
            diagnostic_id=diagnostic_id,
            section_key=section_key,
            answers=body.answers,
            other_answers=body.other_answers,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from sqlalchemy import select
    company_result = await db.execute(
        select(Company.legal_name).where(Company.id == diagnostic.company_id)
    )
    company_name = company_result.scalar_one_or_none()

    return _diagnostic_to_out(diagnostic, company_name)


@router.post("/{diagnostic_id}/submit", response_model=DiagnosticOut)
async def submit_diagnostic(
    diagnostic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit questionnaire — triggers scoring immediately."""
    try:
        diagnostic = await diagnostic_service.submit_and_score(
            db=db, diagnostic_id=diagnostic_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from sqlalchemy import select
    company_result = await db.execute(
        select(Company.legal_name).where(Company.id == diagnostic.company_id)
    )
    company_name = company_result.scalar_one_or_none()

    return _diagnostic_to_out(diagnostic, company_name)


@router.post("/{diagnostic_id}/rerun", response_model=DiagnosticOut)
async def rerun_diagnostic(
    diagnostic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-run scoring and regenerate report for an existing diagnostic."""
    from sqlalchemy import select
    from app.services.diagnostic.report_generator import generate_diagnostic_report

    try:
        diagnostic = await diagnostic_service.submit_and_score(
            db=db, diagnostic_id=diagnostic_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Also regenerate report
    company_result = await db.execute(
        select(Company).where(Company.id == diagnostic.company_id)
    )
    company = company_result.scalar_one_or_none()

    try:
        report = await generate_diagnostic_report(db, diagnostic, company)
        diagnostic.report_id = report.id
        await db.flush()
    except Exception as exc:
        diagnostic.error_message = f"Report regeneration failed: {str(exc)[:500]}"
        await db.flush()

    company_name = company.legal_name if company else None
    return _diagnostic_to_out(diagnostic, company_name)


@router.post("/{diagnostic_id}/generate-report", response_model=DiagnosticOut)
async def generate_report(
    diagnostic_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI report generation for a completed diagnostic."""
    from sqlalchemy import select
    from app.services.diagnostic.report_generator import generate_diagnostic_report

    diagnostic = await diagnostic_service.get_diagnostic(db, diagnostic_id)
    if not diagnostic:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    has_scores = diagnostic.module_scores and any(k != "_meta" for k in (diagnostic.module_scores or {}))
    if not has_scores:
        raise HTTPException(status_code=400, detail="Diagnostic must be scored before generating report")

    company_result = await db.execute(
        select(Company).where(Company.id == diagnostic.company_id)
    )
    company = company_result.scalar_one_or_none()

    diagnostic.progress_message = "Generating AI report..."
    await db.flush()

    # Generate report (this calls AI, may take a while)
    try:
        report = await generate_diagnostic_report(db, diagnostic, company)
        diagnostic.report_id = report.id
        diagnostic.progress_message = None
        await db.flush()
    except Exception as exc:
        diagnostic.progress_message = None
        diagnostic.error_message = f"Report generation failed: {str(exc)[:500]}"
        await db.flush()

    company_name = company.legal_name if company else None
    return _diagnostic_to_out(diagnostic, company_name)


@router.get("/{diagnostic_id}/report")
async def get_diagnostic_report(
    diagnostic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the report for a diagnostic (no company-role check needed)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    diagnostic = await diagnostic_service.get_diagnostic(db, diagnostic_id)
    if not diagnostic:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    if not diagnostic.report_id:
        raise HTTPException(status_code=404, detail="No report generated yet")

    result = await db.execute(
        select(Report)
        .options(selectinload(Report.sections))
        .where(Report.id == diagnostic.report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    sections = sorted(report.sections, key=lambda s: s.sort_order)
    return {
        "id": str(report.id),
        "title": report.title,
        "status": report.status.value,
        "language": report.language.value,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "sections": [
            {
                "id": str(s.id),
                "section_key": s.section_key,
                "section_title": s.section_title,
                "content_cn": s.content_cn,
                "content_en": s.content_en,
                "sort_order": s.sort_order,
                "is_ai_generated": s.is_ai_generated,
            }
            for s in sections
        ],
    }
