"""
ReportGenerator — generates AI-powered narrative reports for each module
by calling Claude for each report section, then persisting Report + ReportSection records.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import Assessment, ModuleScore
from app.models.company import Company
from app.models.intake import IntakeStage
from app.models.report import (
    Report,
    ReportLanguage,
    ReportSection,
    ReportStatus,
    ReportType,
)
from app.services.ai.client import AnthropicClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section definitions per module
# ---------------------------------------------------------------------------

MODULE_SECTIONS: dict[int, list[dict[str, str]]] = {
    1: [  # Gene Structure
        {"key": "executive_summary", "title": "Executive Summary"},
        {"key": "founder_analysis", "title": "Founder & Key Person Analysis"},
        {"key": "industry_analysis", "title": "Industry & Market Analysis"},
        {"key": "product_analysis", "title": "Product & Service Analysis"},
        {"key": "differentiation_analysis", "title": "Differentiation & Competitive Advantage"},
        {"key": "replicability_analysis", "title": "Replicability & Scalability Analysis"},
        {"key": "team_analysis", "title": "Team & Organizational Analysis"},
        {"key": "growth_analysis", "title": "Growth Trajectory & Potential"},
        {"key": "recommendations", "title": "Recommendations & Action Items"},
    ],
    2: [  # Business Model
        {"key": "bm_executive_summary", "title": "Business Model Executive Summary"},
        {"key": "revenue_model_analysis", "title": "Revenue Model Analysis"},
        {"key": "cost_structure_analysis", "title": "Cost Structure & Unit Economics"},
        {"key": "customer_analysis", "title": "Customer Segmentation & Acquisition"},
        {"key": "value_proposition_analysis", "title": "Value Proposition Assessment"},
        {"key": "channel_analysis", "title": "Distribution & Channel Analysis"},
        {"key": "scalability_analysis", "title": "Scalability & Margin Expansion"},
        {"key": "financial_sustainability", "title": "Financial Sustainability Outlook"},
        {"key": "bm_recommendations", "title": "Business Model Recommendations"},
    ],
    3: [  # Valuation
        {"key": "val_executive_summary", "title": "Valuation Executive Summary"},
        {"key": "valuation_methodology", "title": "Valuation Methodology"},
        {"key": "comparable_analysis", "title": "Comparable Company Analysis"},
        {"key": "dcf_analysis", "title": "DCF / Intrinsic Value Analysis"},
        {"key": "valuation_range", "title": "Valuation Range & Sensitivity"},
        {"key": "val_recommendations", "title": "Valuation Recommendations"},
    ],
    4: [  # Financing
        {"key": "fin_executive_summary", "title": "Financing Executive Summary"},
        {"key": "capital_needs_analysis", "title": "Capital Needs Assessment"},
        {"key": "funding_options", "title": "Funding Options & Strategy"},
        {"key": "debt_equity_analysis", "title": "Debt vs Equity Analysis"},
        {"key": "investor_readiness", "title": "Investor Readiness Assessment"},
        {"key": "fin_recommendations", "title": "Financing Recommendations"},
    ],
    5: [  # Exit Mechanism
        {"key": "exit_executive_summary", "title": "Exit Mechanism Executive Summary"},
        {"key": "exit_options", "title": "Exit Options Analysis"},
        {"key": "timeline_analysis", "title": "Exit Timeline & Milestones"},
        {"key": "exit_recommendations", "title": "Exit Recommendations"},
    ],
    6: [  # Listing Standards
        {"key": "listing_executive_summary", "title": "Listing Standards Executive Summary"},
        {"key": "exchange_analysis", "title": "Target Exchange Analysis"},
        {"key": "compliance_gap", "title": "Compliance Gap Assessment"},
        {"key": "listing_readiness", "title": "Listing Readiness Score"},
        {"key": "listing_recommendations", "title": "Listing Recommendations"},
    ],
}

MODULE_TYPE_MAP: dict[int, ReportType] = {
    1: ReportType.module_1,
    2: ReportType.module_2,
    3: ReportType.module_3,
    4: ReportType.module_4,
    5: ReportType.module_5,
    6: ReportType.module_6,
}

MODULE_TITLE_MAP: dict[int, str] = {
    1: "Gene Structure Assessment Report",
    2: "Business Model Assessment Report",
    3: "Valuation Assessment Report",
    4: "Financing Strategy Report",
    5: "Exit Mechanism Report",
    6: "Listing Standards Report",
}


class ReportGenerator:
    """Generates AI narrative reports for a given assessment module."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = AnthropicClient()

    async def generate_module_report(
        self,
        assessment_id: uuid.UUID,
        module_number: int,
        company_id: uuid.UUID,
    ) -> Report:
        """Generate a full report for a specific module.

        Creates a Report record in 'generating' status, generates each section
        narrative via Claude, persists ReportSection records, and sets status to 'draft'.
        """
        sections_def = MODULE_SECTIONS.get(module_number)
        if not sections_def:
            raise ValueError(f"No section definitions for module {module_number}")

        report_type = MODULE_TYPE_MAP.get(module_number)
        if not report_type:
            raise ValueError(f"Unknown module number: {module_number}")

        title = MODULE_TITLE_MAP.get(module_number, f"Module {module_number} Report")

        # 1. Create report record
        report = Report(
            id=uuid.uuid4(),
            assessment_id=assessment_id,
            company_id=company_id,
            report_type=report_type,
            title=title,
            status=ReportStatus.generating,
            language=ReportLanguage.bilingual,
            version=1,
        )
        self._db.add(report)
        await self._db.flush()

        try:
            # 2. Build context for narrative generation
            context = await self._build_report_context(assessment_id, module_number, company_id)

            # 3. Fetch module scores for the narrative
            scores = await self._fetch_module_scores(assessment_id, module_number)

            # 4. Generate each section
            for idx, section_def in enumerate(sections_def):
                try:
                    narrative = await self.generate_section_narrative(
                        section_key=section_def["key"],
                        context=context,
                        scores=scores,
                        language="bilingual",
                    )

                    section = ReportSection(
                        id=uuid.uuid4(),
                        report_id=report.id,
                        section_key=section_def["key"],
                        section_title=section_def["title"],
                        content_en=narrative.get("content_en", ""),
                        content_cn=narrative.get("content_cn"),
                        content_data={"scores_snapshot": scores},
                        sort_order=idx,
                        is_ai_generated=True,
                    )
                    self._db.add(section)

                except Exception as exc:
                    logger.error(
                        "Failed to generate section '%s' for report %s: %s",
                        section_def["key"],
                        report.id,
                        exc,
                    )
                    # Create a placeholder section so the report is still usable
                    section = ReportSection(
                        id=uuid.uuid4(),
                        report_id=report.id,
                        section_key=section_def["key"],
                        section_title=section_def["title"],
                        content_en=f"[Generation failed — please regenerate this section or write manually.]\n\nError: {exc}",
                        content_cn=None,
                        sort_order=idx,
                        is_ai_generated=False,
                    )
                    self._db.add(section)

            # 5. Mark report as draft
            report.status = ReportStatus.draft
            await self._db.flush()

        except Exception:
            report.status = ReportStatus.draft  # Still save as draft even on partial failure
            await self._db.flush()
            logger.exception("Report generation partially failed for module %d", module_number)
            raise

        return report

    async def generate_section_narrative(
        self,
        section_key: str,
        context: dict[str, Any],
        scores: dict[str, Any],
        language: str = "bilingual",
    ) -> dict[str, str]:
        """Generate narrative text for a single report section.

        Uses AnthropicClient.generate_narrative for each language,
        then returns both English and Chinese content.
        """
        # Merge scores into context
        generation_context = {**context, "scores": scores, "section_key": section_key}

        if language == "bilingual":
            # Generate English
            content_en = await self._client.generate_narrative(
                section_name=section_key,
                context=generation_context,
                language="en",
            )
            # Generate Chinese
            content_cn = await self._client.generate_narrative(
                section_name=section_key,
                context=generation_context,
                language="zh",
            )
            return {"content_en": content_en, "content_cn": content_cn}
        elif language == "en":
            content_en = await self._client.generate_narrative(
                section_name=section_key,
                context=generation_context,
                language="en",
            )
            return {"content_en": content_en, "content_cn": None}
        else:
            content_cn = await self._client.generate_narrative(
                section_name=section_key,
                context=generation_context,
                language="zh",
            )
            return {"content_en": None, "content_cn": content_cn}

    # ------------------------------------------------------------------
    # Context / data helpers
    # ------------------------------------------------------------------

    async def _build_report_context(
        self,
        assessment_id: uuid.UUID,
        module_number: int,
        company_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Build a context dict for the narrative generator."""
        context: dict[str, Any] = {}

        # Company profile
        company_result = await self._db.execute(
            select(Company).where(Company.id == company_id)
        )
        company = company_result.scalar_one_or_none()
        if company:
            context["company"] = {
                "legal_name": company.legal_name,
                "primary_industry": company.primary_industry,
                "sub_industry": company.sub_industry,
                "country": company.country,
                "enterprise_stage": company.enterprise_stage,
                "brief_description": company.brief_description,
            }

        # Intake data
        intake_result = await self._db.execute(
            select(IntakeStage)
            .where(IntakeStage.company_id == company_id)
            .order_by(IntakeStage.stage)
        )
        intakes = intake_result.scalars().all()
        context["intake"] = {}
        for intake in intakes:
            context["intake"][f"stage_{intake.stage.value}"] = intake.data or {}

        # Assessment-level info
        assessment_result = await self._db.execute(
            select(Assessment).where(Assessment.id == assessment_id)
        )
        assessment = assessment_result.scalar_one_or_none()
        if assessment:
            context["assessment"] = {
                "overall_score": float(assessment.overall_score) if assessment.overall_score else None,
                "overall_rating": assessment.overall_rating,
                "capital_readiness": assessment.capital_readiness.value if assessment.capital_readiness else None,
            }

        context["module_number"] = module_number

        return context

    async def _fetch_module_scores(
        self,
        assessment_id: uuid.UUID,
        module_number: int,
    ) -> dict[str, Any]:
        """Fetch module and dimension scores for the narrative."""
        result = await self._db.execute(
            select(ModuleScore)
            .options(selectinload(ModuleScore.dimension_scores))
            .where(
                ModuleScore.assessment_id == assessment_id,
                ModuleScore.module_number == module_number,
            )
        )
        ms = result.scalar_one_or_none()

        if not ms:
            return {"module_number": module_number, "total_score": None, "dimensions": []}

        return {
            "module_number": ms.module_number,
            "module_name": ms.module_name,
            "total_score": float(ms.total_score) if ms.total_score else None,
            "rating": ms.rating,
            "weight": float(ms.weight),
            "dimensions": [
                {
                    "dimension_number": ds.dimension_number,
                    "dimension_name": ds.dimension_name,
                    "score": float(ds.score) if ds.score else None,
                    "weight": float(ds.weight),
                    "scoring_method": ds.scoring_method,
                    "ai_reasoning": ds.ai_reasoning,
                }
                for ds in sorted(ms.dimension_scores, key=lambda d: d.dimension_number)
            ],
        }
