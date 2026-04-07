"""
Diagnostic service — handles CRUD, scoring, and report orchestration.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm.attributes import flag_modified

from app.models.diagnostic import Diagnostic, DiagnosticStatus
from app.models.company import Company
from app.services.diagnostic.scoring import score_diagnostic, score_section, recalculate_overall
from app.services.diagnostic.section_analysis import generate_section_analysis


async def create_diagnostic(
    db: AsyncSession,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
) -> Diagnostic:
    """Create a new draft diagnostic for a company."""
    diagnostic = Diagnostic(
        user_id=user_id,
        company_id=company_id,
        status=DiagnosticStatus.draft,
        answers={},
        other_answers={},
    )
    db.add(diagnostic)
    await db.flush()
    return diagnostic


async def save_draft(
    db: AsyncSession,
    diagnostic_id: uuid.UUID,
    answers: dict,
    other_answers: dict | None = None,
) -> Diagnostic:
    """Save draft answers (partial or complete)."""
    result = await db.execute(
        select(Diagnostic).where(Diagnostic.id == diagnostic_id)
    )
    diagnostic = result.scalar_one_or_none()
    if not diagnostic:
        raise ValueError("Diagnostic not found")

    diagnostic.answers = answers
    if other_answers is not None:
        diagnostic.other_answers = other_answers
    diagnostic.status = DiagnosticStatus.draft
    await db.flush()
    return diagnostic


async def submit_and_score(
    db: AsyncSession,
    diagnostic_id: uuid.UUID,
) -> Diagnostic:
    """Submit questionnaire, run scoring, update diagnostic."""
    result = await db.execute(
        select(Diagnostic).where(Diagnostic.id == diagnostic_id)
    )
    diagnostic = result.scalar_one_or_none()
    if not diagnostic:
        raise ValueError("Diagnostic not found")

    if not diagnostic.answers:
        raise ValueError("No answers to score")

    diagnostic.status = DiagnosticStatus.scoring
    diagnostic.submitted_at = datetime.now(timezone.utc)
    diagnostic.progress_message = "Scoring answers..."
    await db.flush()

    try:
        # Run scoring
        scores = score_diagnostic(diagnostic.answers)

        diagnostic.overall_score = scores["overall_score"]
        diagnostic.overall_rating = scores["overall_rating"]
        diagnostic.enterprise_stage = scores["enterprise_stage"]
        diagnostic.capital_readiness = scores["capital_readiness"]
        diagnostic.module_scores = scores["module_scores"]
        diagnostic.key_findings = scores["key_findings"]
        diagnostic.status = DiagnosticStatus.completed
        diagnostic.scored_at = datetime.now(timezone.utc)
        diagnostic.progress_message = None
        diagnostic.error_message = None

        # Update company industry from Q03 if available
        if scores.get("industry"):
            company_result = await db.execute(
                select(Company).where(Company.id == diagnostic.company_id)
            )
            company = company_result.scalar_one_or_none()
            if company and not company.primary_industry:
                company.primary_industry = scores["industry"]

        await db.flush()
    except Exception as exc:
        diagnostic.status = DiagnosticStatus.failed
        diagnostic.error_message = str(exc)[:1000]
        diagnostic.progress_message = None
        await db.flush()
        raise

    return diagnostic


SECTION_ORDER = ["a", "b", "c", "d", "e", "f"]


async def submit_section(
    db: AsyncSession,
    diagnostic_id: uuid.UUID,
    section_key: str,
    answers: dict,
    other_answers: dict | None = None,
) -> Diagnostic:
    """Submit and score a single section of the questionnaire."""
    if section_key not in SECTION_ORDER:
        raise ValueError(f"Invalid section: {section_key}")

    result = await db.execute(
        select(Diagnostic).where(Diagnostic.id == diagnostic_id)
    )
    diagnostic = result.scalar_one_or_none()
    if not diagnostic:
        raise ValueError("Diagnostic not found")

    # Ensure module_scores has _meta
    if not diagnostic.module_scores:
        diagnostic.module_scores = {}
    meta = diagnostic.module_scores.get("_meta", {"sections_submitted": []})
    sections_submitted = meta.get("sections_submitted", [])

    # Validate ordering: previous section must be submitted (unless re-submitting)
    section_idx = SECTION_ORDER.index(section_key)
    if section_key not in sections_submitted and section_idx > 0:
        prev = SECTION_ORDER[section_idx - 1]
        if prev not in sections_submitted:
            raise ValueError(f"Section {prev.upper()} must be submitted first")

    # Merge answers
    existing_answers = diagnostic.answers or {}
    existing_answers.update(answers)
    diagnostic.answers = existing_answers

    if other_answers is not None:
        existing_other = diagnostic.other_answers or {}
        existing_other.update(other_answers)
        diagnostic.other_answers = existing_other

    # Score this section
    section_result = score_section(diagnostic.answers, section_key)

    # Merge module scores
    for mod_key, mod_data in section_result["module_scores"].items():
        diagnostic.module_scores[mod_key] = mod_data

    # Update enterprise stage (section a)
    if section_result["enterprise_stage"]:
        diagnostic.enterprise_stage = section_result["enterprise_stage"]
    if section_result.get("stage_score") is not None:
        meta["stage_score"] = section_result["stage_score"]

    # Update industry from section a
    if section_result.get("industry"):
        company_result = await db.execute(
            select(Company).where(Company.id == diagnostic.company_id)
        )
        company = company_result.scalar_one_or_none()
        if company and not company.primary_industry:
            company.primary_industry = section_result["industry"]

    # Replace findings for this section's modules, keep findings from other modules
    new_finding_modules = set()
    for f in section_result["key_findings"]:
        new_finding_modules.add(f["module"])

    existing_findings = diagnostic.key_findings or []
    # Keep findings from other modules
    kept_findings = [f for f in existing_findings if f.get("module") not in new_finding_modules]
    diagnostic.key_findings = kept_findings + section_result["key_findings"]

    # Generate AI analysis for this section.
    # Pass the latest enterprise_stage so non-A modules get stage-aware advice.
    try:
        analysis = await generate_section_analysis(
            diagnostic.answers,
            section_key,
            section_result,
            enterprise_stage=diagnostic.enterprise_stage,
        )
        meta.setdefault("section_analyses", {})[section_key] = analysis
    except Exception:
        pass  # Non-critical, don't block scoring

    # Track submitted sections
    if section_key not in sections_submitted:
        sections_submitted.append(section_key)
    meta["sections_submitted"] = sections_submitted
    meta.setdefault("section_submitted_at", {})[section_key] = (
        datetime.now(timezone.utc).isoformat()
    )
    diagnostic.module_scores["_meta"] = meta

    # Recalculate overall score from available modules
    overall = recalculate_overall(diagnostic.module_scores)
    diagnostic.overall_score = overall["overall_score"]
    diagnostic.overall_rating = overall["overall_rating"]
    diagnostic.capital_readiness = overall["capital_readiness"]

    # Set timestamps and status
    if not diagnostic.submitted_at:
        diagnostic.submitted_at = datetime.now(timezone.utc)

    all_submitted = all(s in sections_submitted for s in SECTION_ORDER)
    if all_submitted:
        diagnostic.status = DiagnosticStatus.completed
        diagnostic.scored_at = datetime.now(timezone.utc)
    else:
        diagnostic.status = DiagnosticStatus.submitted

    diagnostic.error_message = None
    diagnostic.progress_message = None

    # Flag JSONB columns as modified for SQLAlchemy
    flag_modified(diagnostic, "module_scores")
    flag_modified(diagnostic, "key_findings")
    flag_modified(diagnostic, "answers")
    if other_answers is not None:
        flag_modified(diagnostic, "other_answers")

    await db.flush()
    return diagnostic


async def get_diagnostic(
    db: AsyncSession,
    diagnostic_id: uuid.UUID,
) -> Diagnostic | None:
    result = await db.execute(
        select(Diagnostic).where(Diagnostic.id == diagnostic_id)
    )
    return result.scalar_one_or_none()


async def list_diagnostics(
    db: AsyncSession,
    company_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> list[Diagnostic]:
    """List diagnostics, optionally filtered by company or user."""
    query = select(Diagnostic).order_by(Diagnostic.created_at.desc())
    if company_id:
        query = query.where(Diagnostic.company_id == company_id)
    if user_id:
        query = query.where(Diagnostic.user_id == user_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_all_diagnostics(db: AsyncSession) -> list[Diagnostic]:
    """List all diagnostics (for advisor dashboard)."""
    query = select(Diagnostic).order_by(Diagnostic.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())
