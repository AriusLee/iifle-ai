"""
Module 2: Business Model Structure Scoring — all 8 dimensions + red flags + 10x modifier.

Dimension weights: D1:15%, D2:20%, D3:15%, D4:10%, D5:10%, D6:15%, D7:10%, D8:5%
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

from app.services.ai.client import AnthropicClient
from app.services.scoring.ai_scorer import AIScorer, DimensionResult
from app.services.scoring.rule_based import (
    score_customer_concentration,
    score_customer_quality,
    score_efficiency_trend,
    score_gross_margin,
    score_net_margin,
    score_recurring_revenue,
    score_replicability_checklist,
    score_revenue_diversification,
    score_revenue_quality,
    score_yoy_revenue_growth,
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
    red_flag_deductions: list[dict[str, Any]]
    ten_x_modifier: int
    total_score: float
    rating: str


# ---------------------------------------------------------------------------
# Dimension metadata
# ---------------------------------------------------------------------------

DIMENSIONS = [
    (1, "Customer Analysis", 0.15, "threshold"),
    (2, "Revenue Model", 0.20, "threshold"),
    (3, "Profitability Structure", 0.15, "threshold"),
    (4, "Business Model Clarity", 0.10, "ai"),
    (5, "Replicability", 0.10, "checklist"),
    (6, "Scalability", 0.15, "ai"),
    (7, "Recurring Income", 0.10, "threshold"),
    (8, "Platform Potential", 0.05, "ai"),
]


def _rating(score: float) -> str:
    """Business Model rating: Mature / Developing / Early."""
    if score >= 80:
        return "Mature"
    if score >= 60:
        return "Developing"
    return "Early"


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class BusinessModelScorer:
    """Orchestrates scoring for all 8 Business Model dimensions."""

    def __init__(self, client: AnthropicClient | None = None) -> None:
        self._client = client or AnthropicClient()
        self._ai = AIScorer(self._client)

    async def score(
        self,
        intake_data: dict[str, Any],
        research_data: dict[str, Any] | None = None,
    ) -> ModuleResult:
        """Score all 8 dimensions and apply red flags / 10x modifier."""

        # Launch AI-scored dimensions in parallel
        ai_tasks = {
            4: asyncio.create_task(self._score_d4(intake_data)),
            6: asyncio.create_task(self._score_d6(intake_data)),
            8: asyncio.create_task(self._score_d8(intake_data)),
        }

        # Rule-based dimensions
        d1 = self._score_d1(intake_data)
        d2 = self._score_d2(intake_data)
        d3 = self._score_d3(intake_data)
        d5 = self._score_d5(intake_data)
        d7 = self._score_d7(intake_data)

        # Await AI tasks
        d4 = await ai_tasks[4]
        d6 = await ai_tasks[6]
        d8 = await ai_tasks[8]

        dimensions = [d1, d2, d3, d4, d5, d6, d7, d8]

        # Weighted score
        weighted_sum = sum(d["score"] * d["weight"] for d in dimensions)

        # 10x Test Modifier (from D6 scalability AI result)
        ten_x_modifier = self._extract_10x_modifier(d6)

        # Red flag deductions
        red_flags = self._detect_red_flags(intake_data)
        total_deductions = sum(rf["deduction"] for rf in red_flags)

        total = max(0.0, min(100.0, weighted_sum + ten_x_modifier - total_deductions))

        return ModuleResult(
            module_number=2,
            module_name="Business Model",
            dimensions=dimensions,
            red_flag_deductions=red_flags,
            ten_x_modifier=ten_x_modifier,
            total_score=round(total, 2),
            rating=_rating(total),
        )

    # ------------------------------------------------------------------
    # D1: Customer Analysis (threshold)
    # ------------------------------------------------------------------

    def _score_d1(self, intake_data: dict[str, Any]) -> DimensionScore:
        top1_pct = float(intake_data.get("top1_customer_pct", 50) or 50)
        top5_pct = float(intake_data.get("top5_customer_pct", 80) or 80)

        top1_score, top5_score = score_customer_concentration(top1_pct, top5_pct)

        quality_score = score_customer_quality(
            avg_relationship_years=_safe_float(intake_data.get("avg_customer_relationship_years")),
            retention_rate_pct=_safe_float(intake_data.get("customer_retention_rate_pct")),
            long_term_contracts=intake_data.get("long_term_contracts"),
        )

        # Weighted: top1 50%, top5 30%, quality 20%
        composite = (top1_score * 0.50) + (top5_score * 0.30) + (quality_score * 0.20)
        final = max(0.0, min(100.0, round(composite, 2)))

        return DimensionScore(
            dimension_number=1,
            dimension_name="Customer Analysis",
            score=final,
            weight=0.15,
            scoring_method="threshold",
            calculation_detail={
                "top1_customer_pct": top1_pct,
                "top1_score": top1_score,
                "top5_customer_pct": top5_pct,
                "top5_score": top5_score,
                "quality_score": quality_score,
                "weights": "top1:50%, top5:30%, quality:20%",
                "method": "threshold_and_rubric",
            },
            ai_reasoning=None,
        )

    # ------------------------------------------------------------------
    # D2: Revenue Model (threshold)
    # ------------------------------------------------------------------

    def _score_d2(self, intake_data: dict[str, Any]) -> DimensionScore:
        num_streams = int(intake_data.get("num_revenue_streams", 1) or 1)
        max_stream_pct = float(intake_data.get("max_revenue_stream_pct", 80) or 80)
        model_type = str(intake_data.get("revenue_model_type", "project_based") or "project_based")
        yoy_growth = float(intake_data.get("yoy_revenue_growth", 0) or 0)

        diversification = score_revenue_diversification(num_streams, max_stream_pct)
        quality = score_revenue_quality(model_type)
        growth = score_yoy_revenue_growth(yoy_growth)

        # Weighted: diversification 30%, quality 40%, growth 30%
        composite = (diversification * 0.30) + (quality * 0.40) + (growth * 0.30)
        final = max(0.0, min(100.0, round(composite, 2)))

        return DimensionScore(
            dimension_number=2,
            dimension_name="Revenue Model",
            score=final,
            weight=0.20,
            scoring_method="threshold",
            calculation_detail={
                "num_revenue_streams": num_streams,
                "max_revenue_stream_pct": max_stream_pct,
                "revenue_model_type": model_type,
                "yoy_revenue_growth": yoy_growth,
                "diversification_score": diversification,
                "quality_score": quality,
                "growth_score": growth,
                "weights": "diversification:30%, quality:40%, growth:30%",
                "method": "threshold_based",
            },
            ai_reasoning=None,
        )

    # ------------------------------------------------------------------
    # D3: Profitability Structure (threshold, industry-adjusted)
    # ------------------------------------------------------------------

    def _score_d3(self, intake_data: dict[str, Any]) -> DimensionScore:
        gross_margin_pct = float(intake_data.get("gross_margin_pct", 0) or 0)
        net_margin_pct = float(intake_data.get("net_margin_pct", 0) or 0)
        industry = str(intake_data.get("industry", intake_data.get("primary_industry", "services")) or "services")
        efficiency_cagr = float(intake_data.get("revenue_per_employee_cagr", 0) or 0)

        gm_score = score_gross_margin(gross_margin_pct, industry)
        nm_score = score_net_margin(net_margin_pct)
        eff_score = score_efficiency_trend(efficiency_cagr)

        # Weighted: gross margin 40%, net margin 30%, efficiency 30%
        composite = (gm_score * 0.40) + (nm_score * 0.30) + (eff_score * 0.30)
        final = max(0.0, min(100.0, round(composite, 2)))

        return DimensionScore(
            dimension_number=3,
            dimension_name="Profitability Structure",
            score=final,
            weight=0.15,
            scoring_method="threshold",
            calculation_detail={
                "gross_margin_pct": gross_margin_pct,
                "gross_margin_score": gm_score,
                "net_margin_pct": net_margin_pct,
                "net_margin_score": nm_score,
                "revenue_per_employee_cagr": efficiency_cagr,
                "efficiency_score": eff_score,
                "industry": industry,
                "weights": "gross_margin:40%, net_margin:30%, efficiency:30%",
                "method": "threshold_industry_adjusted",
            },
            ai_reasoning=None,
        )

    # ------------------------------------------------------------------
    # D4: Business Model Clarity (AI)
    # ------------------------------------------------------------------

    async def _score_d4(self, intake_data: dict[str, Any]) -> DimensionScore:
        try:
            result = await self._ai.score_business_model_clarity(intake_data)
        except Exception as exc:
            logger.error("AI scoring failed for BM D4: %s", exc)
            result = DimensionResult(score=50.0, reasoning=f"AI scoring failed: {exc}", sub_scores=None)

        return DimensionScore(
            dimension_number=4,
            dimension_name="Business Model Clarity",
            score=result["score"],
            weight=0.10,
            scoring_method="ai",
            calculation_detail={
                "sub_scores": result.get("sub_scores"),
                "method": "rubric_based_ai_judged",
            },
            ai_reasoning=result["reasoning"],
        )

    # ------------------------------------------------------------------
    # D5: Replicability (checklist)
    # ------------------------------------------------------------------

    def _score_d5(self, intake_data: dict[str, Any]) -> DimensionScore:
        items = intake_data.get("bm_replicability_checklist") or {}
        if not items:
            items = {
                "sops_documented": intake_data.get("sops_documented", "no"),
                "trainable_in_4_weeks": intake_data.get("trainable_in_4_weeks", "no"),
                "central_facility": intake_data.get("central_facility", "no"),
                "replicated_2_plus_locations": intake_data.get("replicated_2_plus_locations", "no"),
                "quality_consistent": intake_data.get("quality_consistent", "no"),
            }

        score = score_replicability_checklist(items, module="bm")

        return DimensionScore(
            dimension_number=5,
            dimension_name="Replicability",
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
    # D6: Scalability (AI + 10x modifier)
    # ------------------------------------------------------------------

    async def _score_d6(self, intake_data: dict[str, Any]) -> DimensionScore:
        try:
            result = await self._ai.score_scalability(intake_data)
        except Exception as exc:
            logger.error("AI scoring failed for BM D6: %s", exc)
            result = DimensionResult(score=50.0, reasoning=f"AI scoring failed: {exc}", sub_scores=None)

        return DimensionScore(
            dimension_number=6,
            dimension_name="Scalability",
            score=result["score"],
            weight=0.15,
            scoring_method="ai",
            calculation_detail={
                "sub_scores": result.get("sub_scores"),
                "method": "rubric_based_ai_judged_with_10x",
            },
            ai_reasoning=result["reasoning"],
        )

    # ------------------------------------------------------------------
    # D7: Recurring Income (threshold)
    # ------------------------------------------------------------------

    def _score_d7(self, intake_data: dict[str, Any]) -> DimensionScore:
        recurring_pct = float(intake_data.get("recurring_revenue_pct", 0) or 0)
        score = score_recurring_revenue(recurring_pct)

        return DimensionScore(
            dimension_number=7,
            dimension_name="Recurring Income",
            score=float(score),
            weight=0.10,
            scoring_method="threshold",
            calculation_detail={
                "recurring_revenue_pct": recurring_pct,
                "method": "threshold_based",
            },
            ai_reasoning=None,
        )

    # ------------------------------------------------------------------
    # D8: Platform Potential (AI)
    # ------------------------------------------------------------------

    async def _score_d8(self, intake_data: dict[str, Any]) -> DimensionScore:
        try:
            result = await self._ai.score_platform_potential(intake_data)
        except Exception as exc:
            logger.error("AI scoring failed for BM D8: %s", exc)
            result = DimensionResult(score=30.0, reasoning=f"AI scoring failed: {exc}", sub_scores=None)

        return DimensionScore(
            dimension_number=8,
            dimension_name="Platform Potential",
            score=result["score"],
            weight=0.05,
            scoring_method="ai",
            calculation_detail={
                "sub_scores": result.get("sub_scores"),
                "method": "rubric_based_ai_judged",
            },
            ai_reasoning=result["reasoning"],
        )

    # ------------------------------------------------------------------
    # 10x Test Modifier
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_10x_modifier(d6: DimensionScore) -> int:
        """Extract 10x test modifier from D6 Scalability AI sub_scores.

        Convention: sub_scores.ten_x_test = 100 → Yes (+5), 50 → Partial (0), 0 → No (-5)
        """
        sub_scores = (d6.get("calculation_detail") or {}).get("sub_scores") or {}
        ten_x = sub_scores.get("ten_x_test")
        if ten_x is None:
            return 0
        if isinstance(ten_x, (int, float)):
            if ten_x >= 80:
                return 5
            if ten_x <= 20:
                return -5
        return 0

    # ------------------------------------------------------------------
    # Red Flag Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_red_flags(intake_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Detect capital-market red flags and return deduction records."""
        flags: list[dict[str, Any]] = []

        # 1. Top 1 customer > 30%
        top1 = _safe_float(intake_data.get("top1_customer_pct"))
        if top1 is not None and top1 > 30:
            flags.append({
                "flag": "top1_customer_concentration",
                "description": f"Top 1 customer accounts for {top1:.0f}% of revenue (>30% threshold)",
                "deduction": 5,
                "source_field": "top1_customer_pct",
                "source_value": str(top1),
            })

        # 2. >80% one-time/project revenue
        model_type = str(intake_data.get("revenue_model_type", "") or "").lower()
        max_stream = _safe_float(intake_data.get("max_revenue_stream_pct"))
        if model_type in ("one_time", "project_based") and (max_stream is None or max_stream > 80):
            flags.append({
                "flag": "one_time_revenue_dependency",
                "description": ">80% revenue from one-time or project-based sources",
                "deduction": 5,
                "source_field": "revenue_model_type",
                "source_value": model_type,
            })

        # 3. Gross margin declining 3 consecutive years
        gm_trend = intake_data.get("gross_margin_trend") or []
        if isinstance(gm_trend, list) and len(gm_trend) >= 3:
            vals = [float(v) for v in gm_trend[-3:] if v is not None]
            if len(vals) == 3 and vals[0] > vals[1] > vals[2]:
                flags.append({
                    "flag": "gross_margin_declining",
                    "description": "Gross margin declining for 3 consecutive years",
                    "deduction": 3,
                    "source_field": "gross_margin_trend",
                    "source_value": str(vals),
                })

        # 4. Owner-dependent operations
        founder_roles = intake_data.get("founder_roles") or []
        if isinstance(founder_roles, list) and len(founder_roles) >= 3:
            flags.append({
                "flag": "owner_dependent_operations",
                "description": f"Founder holds {len(founder_roles)} key roles — owner-dependent operations",
                "deduction": 5,
                "source_field": "founder_roles",
                "source_value": str(founder_roles),
            })
        elif str(intake_data.get("key_person_dependency", "")).lower() in ("high", "critical"):
            flags.append({
                "flag": "owner_dependent_operations",
                "description": "High key-person dependency identified",
                "deduction": 5,
                "source_field": "key_person_dependency",
                "source_value": str(intake_data.get("key_person_dependency")),
            })

        # 5. No documented SOPs and >10 employees
        sops = str(intake_data.get("sops_documented", "no")).lower()
        headcount = _safe_float(intake_data.get("employee_count") or intake_data.get("headcount"))
        if sops == "no" and headcount is not None and headcount > 10:
            flags.append({
                "flag": "no_sops_with_headcount",
                "description": f"No documented SOPs with {int(headcount)} employees",
                "deduction": 3,
                "source_field": "sops_documented",
                "source_value": sops,
            })

        return flags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
