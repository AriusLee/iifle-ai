"""
Chat tool definitions for Claude tool_use — allows the AI assistant to
edit report sections, retrieve company data, and search the web.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import Assessment, AutoFlag, ModuleScore
from app.models.intake import IntakeStage
from app.models.report import Report, ReportSection
from app.models.research import CompanyResearch, ResearchStatus
from app.services.ai.provider import get_ai_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool_use format)
# ---------------------------------------------------------------------------

CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "edit_report_section",
        "description": (
            "Edit a section of a company report. Use this when the user asks to "
            "modify, rewrite, or update a specific report section."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section_key": {
                    "type": "string",
                    "description": "The key identifying the report section (e.g. 'executive_summary', 'founder_analysis').",
                },
                "new_content_en": {
                    "type": "string",
                    "description": "The new English content for the section.",
                },
                "new_content_cn": {
                    "type": "string",
                    "description": "The new Chinese content for the section (optional).",
                },
            },
            "required": ["section_key", "new_content_en"],
        },
    },
    {
        "name": "get_company_data",
        "description": (
            "Retrieve company data including intake questionnaire responses, "
            "assessment scores, auto-flags, or research data. Use this to look up "
            "specific data points when answering the user's questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data_type": {
                    "type": "string",
                    "enum": ["intake", "scores", "flags", "research"],
                    "description": "The type of data to retrieve.",
                },
                "module_number": {
                    "type": "integer",
                    "description": "Optional module number to filter scores (1=Gene, 2=Business Model, etc.).",
                },
            },
            "required": ["data_type"],
        },
    },
    {
        "name": "search_web",
        "description": (
            "Search the web for information about the company, its industry, "
            "competitors, or market data. Use this when the user asks about "
            "external information not already in the system."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
            },
            "required": ["query"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    db: AsyncSession,
    company_id: uuid.UUID,
) -> str:
    """Dispatch a tool call to its handler and return the result as a string."""
    handlers = {
        "edit_report_section": _handle_edit_report_section,
        "get_company_data": _handle_get_company_data,
        "search_web": _handle_search_web,
    }

    handler = handlers.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = await handler(tool_input, db, company_id)
        return result
    except Exception as exc:
        logger.exception("Tool '%s' failed for company %s", tool_name, company_id)
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_edit_report_section(
    tool_input: dict[str, Any],
    db: AsyncSession,
    company_id: uuid.UUID,
) -> str:
    """Edit a report section's content."""
    section_key = tool_input["section_key"]
    new_content_en = tool_input["new_content_en"]
    new_content_cn = tool_input.get("new_content_cn")

    # Find the most recent report for this company
    report_result = await db.execute(
        select(Report)
        .where(Report.company_id == company_id)
        .order_by(Report.created_at.desc())
        .limit(1)
    )
    report = report_result.scalar_one_or_none()

    if not report:
        return json.dumps({"error": "No report found for this company."})

    # Find the section
    section_result = await db.execute(
        select(ReportSection).where(
            ReportSection.report_id == report.id,
            ReportSection.section_key == section_key,
        )
    )
    section = section_result.scalar_one_or_none()

    if not section:
        return json.dumps({
            "error": f"Section '{section_key}' not found in the latest report."
        })

    # Update the section
    section.content_en = new_content_en
    if new_content_cn is not None:
        section.content_cn = new_content_cn
    section.is_ai_generated = True
    section.last_edited_at = datetime.now(timezone.utc)
    await db.flush()

    return json.dumps({
        "success": True,
        "section_key": section_key,
        "message": f"Section '{section.section_title}' has been updated successfully.",
    })


async def _handle_get_company_data(
    tool_input: dict[str, Any],
    db: AsyncSession,
    company_id: uuid.UUID,
) -> str:
    """Retrieve company data by type."""
    data_type = tool_input["data_type"]
    module_number = tool_input.get("module_number")

    if data_type == "intake":
        return await _get_intake_data(db, company_id)
    elif data_type == "scores":
        return await _get_scores_data(db, company_id, module_number)
    elif data_type == "flags":
        return await _get_flags_data(db, company_id)
    elif data_type == "research":
        return await _get_research_data(db, company_id)
    else:
        return json.dumps({"error": f"Unknown data_type: {data_type}"})


