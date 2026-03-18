"""
Scoring Engine Orchestrator — coordinates auto-flag detection and module scoring
for Stage 1 assessments, persists results, and computes the overall score.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import (
    Assessment,
    AssessmentStatus,
    AutoFlag,
    CapitalReadiness,
    DimensionScore as DimensionScoreModel,
    FlagSeverity,
    ModuleScore as ModuleScoreModel,
)
from app.models.intake import IntakeStage
from app.services.ai.provider import get_ai_client
from app.services.scoring.auto_flags import detect_stage1_flags
from app.services.scoring.modules.business_model import BusinessModelScorer
from app.services.scoring.modules.gene import GeneStructureScorer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage-weighted module aggregation tables
# ---------------------------------------------------------------------------

# Default weights (Stage 2.0+)
DEFAULT_MODULE_WEIGHTS: dict[int, float] = {
    1: 0.15,  # Gene Structure
    2: 0.20,  # Business Model
    3: 0.20,  # Valuation
    4: 0.15,  # Financing
    5: 0.10,  # Exit Mechanism
    6: 0.20,  # Listing Standards
}

# Early stage weights (Stage 1.0-2.0)
EARLY_STAGE_WEIGHTS: dict[int, float] = {
    1: 0.20,  # Gene — higher
    2: 0.25,  # Business Model — higher
    3: 0.20,  # Valuation
    4: 0.15,  # Financing
    5: 0.10,  # Exit
    6: 0.10,  # Listing — lower
}

# Late stage weights (Stage 3.0-4.0)
LATE_STAGE_WEIGHTS: dict[int, float] = {
    1: 0.10,  # Gene — lower
    2: 0.20,  # Business Model
    3: 0.20,  # Valuation
    4: 0.15,  # Financing
    5: 0.10,  # Exit
    6: 0.25,  # Listing — higher
}


def _overall_rating(score: float) -> str:
    """Map overall score to universal rating label."""
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Strong"
    if score >= 70:
        return "Good"
    if score >= 60:
        return "Satisfactory"
    if score >= 50:
        return "Below Average"
    if score >= 40:
        return "Weak"
    return "Critical"


def _capital_readiness(score: float) -> CapitalReadiness:
    if score >= 70:
        return CapitalReadiness.green
    if score >= 50:
        return CapitalReadiness.amber
    return CapitalReadiness.red


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ScoringEngine:
    """Orchestrates the full scoring pipeline for a company assessment."""

    def __init__(self, client: AnthropicClient | None = None) -> None:
        self._client = client or get_ai_client()
        self._gene_scorer = GeneStructureScorer(self._client)
        self._bm_scorer = BusinessModelScorer(self._client)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def score_stage1(
        self,
        company_id: uuid.UUID,
        intake_data: dict[str, Any],
        db: AsyncSession,
        assessment_id: uuid.UUID | None = None,
    ) -> Assessment:
        """Run Stage 1 scoring: auto-flags + Gene Structure + Business Model.

        If assessment_id is provided, uses that existing record. Otherwise creates a new one.
        """
        # 1. Get or create assessment record
        if assessment_id:
            from sqlalchemy import select as sa_select
            result = await db.execute(sa_select(Assessment).where(Assessment.id == assessment_id))
            assessment = result.scalar_one_or_none()
            if not assessment:
                assessment = Assessment(id=assessment_id, company_id=company_id, trigger_stage="1", status=AssessmentStatus.scoring)
                db.add(assessment)
            else:
                assessment.status = AssessmentStatus.scoring
            await db.flush()
        else:
            assessment = Assessment(
                id=uuid.uuid4(),
                company_id=company_id,
                trigger_stage="1",
                status=AssessmentStatus.scoring,
            )
            db.add(assessment)
            await db.flush()

        async def _update_progress(msg: str):
            """Update assessment progress message so frontend can show it."""
            assessment.progress_message = msg
            await db.flush()
            await db.commit()

        try:
            # 2. Auto-flag detection
            await _update_progress("Detecting risk flags...")
            flag_records = detect_stage1_flags(intake_data)

            # 3. Attempt web research (best-effort)
            await _update_progress("Gathering research data...")
            research_data = await self._try_research(intake_data)

            # 4. Score Gene Structure (sequential for progress tracking)
            await _update_progress("Scoring Gene Structure: Founder & Leadership...")
            gene_result = await self._gene_scorer.score(intake_data, research_data, progress_callback=_update_progress)

            # 5. Score Business Model
            await _update_progress("Scoring Business Model: Customer Analysis...")
            bm_result = await self._bm_scorer.score(intake_data, research_data, progress_callback=_update_progress)

            # 6. Persist module scores
            await _update_progress("Saving scores...")
            gene_module = self._create_module_score(assessment.id, gene_result)
            bm_module = self._create_module_score(assessment.id, bm_result)
            db.add(gene_module)
            db.add(bm_module)
            await db.flush()

            # 6. Persist dimension scores
            for dim in gene_result["dimensions"]:
                db.add(self._create_dimension_score(gene_module.id, dim))
            for dim in bm_result["dimensions"]:
                db.add(self._create_dimension_score(bm_module.id, dim))

            # 7. Persist auto-flags
            for flag in flag_records:
                db.add(AutoFlag(
                    id=uuid.uuid4(),
                    assessment_id=assessment.id,
                    company_id=company_id,
                    flag_type=flag["flag_type"],
                    severity=FlagSeverity(flag["severity"]),
                    description=flag["description"],
                    source_field=flag.get("source_field"),
                    source_value=flag.get("source_value"),
                    stage="1",
                ))

            # 8. Calculate overall score (Stage 1 only has modules 1 & 2)
            enterprise_stage = intake_data.get("enterprise_stage", "1.0")
            module_scores = [
                {"module_number": 1, "score": gene_result["total_score"], "weight": None},
                {"module_number": 2, "score": bm_result["total_score"], "weight": None},
            ]
            overall = self.calculate_overall_score(module_scores, enterprise_stage)

            # 9. Update assessment
            assessment.overall_score = Decimal(str(round(overall, 2)))
            assessment.overall_rating = _overall_rating(overall)
            assessment.enterprise_stage_classification = enterprise_stage
            assessment.capital_readiness = _capital_readiness(overall)
            assessment.status = AssessmentStatus.draft
            assessment.updated_at = datetime.now(timezone.utc)

            await db.flush()

            # 10. Auto-trigger report generation (best-effort)
            try:
                from app.services.report.generator import ReportGenerator

                generator = ReportGenerator(db)
                await generator.generate_module_report(assessment.id, 1, company_id)
                await generator.generate_module_report(assessment.id, 2, company_id)
                logger.info(
                    "Auto-generated Module 1 & 2 reports for assessment %s",
                    assessment.id,
                )
            except Exception as report_exc:
                logger.warning(
                    "Auto report generation failed for assessment %s (non-critical): %s",
                    assessment.id,
                    report_exc,
                )

        except Exception:
            assessment.status = AssessmentStatus.pending
            logger.exception("Scoring failed for company %s", company_id)
            raise

        return assessment

    # ------------------------------------------------------------------
    # Overall score calculation
    # ------------------------------------------------------------------

    def calculate_overall_score(
        self,
        module_scores: list[dict[str, Any]],
        enterprise_stage: str,
    ) -> float:
        """Compute weighted overall score across available modules.

        *module_scores*: list of ``{"module_number": int, "score": float, "weight": float | None}``
        *enterprise_stage*: e.g. "1.0", "2.0", "3.5"
        """
        # Select weight table
        try:
            stage_num = float(enterprise_stage)
        except (TypeError, ValueError):
            stage_num = 1.0

        if stage_num >= 3.0:
            weight_table = LATE_STAGE_WEIGHTS
        elif stage_num <= 2.0:
            weight_table = EARLY_STAGE_WEIGHTS
        else:
            weight_table = DEFAULT_MODULE_WEIGHTS

        # Only include modules that have been scored
        scored_modules = {
            m["module_number"]: m["score"]
            for m in module_scores
            if m.get("score") is not None
        }

        if not scored_modules:
            return 0.0

        # Normalise weights to only scored modules
        total_weight = sum(
            weight_table.get(mn, 0.15) for mn in scored_modules
        )

        if total_weight == 0:
            return 0.0

        weighted_sum = sum(
            scored_modules[mn] * (weight_table.get(mn, 0.15) / total_weight)
            for mn in scored_modules
        )

        return max(0.0, min(100.0, round(weighted_sum, 2)))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _try_research(self, intake_data: dict[str, Any]) -> dict[str, Any] | None:
        """Best-effort web research. Returns None on failure."""
        company_name = intake_data.get("company_name") or intake_data.get("legal_name") or ""
        industry = intake_data.get("industry") or intake_data.get("primary_industry") or ""

        if not company_name and not industry:
            return None

        try:
            query = f"{company_name} {industry} Malaysia market industry analysis"
            return await self._client.research_web(
                query=query,
                company_context={
                    "company_name": company_name,
                    "industry": industry,
                    "country": intake_data.get("country", "Malaysia"),
                },
            )
        except Exception as exc:
            logger.warning("Web research failed (non-critical): %s", exc)
            return None

    @staticmethod
    def _create_module_score(assessment_id: uuid.UUID, result: dict[str, Any]) -> ModuleScoreModel:
        """Create a ModuleScore ORM instance from a module result dict."""
        # Determine weight based on module number
        module_num = result["module_number"]
        weight_map = {1: Decimal("0.150"), 2: Decimal("0.200")}  # Stage 1 defaults
        return ModuleScoreModel(
            id=uuid.uuid4(),
            assessment_id=assessment_id,
            module_number=module_num,
            module_name=result["module_name"],
            total_score=Decimal(str(round(result["total_score"], 2))),
            rating=result["rating"],
            weight=weight_map.get(module_num, Decimal("0.150")),
            scored_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _create_dimension_score(
        module_score_id: uuid.UUID,
        dim: dict[str, Any],
    ) -> DimensionScoreModel:
        """Create a DimensionScore ORM instance from a dimension dict."""
        return DimensionScoreModel(
            id=uuid.uuid4(),
            module_score_id=module_score_id,
            dimension_number=dim["dimension_number"],
            dimension_name=dim["dimension_name"],
            score=Decimal(str(round(dim["score"], 2))),
            weight=Decimal(str(dim["weight"])),
            scoring_method=dim.get("scoring_method"),
            calculation_detail=dim.get("calculation_detail"),
            ai_reasoning=dim.get("ai_reasoning"),
            input_data_snapshot=dim.get("calculation_detail"),
        )
