"""
Module 1: Gene Structure Scoring — all 7 dimensions + checklist modifier.

Dimension weights: D1:15%, D2:15%, D3:15%, D4:15%, D5:10%, D6:15%, D7:15%
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from app.services.ai.provider import get_ai_client
from app.services.scoring.ai_scorer import AIScorer, DimensionResult
from app.services.scoring.rule_based import (
    gene_checklist_modifier,
    score_growth_potential,
    score_moat,
    score_replicability_checklist,
    score_team_foundation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class DimensionScore(TypedDict):
    dimension_number: int
    dimension_name: str
    score: float
    weight: float
    scoring_method: str
    calculation_detail: dict[str, Any]
    ai_reasoning: str | None


class ModuleResult(TypedDict):
    module_number: int
    module_name: str
    dimensions: list[DimensionScore]
    checklist_modifier: int
    total_score: float
    rating: str


# ---------------------------------------------------------------------------
# Dimension metadata
# ---------------------------------------------------------------------------

DIMENSIONS = [
    (1, "Founder & Leadership", 0.15, "ai"),
    (2, "Industry Positioning", 0.15, "ai+data"),
    (3, "Product Competitiveness", 0.15, "ai"),
    (4, "Enterprise Differentiation", 0.15, "ai+moat"),
    (5, "Replicability & Scalability", 0.10, "checklist"),
    (6, "Team Foundation", 0.15, "checklist+rubric"),
    (7, "Growth Potential", 0.15, "threshold"),
]


def _rating(score: float) -> str:
    """Gene Structure rating: Strong / Medium / Weak."""
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Medium"
    return "Weak"


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class GeneStructureScorer:
    """Orchestrates scoring for all 7 Gene Structure dimensions."""

    def __init__(self, client: AnthropicClient | None = None) -> None:
        self._client = client or get_ai_client()
        self._ai = AIScorer(self._client)

    async def score(
        self,
        intake_data: dict[str, Any],
        research_data: dict[str, Any] | None = None,
        progress_callback=None,
    ) -> ModuleResult:
        """Score all 7 dimensions sequentially with progress updates."""

        async def _progress(msg: str):
            if progress_callback:
                await progress_callback(f"Gene Structure: {msg}")

        await _progress("Analyzing Founder & Leadership...")
        d1 = await self._score_d1(intake_data)

        await _progress("Evaluating Industry Positioning...")
        d2 = await self._score_d2(intake_data, research_data)

        await _progress("Assessing Product Competitiveness...")
        d3 = await self._score_d3(intake_data)

        await _progress("Scoring Enterprise Differentiation...")
        d4 = await self._score_d4(intake_data)

        await _progress("Checking Replicability & Scalability...")
        d5 = self._score_d5(intake_data)

        await _progress("Evaluating Team Foundation...")
        d6 = self._score_d6(intake_data)

        await _progress("Calculating Growth Potential...")
        d7 = self._score_d7(intake_data)

        dimensions = [d1, d2, d3, d4, d5, d6, d7]

        # Checklist modifier
        checklist_items_met = self._count_checklist_items(intake_data)
        modifier = gene_checklist_modifier(checklist_items_met)

        # Weighted score
        weighted_sum = sum(d["score"] * d["weight"] for d in dimensions)
        total = max(0.0, min(100.0, weighted_sum + modifier))

        return ModuleResult(
            module_number=1,
            module_name="Gene Structure",
            dimensions=dimensions,
            checklist_modifier=modifier,
            total_score=round(total, 2),
            rating=_rating(total),
        )

    # ------------------------------------------------------------------
    # D1: Founder & Leadership (AI)
    # ------------------------------------------------------------------

    async def _score_d1(self, intake_data: dict[str, Any]) -> DimensionScore:
        try:
            result = await self._ai.score_founder_leadership(intake_data)
        except Exception as exc:
            logger.error("AI scoring failed for Gene D1: %s", exc)
            result = DimensionResult(score=50.0, reasoning=f"AI scoring failed: {exc}", sub_scores=None)

        return DimensionScore(
            dimension_number=1,
            dimension_name="Founder & Leadership",
            score=result["score"],
            weight=0.15,
            scoring_method="ai",
            calculation_detail={
                "sub_scores": result.get("sub_scores"),
                "method": "rubric_based_ai_judged",
            },
            ai_reasoning=result["reasoning"],
        )

    # ------------------------------------------------------------------
    # D2: Industry Positioning (AI + data)
    # ------------------------------------------------------------------

    async def _score_d2(
        self,
        intake_data: dict[str, Any],
        research_data: dict[str, Any] | None,
    ) -> DimensionScore:
        try:
            result = await self._ai.score_industry_positioning(intake_data, research_data)
        except Exception as exc:
            logger.error("AI scoring failed for Gene D2: %s", exc)
            result = DimensionResult(score=50.0, reasoning=f"AI scoring failed: {exc}", sub_scores=None)

        return DimensionScore(
            dimension_number=2,
            dimension_name="Industry Positioning",
            score=result["score"],
            weight=0.15,
            scoring_method="ai+data",
            calculation_detail={
                "sub_scores": result.get("sub_scores"),
                "method": "rubric_based_data_supported",
                "research_available": research_data is not None,
            },
            ai_reasoning=result["reasoning"],
        )

    # ------------------------------------------------------------------
    # D3: Product Competitiveness (AI + consistency bonus)
    # ------------------------------------------------------------------

    async def _score_d3(self, intake_data: dict[str, Any]) -> DimensionScore:
        try:
            result = await self._ai.score_product_competitiveness(intake_data)
        except Exception as exc:
            logger.error("AI scoring failed for Gene D3: %s", exc)
            result = DimensionResult(score=50.0, reasoning=f"AI scoring failed: {exc}", sub_scores=None)

        # Check consistency bonus from AI sub_scores or intake data
        score = result["score"]
        consistency_bonus = 0
        sub_scores = result.get("sub_scores") or {}
        if sub_scores.get("consistency_bonus_applied") or sub_scores.get("all_aligned"):
            consistency_bonus = 5
            score = min(100.0, score + consistency_bonus)

        return DimensionScore(
            dimension_number=3,
            dimension_name="Product Competitiveness",
            score=score,
            weight=0.15,
            scoring_method="ai",
            calculation_detail={
                "sub_scores": sub_scores,
                "consistency_bonus": consistency_bonus,
                "method": "rubric_based_ai_judged_with_consistency",
            },
            ai_reasoning=result["reasoning"],
        )

    # ------------------------------------------------------------------
    # D4: Enterprise Differentiation (AI + moat scoring)
    # ------------------------------------------------------------------

    async def _score_d4(self, intake_data: dict[str, Any]) -> DimensionScore:
        # If structured moat data is available, compute rule-based moat score
        moat_data = intake_data.get("moats") or {}
        rule_moat_score: int | None = None
        if moat_data and isinstance(moat_data, dict):
            rule_moat_score = score_moat(moat_data)

        try:
            result = await self._ai.score_enterprise_differentiation(intake_data)
        except Exception as exc:
            logger.error("AI scoring failed for Gene D4: %s", exc)
            result = DimensionResult(
                score=float(rule_moat_score) if rule_moat_score is not None else 50.0,
                reasoning=f"AI scoring failed: {exc}",
                sub_scores=None,
            )

        # Blend: if both available, take average weighted toward rule-based for consistency
        final_score = result["score"]
        if rule_moat_score is not None:
            final_score = round((result["score"] * 0.4) + (rule_moat_score * 0.6), 2)

        return DimensionScore(
            dimension_number=4,
            dimension_name="Enterprise Differentiation",
            score=max(0.0, min(100.0, final_score)),
            weight=0.15,
            scoring_method="ai+moat",
            calculation_detail={
                "ai_score": result["score"],
                "rule_moat_score": rule_moat_score,
                "blend_formula": "ai*0.4 + moat_rule*0.6" if rule_moat_score else "ai_only",
                "sub_scores": result.get("sub_scores"),
                "method": "rubric_based_with_moat_scoring",
            },
            ai_reasoning=result["reasoning"],
        )

    # ------------------------------------------------------------------
    # D5: Replicability & Scalability (checklist)
    # ------------------------------------------------------------------

    def _score_d5(self, intake_data: dict[str, Any]) -> DimensionScore:
        items = intake_data.get("replicability_checklist") or {}
        if not items:
            # Try to build from individual fields
            items = {
                "sops_documented": intake_data.get("sops_documented", "no"),
                "training_system": intake_data.get("training_system", "no"),
                "quality_control": intake_data.get("quality_control", "no"),
                "geographic_expansion": intake_data.get("geographic_expansion", "no"),
                "central_facility": intake_data.get("central_facility", "no"),
                "franchise_model_ready": intake_data.get("franchise_model_ready", "no"),
            }

        score = score_replicability_checklist(items, module="gene")

        return DimensionScore(
            dimension_number=5,
            dimension_name="Replicability & Scalability",
            score=float(score),
            weight=0.10,
            scoring_method="checklist",
            calculation_detail={
                "checklist_items": items,
                "method": "checklist_based",
            },
            ai_reasoning=None,
        )

    # ------------------------------------------------------------------
    # D6: Team Foundation (checklist + rubric)
    # ------------------------------------------------------------------

    def _score_d6(self, intake_data: dict[str, Any]) -> DimensionScore:
        org_data = intake_data.get("org_data") or {
            "org_chart": intake_data.get("org_chart", "none"),
            "key_positions": intake_data.get("key_positions", "major_gaps"),
        }
        talent_data = intake_data.get("talent_data") or {
            "de_cai_gang_alignment": intake_data.get("de_cai_gang_alignment", "none"),
            "training_program": intake_data.get("training_program", "none"),
            "employee_turnover": intake_data.get("employee_turnover", "high"),
        }
        culture_data = intake_data.get("culture_data") or {
            "vision_mission_values": intake_data.get("vision_mission_values", "none"),
            "equity_incentive": intake_data.get("equity_incentive", "none"),
        }

        score = score_team_foundation(org_data, talent_data, culture_data)

        return DimensionScore(
            dimension_number=6,
            dimension_name="Team Foundation",
            score=float(score),
            weight=0.15,
            scoring_method="checklist+rubric",
            calculation_detail={
                "org_data": org_data,
                "talent_data": talent_data,
                "culture_data": culture_data,
                "method": "checklist_rubric_hybrid",
            },
            ai_reasoning=None,
        )

    # ------------------------------------------------------------------
    # D7: Growth Potential (threshold)
    # ------------------------------------------------------------------

    def _score_d7(self, intake_data: dict[str, Any]) -> DimensionScore:
        revenue_cagr = float(intake_data.get("revenue_cagr", 0) or 0)
        pat_values = intake_data.get("pat_values") or intake_data.get("pat_trajectory") or []
        if not isinstance(pat_values, list):
            pat_values = []
        pat_values = [float(v) for v in pat_values if v is not None]

        capital_leverage = str(intake_data.get("capital_leverage", "low") or "low")

        score = score_growth_potential(revenue_cagr, pat_values, capital_leverage)

        return DimensionScore(
            dimension_number=7,
            dimension_name="Growth Potential",
            score=float(score),
            weight=0.15,
            scoring_method="threshold",
            calculation_detail={
                "revenue_cagr": revenue_cagr,
                "pat_values": pat_values,
                "capital_leverage": capital_leverage,
                "method": "threshold_based_quantitative",
            },
            ai_reasoning=None,
        )

    # ------------------------------------------------------------------
    # 9-item checklist helper
    # ------------------------------------------------------------------

    @staticmethod
    def _count_checklist_items(intake_data: dict[str, Any]) -> int:
        """Count how many of the 9 Gene assessment checklist items are met."""
        checklist = intake_data.get("gene_checklist") or {}
        if isinstance(checklist, dict):
            return sum(
                1 for v in checklist.values()
                if str(v).lower().strip() in ("yes", "true", "1", "met")
            )
        if isinstance(checklist, list):
            return sum(
                1 for v in checklist
                if str(v).lower().strip() in ("yes", "true", "1", "met")
            )
        # Fallback: try to count from individual known fields
        gene_items = [
            "founder_experience_adequate",
            "industry_growing",
            "product_differentiated",
            "moat_exists",
            "sops_documented",
            "team_complete",
            "growth_positive",
            "succession_plan",
            "management_stable",
        ]
        return sum(
            1 for item in gene_items
            if str(intake_data.get(item, "no")).lower().strip() in ("yes", "true", "1", "met")
        )