async def _handle_search_web(
    tool_input: dict[str, Any],
    db: AsyncSession,
    company_id: uuid.UUID,
) -> str:
    """Search the web using Claude's web search capability."""
    query = tool_input["query"]

    try:
        client = get_ai_client()
        # Fetch basic company context for the search
        from app.models.company import Company

        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()

        company_context = {}
        if company:
            company_context = {
                "company_name": company.legal_name,
                "industry": company.primary_industry or "",
                "country": company.country,
            }

        research = await client.research_web(query=query, company_context=company_context)
        return json.dumps(research, default=str)
    except Exception as exc:
        logger.warning("Web search failed: %s", exc)
        return json.dumps({"error": f"Web search failed: {exc}"})


# ---------------------------------------------------------------------------
# Data retrieval helpers
# ---------------------------------------------------------------------------

async def _get_intake_data(db: AsyncSession, company_id: uuid.UUID) -> str:
    """Retrieve all intake data for a company."""
    result = await db.execute(
        select(IntakeStage)
        .where(IntakeStage.company_id == company_id)
        .order_by(IntakeStage.stage)
    )
    stages = result.scalars().all()

    if not stages:
        return json.dumps({"message": "No intake data found."})

    data = {}
    for stage in stages:
        data[f"stage_{stage.stage.value}"] = {
            "status": stage.status.value,
            "data": stage.data or {},
            "completed_sections": stage.completed_sections or [],
        }

    return json.dumps(data, default=str)


async def _get_scores_data(
    db: AsyncSession,
    company_id: uuid.UUID,
    module_number: int | None = None,
) -> str:
    """Retrieve assessment scores for a company."""
    # Get latest assessment
    query = (
        select(Assessment)
        .options(
            selectinload(Assessment.module_scores).selectinload(ModuleScore.dimension_scores),
        )
        .where(Assessment.company_id == company_id)
        .order_by(Assessment.created_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    assessment = result.scalar_one_or_none()

    if not assessment:
        return json.dumps({"message": "No assessment scores found."})

    data: dict[str, Any] = {
        "overall_score": float(assessment.overall_score) if assessment.overall_score else None,
        "overall_rating": assessment.overall_rating,
        "capital_readiness": assessment.capital_readiness.value if assessment.capital_readiness else None,
        "modules": [],
    }

    for ms in sorted(assessment.module_scores, key=lambda m: m.module_number):
        if module_number is not None and ms.module_number != module_number:
            continue

        module_data: dict[str, Any] = {
            "module_number": ms.module_number,
            "module_name": ms.module_name,
            "total_score": float(ms.total_score) if ms.total_score else None,
            "rating": ms.rating,
            "weight": float(ms.weight),
            "dimensions": [],
        }

        for ds in sorted(ms.dimension_scores, key=lambda d: d.dimension_number):
            module_data["dimensions"].append({
                "dimension_number": ds.dimension_number,
                "dimension_name": ds.dimension_name,
                "score": float(ds.score) if ds.score else None,
                "weight": float(ds.weight),
                "scoring_method": ds.scoring_method,
                "ai_reasoning": ds.ai_reasoning,
            })

        data["modules"].append(module_data)

    return json.dumps(data, default=str)


async def _get_flags_data(db: AsyncSession, company_id: uuid.UUID) -> str:
    """Retrieve auto-flags for the latest assessment."""
    # Get latest assessment
    assessment_result = await db.execute(
        select(Assessment)
        .where(Assessment.company_id == company_id)
        .order_by(Assessment.created_at.desc())
        .limit(1)
    )
    assessment = assessment_result.scalar_one_or_none()

    if not assessment:
        return json.dumps({"message": "No assessment found."})

    flags_result = await db.execute(
        select(AutoFlag).where(AutoFlag.assessment_id == assessment.id)
    )
    flags = flags_result.scalars().all()

    data = [
        {
            "flag_type": f.flag_type,
            "severity": f.severity.value,
            "description": f.description,
            "source_field": f.source_field,
            "source_value": f.source_value,
            "is_resolved": f.is_resolved,
        }
        for f in flags
    ]

    return json.dumps(data, default=str)


async def _get_research_data(db: AsyncSession, company_id: uuid.UUID) -> str:
    """Retrieve the latest research data."""
    result = await db.execute(
        select(CompanyResearch)
        .where(
            CompanyResearch.company_id == company_id,
            CompanyResearch.status == ResearchStatus.completed,
        )
        .order_by(CompanyResearch.created_at.desc())
        .limit(1)
    )
    research = result.scalar_one_or_none()

    if not research:
        return json.dumps({"message": "No research data found."})

    data = {
        "research_type": research.research_type,
        "company_data": research.company_data,
        "industry_data": research.industry_data,
        "peer_data": research.peer_data,
        "sources": research.sources,
        "research_date": research.research_date,
    }

    return json.dumps(data, default=str)
