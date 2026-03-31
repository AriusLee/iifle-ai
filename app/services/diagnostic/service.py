"""
Diagnostic service — handles CRUD, scoring, and report orchestration.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnostic import Diagnostic, DiagnosticStatus
from app.models.company import Company
from app.services.diagnostic.scoring import score_diagnostic


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
