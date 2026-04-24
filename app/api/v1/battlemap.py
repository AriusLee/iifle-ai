"""
API endpoints for Phase 1.5 Battle Map.

Flow:
  1. POST   /diagnostics/{diagnostic_id}/battlemap         → create (or fetch existing)
  2. GET    /battlemaps/{battle_map_id}                    → read
  3. PUT    /battlemaps/{battle_map_id}/draft              → save draft answers
  4. POST   /battlemaps/{battle_map_id}/submit             → classify variant
  5. POST   /battlemaps/{battle_map_id}/generate-report    → AI-generate the 10-chapter report
  6. GET    /battlemaps/{battle_map_id}/report             → read the generated report
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.models.battlemap import BattleMap, BattleMapStatus
from app.models.company import Company
from app.models.diagnostic import Diagnostic
from app.models.report import Report
from app.models.user import User
from app.services.battlemap import service as battlemap_service
from app.services.battlemap.report_generator import generate_battlemap_report

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DraftRequest(BaseModel):
    answers: dict
    other_answers: dict = Field(default_factory=dict)


class SectionSubmitRequest(BaseModel):
    answers: dict
    other_answers: dict = Field(default_factory=dict)


class BattleMapOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str | None = None
    diagnostic_id: uuid.UUID
    status: str
    variant: str | None = None
    variant_name_zh: str | None = None
    variant_name_en: str | None = None
    current_stage: str | None = None
    target_stage: str | None = None
    answers: dict | None = None
    other_answers: dict | None = None
    top_priorities: list | None = None
    do_not_do: list | None = None
    battle_modules: list | None = None
    timeline: dict | None = None
    source_scores: dict | None = None
    sections_submitted: list[str] | None = None
    section_analyses: dict | None = None
    report_id: uuid.UUID | None = None
    progress_message: str | None = None
    error_message: str | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


def _battle_map_to_out(bm: BattleMap, company_name: str | None = None) -> BattleMapOut:
    variant_name_zh = None
    variant_name_en = None
    if bm.variant:
        from app.services.battlemap.variants import variant_meta
        meta = variant_meta(bm.variant)
        variant_name_zh = meta["name_zh"]
        variant_name_en = meta["name_en"]

    # Split _meta (bookkeeping) from per-section analyses so the frontend can
    # render analyses by section-key directly without special-casing _meta.
    raw_analyses = bm.section_analyses or {}
    sections_submitted = (raw_analyses.get("_meta") or {}).get("sections_submitted") or []
    public_analyses = {k: v for k, v in raw_analyses.items() if k != "_meta"}

    return BattleMapOut(
        id=bm.id,
        company_id=bm.company_id,
        company_name=company_name,
        diagnostic_id=bm.diagnostic_id,
        status=bm.status.value,
        variant=bm.variant.value if bm.variant else None,
        variant_name_zh=variant_name_zh,
        variant_name_en=variant_name_en,
        current_stage=bm.current_stage,
        target_stage=bm.target_stage,
        answers=bm.answers,
        other_answers=bm.other_answers,
        top_priorities=bm.top_priorities,
        do_not_do=bm.do_not_do,
        battle_modules=bm.battle_modules,
        timeline=bm.timeline,
        source_scores=bm.source_scores,
        sections_submitted=sections_submitted,
        section_analyses=public_analyses,
        report_id=bm.report_id,
        progress_message=bm.progress_message,
        error_message=bm.error_message,
        submitted_at=bm.submitted_at,
        completed_at=bm.completed_at,
        created_at=bm.created_at,
    )


async def _company_name(db: AsyncSession, company_id: uuid.UUID) -> str | None:
    result = await db.execute(select(Company.legal_name).where(Company.id == company_id))
    return result.scalar_one_or_none()


# ── Create (under a diagnostic) ───────────────────────────────────────────────

@router.post(
    "/diagnostics/{diagnostic_id}/battlemap",
    response_model=BattleMapOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_for_diagnostic(
    diagnostic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Phase 1.5 battle map attached to a completed Phase 1 diagnostic."""
    diag_result = await db.execute(select(Diagnostic).where(Diagnostic.id == diagnostic_id))
    diagnostic = diag_result.scalar_one_or_none()
    if not diagnostic:
        raise HTTPException(status_code=404, detail="Diagnostic not found")

    has_scores = diagnostic.module_scores and any(k != "_meta" for k in (diagnostic.module_scores or {}))
    if not has_scores:
        raise HTTPException(
            status_code=400,
            detail="Phase 1 diagnostic must be scored before starting Phase 1.5",
        )

    battle_map = await battlemap_service.create_battle_map(db, current_user.id, diagnostic)
    name = await _company_name(db, battle_map.company_id)
    return _battle_map_to_out(battle_map, name)


# ── Read ──────────────────────────────────────────────────────────────────────

