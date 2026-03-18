"""
Builds rich context strings for the chat system prompt by fetching
company profile, intake data, assessment scores, flags, reports, and research.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import Assessment, AutoFlag, ModuleScore
from app.models.company import Company
from app.models.intake import IntakeStage
from app.models.report import Report, ReportSection
from app.models.research import CompanyResearch, ResearchStatus

logger = logging.getLogger(__name__)


async def build_chat_context(db: AsyncSession, company_id: uuid.UUID) -> str:
    """Fetch all relevant company data and return a formatted context string
    that is injected into the Claude system prompt.

    Sections:
    1. Company profile
    2. Latest intake data (Stage 1/2/3 summaries)
    3. Latest assessment scores (module + dimension)
    4. Auto-flags
    5. Report sections (if any)
    6. Research data (if any)
    """
    parts: list[str] = []

    # ----- 1. Company profile -----
    company = await _fetch_company(db, company_id)
    if company:
        parts.append(_format_company_profile(company))
    else:
        parts.append("## Company Profile\nCompany data not found.\n")

    # ----- 2. Intake data -----
    intake_stages = await _fetch_intake_stages(db, company_id)
    if intake_stages:
        parts.append(_format_intake_data(intake_stages))

    # ----- 3. Assessment scores -----
    assessment = await _fetch_latest_assessment(db, company_id)
    if assessment:
        parts.append(_format_assessment(assessment))

    # ----- 4. Auto-flags -----
    if assessment:
        flags = await _fetch_flags(db, assessment.id)
        if flags:
            parts.append(_format_flags(flags))

    # ----- 5. Report sections -----
    report = await _fetch_latest_report(db, company_id)
    if report:
        parts.append(_format_report(report))

    # ----- 6. Research data -----
    research = await _fetch_latest_research(db, company_id)
    if research:
        parts.append(_format_research(research))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

async def _fetch_company(db: AsyncSession, company_id: uuid.UUID) -> Company | None:
    result = await db.execute(select(Company).where(Company.id == company_id))
    return result.scalar_one_or_none()


async def _fetch_intake_stages(db: AsyncSession, company_id: uuid.UUID) -> list[IntakeStage]:
    result = await db.execute(
        select(IntakeStage)
        .where(IntakeStage.company_id == company_id)
        .order_by(IntakeStage.stage)
    )
    return list(result.scalars().all())


async def _fetch_latest_assessment(db: AsyncSession, company_id: uuid.UUID) -> Assessment | None:
    result = await db.execute(
        select(Assessment)
        .options(
            selectinload(Assessment.module_scores).selectinload(ModuleScore.dimension_scores),
        )
        .where(Assessment.company_id == company_id)
        .order_by(Assessment.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _fetch_flags(db: AsyncSession, assessment_id: uuid.UUID) -> list[AutoFlag]:
    result = await db.execute(
        select(AutoFlag).where(AutoFlag.assessment_id == assessment_id)
    )
    return list(result.scalars().all())


async def _fetch_latest_report(db: AsyncSession, company_id: uuid.UUID) -> Report | None:
    result = await db.execute(
        select(Report)
        .options(selectinload(Report.sections))
        .where(Report.company_id == company_id)
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _fetch_latest_research(db: AsyncSession, company_id: uuid.UUID) -> CompanyResearch | None:
    result = await db.execute(
        select(CompanyResearch)
        .where(
            CompanyResearch.company_id == company_id,
            CompanyResearch.status == ResearchStatus.completed,
        )
        .order_by(CompanyResearch.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _format_company_profile(company: Company) -> str:
    lines = [
        "## Company Profile",
        f"- **Legal Name**: {company.legal_name}",
        f"- **Registration Number**: {company.registration_number or 'N/A'}",
        f"- **Date of Incorporation**: {company.date_of_incorporation or 'N/A'}",
        f"- **Company Type**: {company.company_type or 'N/A'}",
        f"- **Primary Industry**: {company.primary_industry or 'N/A'}",
        f"- **Sub-Industry**: {company.sub_industry or 'N/A'}",
        f"- **Country**: {company.country}",
        f"- **Website**: {company.website or 'N/A'}",
        f"- **Enterprise Stage**: {company.enterprise_stage or 'N/A'}",
        f"- **Brief Description**: {company.brief_description or 'N/A'}",
    ]
    return "\n".join(lines)


def _format_intake_data(stages: list[IntakeStage]) -> str:
    lines = ["## Intake Data"]
    for stage in stages:
        lines.append(f"\n### Stage {stage.stage.value} (Status: {stage.status.value})")
        if stage.data:
            # Summarise key fields rather than dumping everything
            data = stage.data
            if isinstance(data, dict):
                for key, value in data.items():
                    # Truncate very long values
                    val_str = json.dumps(value, default=str) if not isinstance(value, str) else value
                    if len(val_str) > 500:
                        val_str = val_str[:497] + "..."
                    lines.append(f"- **{key}**: {val_str}")
        if stage.completed_sections:
            lines.append(f"- Completed sections: {', '.join(str(s) for s in stage.completed_sections)}")
    return "\n".join(lines)


def _format_assessment(assessment: Assessment) -> str:
    lines = [
        "## Latest Assessment Scores",
        f"- **Overall Score**: {assessment.overall_score}",
        f"- **Overall Rating**: {assessment.overall_rating or 'N/A'}",
        f"- **Capital Readiness**: {assessment.capital_readiness.value if assessment.capital_readiness else 'N/A'}",
        f"- **Enterprise Stage**: {assessment.enterprise_stage_classification or 'N/A'}",
    ]

    for ms in sorted(assessment.module_scores, key=lambda m: m.module_number):
        lines.append(
            f"\n### Module {ms.module_number}: {ms.module_name} "
            f"(Score: {ms.total_score}, Rating: {ms.rating}, Weight: {ms.weight})"
        )
        for ds in sorted(ms.dimension_scores, key=lambda d: d.dimension_number):
            lines.append(
                f"  - D{ds.dimension_number} {ds.dimension_name}: "
                f"Score={ds.score}, Weight={ds.weight}, Method={ds.scoring_method or 'N/A'}"
            )
            if ds.ai_reasoning:
                # Truncate long reasoning
                reasoning = ds.ai_reasoning
                if len(reasoning) > 300:
                    reasoning = reasoning[:297] + "..."
                lines.append(f"    Reasoning: {reasoning}")

    return "\n".join(lines)


def _format_flags(flags: list[AutoFlag]) -> str:
    lines = ["## Auto-Flags"]
    for f in flags:
        resolved = " (RESOLVED)" if f.is_resolved else ""
        lines.append(
            f"- [{f.severity.value.upper()}] {f.flag_type}: {f.description}{resolved}"
        )
    return "\n".join(lines)


def _format_report(report: Report) -> str:
    lines = [
        "## Current Report",
        f"- **Report Type**: {report.report_type.value}",
        f"- **Title**: {report.title}",
        f"- **Status**: {report.status.value}",
        f"- **Language**: {report.language.value}",
        f"- **Version**: {report.version}",
    ]

    if report.sections:
        lines.append("\n### Report Sections")
        for section in sorted(report.sections, key=lambda s: s.sort_order):
            lines.append(f"\n#### {section.section_title} (key: {section.section_key})")
            if section.content_en:
                content = section.content_en
                if len(content) > 800:
                    content = content[:797] + "..."
                lines.append(content)

    return "\n".join(lines)


def _format_research(research: CompanyResearch) -> str:
    lines = [
        "## Research Data",
        f"- **Research Type**: {research.research_type}",
        f"- **Research Date**: {research.research_date or 'N/A'}",
    ]

    if research.industry_data:
        lines.append(f"\n### Industry Data")
        lines.append(json.dumps(research.industry_data, indent=2, default=str)[:2000])

    if research.company_data:
        lines.append(f"\n### Company-Specific Data")
        lines.append(json.dumps(research.company_data, indent=2, default=str)[:2000])

    if research.peer_data:
        lines.append(f"\n### Peer/Competitor Data")
        lines.append(json.dumps(research.peer_data, indent=2, default=str)[:2000])

    return "\n".join(lines)