@router.get("/battlemaps/mine", response_model=list[BattleMapOut])
async def list_mine(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await battlemap_service.list_by_user(db, current_user.id)
    results = []
    for bm in items:
        name = await _company_name(db, bm.company_id)
        results.append(_battle_map_to_out(bm, name))
    return results


@router.get("/battlemaps", response_model=list[BattleMapOut])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Advisor dashboard — list all battle maps across customers."""
    items = await battlemap_service.list_all(db)
    results = []
    for bm in items:
        name = await _company_name(db, bm.company_id)
        results.append(_battle_map_to_out(bm, name))
    return results


@router.get("/battlemaps/{battle_map_id}", response_model=BattleMapOut)
async def get_one(
    battle_map_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bm = await battlemap_service.get_battle_map(db, battle_map_id)
    if not bm:
        raise HTTPException(status_code=404, detail="BattleMap not found")
    name = await _company_name(db, bm.company_id)
    return _battle_map_to_out(bm, name)


# ── Save draft / submit / generate ───────────────────────────────────────────

@router.put("/battlemaps/{battle_map_id}/draft", response_model=BattleMapOut)
async def save_draft(
    battle_map_id: uuid.UUID,
    body: DraftRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bm = await battlemap_service.save_draft(
        db=db,
        battle_map_id=battle_map_id,
        answers=body.answers,
        other_answers=body.other_answers,
    )
    name = await _company_name(db, bm.company_id)
    return _battle_map_to_out(bm, name)


@router.post(
    "/battlemaps/{battle_map_id}/sections/{section_key}/submit",
    response_model=BattleMapOut,
)
async def submit_section(
    battle_map_id: uuid.UUID,
    section_key: str,
    body: SectionSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit one section: saves answers, generates AI analysis, auto-classifies
    when all 8 sections are submitted."""
    try:
        bm = await battlemap_service.submit_section(
            db=db,
            battle_map_id=battle_map_id,
            section_key=section_key,
            answers=body.answers,
            other_answers=body.other_answers,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    name = await _company_name(db, bm.company_id)
    return _battle_map_to_out(bm, name)


@router.post("/battlemaps/{battle_map_id}/submit", response_model=BattleMapOut)
async def submit(
    battle_map_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manual all-at-once classify (kept as fallback; normally auto-runs after
    the 8th section submit)."""
    try:
        bm = await battlemap_service.submit_and_classify(db, battle_map_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    name = await _company_name(db, bm.company_id)
    return _battle_map_to_out(bm, name)


@router.post("/battlemaps/{battle_map_id}/generate-report", response_model=BattleMapOut)
async def generate_report(
    battle_map_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bm = await battlemap_service.get_battle_map(db, battle_map_id)
    if not bm:
        raise HTTPException(status_code=404, detail="BattleMap not found")
    if bm.variant is None:
        raise HTTPException(
            status_code=400,
            detail="Battle map must be submitted and classified before generating report",
        )

    diag_result = await db.execute(
        select(Diagnostic).where(Diagnostic.id == bm.diagnostic_id)
    )
    diagnostic = diag_result.scalar_one_or_none()
    if not diagnostic:
        raise HTTPException(status_code=400, detail="Linked diagnostic missing")

    company_result = await db.execute(select(Company).where(Company.id == bm.company_id))
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=400, detail="Company missing")

    bm.status = BattleMapStatus.generating
    bm.progress_message = "Generating battle map report..."
    await db.flush()

    try:
        report = await generate_battlemap_report(db, bm, diagnostic, company)
        bm.report_id = report.id
        bm.status = BattleMapStatus.completed
        bm.progress_message = None
        await db.flush()
    except Exception as exc:
        bm.status = BattleMapStatus.failed
        bm.progress_message = None
        bm.error_message = f"Report generation failed: {str(exc)[:500]}"
        await db.flush()

    return _battle_map_to_out(bm, company.legal_name)


@router.get("/battlemaps/{battle_map_id}/report")
async def get_report(
    battle_map_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bm = await battlemap_service.get_battle_map(db, battle_map_id)
    if not bm:
        raise HTTPException(status_code=404, detail="BattleMap not found")
    if not bm.report_id:
        raise HTTPException(status_code=404, detail="No report generated yet")

    result = await db.execute(
        select(Report)
        .options(selectinload(Report.sections))
        .where(Report.id == bm.report_id)
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
        "variant": bm.variant.value if bm.variant else None,
        "current_stage": bm.current_stage,
        "target_stage": bm.target_stage,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "sections": [
            {
                "id": str(s.id),
                "section_key": s.section_key,
                "section_title": s.section_title,
                "content_cn": s.content_cn,
                "content_en": s.content_en,
                "content_data": s.content_data,
                "sort_order": s.sort_order,
                "is_ai_generated": s.is_ai_generated,
            }
            for s in sections
        ],
    }
