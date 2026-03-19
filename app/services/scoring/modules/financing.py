"""
Module 4: Financing Structure Scoring — 7 dimensions + investor recommendation.

Dimensions:
  D1: Enterprise Stage Readiness (PAT threshold)           — threshold  15%
  D2: Financial Track Record (audit + revenue + profit)    — checklist  20%
  D3: Cash Flow Health (operating CF + runway + CCC)       — threshold  15%
  D4: Equity Structure Clarity (8-item checklist)          — checklist  10%
  D5: Use-of-Proceeds Clarity (AI-judged)                  — ai        15%
  D6: Governance & Compliance (9-item checklist)           — checklist  15%
  D7: Documentation Readiness (10-item checklist)          — checklist  10%
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypedDict

from app.services.ai.provider import get_ai_client
from app.services.scoring.ai_scorer import AIScorer, DimensionResult
from app.services.scoring.rule_based import checklist_score, threshold_score

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
    total_score: float
    rating: str
    investor_recommendation: dict[str, Any]
    debt_equity_assessment: dict[str, Any]


# ---------------------------------------------------------------------------
# Dimension metadata
# ---------------------------------------------------------------------------

DIMENSIONS = [
    (1, "Enterprise Stage Readiness", 0.15, "threshold"),
    (2, "Financial Track Record", 0.20, "checklist"),
    (3, "Cash Flow Health", 0.15, "threshold"),
    (4, "Equity Structure Clarity", 0.10, "checklist"),
    (5, "Use-of-Proceeds Clarity", 0.15, "ai"),
    (6, "Governance & Compliance", 0.15, "checklist"),
    (7, "Documentation Readiness", 0.10, "checklist"),
]


def _rating(score: float) -> str:
    if score >= 80:
        return "Capital Ready"
    if score >= 65:
        return "Near Ready"
    if score >= 50:
        return "Developing"
    if score >= 35:
        return "Early Stage"
    return "Not Ready"


# ---------------------------------------------------------------------------
# D1: Enterprise Stage Readiness — PAT threshold
# ---------------------------------------------------------------------------

_PAT_READINESS = [
    (lambda v: v >= 8, 100),   # Main Market ready
    (lambda v: v >= 6, 85),    # Main Market approaching
    (lambda v: v >= 5, 75),    # ACE Market strong
    (lambda v: v >= 3, 60),    # ACE Market minimum
    (lambda v: v >= 1, 40),    # Pre-IPO
    (lambda v: v > 0, 25),     # Profitable but small
    (lambda _: True, 10),      # Loss-making
]

_REVENUE_SIZE = [
    (lambda v: v >= 100, 100),  # RM100M+
    (lambda v: v >= 50, 85),
    (lambda v: v >= 20, 70),
    (lambda v: v >= 10, 55),
    (lambda v: v >= 5, 40),
    (lambda _: True, 20),
]


def _score_d1(metrics: dict) -> DimensionScore:
    """D1: Enterprise Stage Readiness based on PAT and revenue size."""
    pat = metrics.get("pat_latest", 0) or 0
    rev = metrics.get("revenue_latest", 0) or 0
    pat_score = threshold_score(float(pat), _PAT_READINESS)
    rev_score = threshold_score(float(rev), _REVENUE_SIZE)
    score = round(pat_score * 0.60 + rev_score * 0.40)
    return DimensionScore(
        dimension_number=1, dimension_name="Enterprise Stage Readiness",
        score=float(score), weight=0.15, scoring_method="threshold",
        calculation_detail={
            "pat_latest": pat, "revenue_latest": rev,
            "pat_score": pat_score, "revenue_score": rev_score,
        },
        ai_reasoning=None,
    )


# ---------------------------------------------------------------------------
# D2: Financial Track Record
# ---------------------------------------------------------------------------

_D2_CHECKLIST = {
    "has_audited_3yr": {"yes": 25, "partial": 12, "no": 0},
    "revenue_consistent_growth": {"yes": 20, "partial": 10, "no": 0},
    "profitable_3yr": {"yes": 20, "partial": 10, "no": 0},
    "audit_opinion_clean": {"yes": 15, "partial": 8, "no": 0},
    "no_restatements": {"yes": 10, "partial": 5, "no": 0},
    "accounting_standard_mfrs": {"yes": 10, "partial": 5, "no": 0},
}


def _score_d2(intake_data: dict, metrics: dict) -> DimensionScore:
    """D2: Financial Track Record — audit history + revenue consistency + profit quality."""
    audit = intake_data.get("audit", {})
    audit_info = audit.get("audit_info", {}) if isinstance(audit, dict) else {}

    items: dict[str, str] = {}

    # Audited 3 years
    years_audited = audit_info.get("years_audited", 0) if isinstance(audit_info, dict) else 0
    items["has_audited_3yr"] = "yes" if years_audited >= 3 else ("partial" if years_audited >= 1 else "no")

    # Revenue consistency
    rev_cagr = metrics.get("revenue_cagr_3yr")
    if rev_cagr is not None and rev_cagr > 5:
        items["revenue_consistent_growth"] = "yes"
    elif rev_cagr is not None and rev_cagr >= 0:
        items["revenue_consistent_growth"] = "partial"
    else:
        items["revenue_consistent_growth"] = "no"

    # Profitable 3 years
    pat_cagr = metrics.get("pat_cagr_3yr")
    net_margin = metrics.get("net_margin_t0", 0) or 0
    if net_margin > 5 and (pat_cagr is None or pat_cagr > 0):
        items["profitable_3yr"] = "yes"
    elif net_margin > 0:
        items["profitable_3yr"] = "partial"
    else:
        items["profitable_3yr"] = "no"

    # Audit opinion
    opinion = audit_info.get("audit_opinion", "unknown") if isinstance(audit_info, dict) else "unknown"
    items["audit_opinion_clean"] = "yes" if opinion == "unqualified" else (
        "partial" if opinion in ("qualified",) else "no"
    )

    # No restatements (assume yes if clean audit)
    items["no_restatements"] = "yes" if opinion == "unqualified" else "partial"

    # Accounting standard
    standard = audit_info.get("accounting_standard", "unknown") if isinstance(audit_info, dict) else "unknown"
    items["accounting_standard_mfrs"] = "yes" if standard in ("mfrs", "ifrs") else (
        "partial" if standard == "mpers" else "no"
    )

    score = checklist_score(items, _D2_CHECKLIST)
    return DimensionScore(
        dimension_number=2, dimension_name="Financial Track Record",
        score=float(score), weight=0.20, scoring_method="checklist",
        calculation_detail={"items": items},
        ai_reasoning=None,
    )


# ---------------------------------------------------------------------------
# D3: Cash Flow Health
# ---------------------------------------------------------------------------

_OCF_MARGIN = [
    (lambda v: v > 15, 100), (lambda v: v > 10, 85), (lambda v: v > 5, 70),
    (lambda v: v > 0, 50), (lambda _: True, 15),
]
_RUNWAY_MONTHS = [
    (lambda v: v > 18, 100), (lambda v: v > 12, 85), (lambda v: v > 6, 65),
    (lambda v: v > 3, 40), (lambda _: True, 15),
]
_CCC_SCORE = [
    (lambda v: v < 30, 100), (lambda v: v < 60, 80), (lambda v: v < 90, 60),
    (lambda v: v < 120, 40), (lambda _: True, 20),
]


def _score_d3(metrics: dict) -> DimensionScore:
    """D3: Cash Flow Health — operating CF margin + runway + CCC."""
    ocf = threshold_score(float(metrics.get("operating_cf_margin_t0", 0) or 0), _OCF_MARGIN)
    runway = threshold_score(float(metrics.get("cash_runway_months", 0) or 0), _RUNWAY_MONTHS)
    ccc = threshold_score(float(metrics.get("cash_conversion_cycle_t0", 999) or 999), _CCC_SCORE)
    score = round(ocf * 0.40 + runway * 0.30 + ccc * 0.30)
    return DimensionScore(
        dimension_number=3, dimension_name="Cash Flow Health",
        score=float(score), weight=0.15, scoring_method="threshold",
        calculation_detail={
            "ocf_margin_score": ocf, "runway_score": runway, "ccc_score": ccc,
            "operating_cf_margin": metrics.get("operating_cf_margin_t0"),
            "cash_runway_months": metrics.get("cash_runway_months"),
            "ccc": metrics.get("cash_conversion_cycle_t0"),
        },
        ai_reasoning=None,
    )


# ---------------------------------------------------------------------------
# D4: Equity Structure Clarity — 8-item checklist
# ---------------------------------------------------------------------------

_D4_CHECKLIST = {
    "shareholder_agreement_in_place": {"yes": 15, "partial": 8, "no": 0},
    "clean_cap_table": {"yes": 15, "partial": 8, "no": 0},
    "no_complex_instruments": {"yes": 10, "partial": 5, "no": 0},
    "paid_up_capital_adequate": {"yes": 10, "partial": 5, "no": 0},
    "no_nominee_structures": {"yes": 15, "partial": 8, "no": 0},
    "esos_plan_in_place": {"yes": 10, "partial": 5, "no": 0},
    "founder_majority_control": {"yes": 15, "partial": 8, "no": 0},
    "rpt_arms_length": {"yes": 10, "partial": 5, "no": 0},
}


def _score_d4(intake_data: dict) -> DimensionScore:
    """D4: Equity Structure Clarity — 8-item checklist."""
    funding = intake_data.get("funding", {}) or {}
    rpt = intake_data.get("related_party", {}) or {}

    items: dict[str, str] = {}
    items["shareholder_agreement_in_place"] = "yes" if funding.get("has_shareholder_agreement") else "no"
    items["esos_plan_in_place"] = "yes" if funding.get("has_esos_plan") else "no"
    items["no_complex_instruments"] = "no" if funding.get("has_convertible_instruments") else "yes"

    # Clean cap table: check if shareholders add up to ~100%
    shareholders = funding.get("current_shareholders", [])
    if shareholders:
        total_pct = sum(s.get("ownership_pct", 0) for s in shareholders if isinstance(s, dict))
        items["clean_cap_table"] = "yes" if 99 <= total_pct <= 101 else "partial"
    else:
        items["clean_cap_table"] = "no"

    # Paid up capital
    puc = funding.get("paid_up_capital")
    items["paid_up_capital_adequate"] = "yes" if puc and puc > 0 else "no"

    # Nominee structures — assume clean unless complex instruments
    items["no_nominee_structures"] = "yes" if not funding.get("has_convertible_instruments") else "partial"

    # Founder majority
    founder_pct = sum(
        s.get("ownership_pct", 0)
        for s in shareholders
        if isinstance(s, dict) and s.get("type") in ("founder", "co_founder")
    )
    items["founder_majority_control"] = "yes" if founder_pct > 50 else ("partial" if founder_pct > 30 else "no")

    # RPT arms length
    if rpt.get("has_related_party_transactions"):
        txns = rpt.get("transactions", [])
        arms_length = all(
            t.get("is_arms_length") == "yes" for t in txns if isinstance(t, dict)
        ) if txns else False
        items["rpt_arms_length"] = "yes" if arms_length else "partial"
    else:
        items["rpt_arms_length"] = "yes"

    score = checklist_score(items, _D4_CHECKLIST)
    return DimensionScore(
        dimension_number=4, dimension_name="Equity Structure Clarity",
        score=float(score), weight=0.10, scoring_method="checklist",
        calculation_detail={"items": items, "founder_ownership_pct": founder_pct},
        ai_reasoning=None,
    )


# ---------------------------------------------------------------------------
# D5: Use-of-Proceeds Clarity — AI-judged
# ---------------------------------------------------------------------------

USE_OF_PROCEEDS_RUBRIC = """\
## Dimension 5: Use-of-Proceeds Clarity (Financing Structure)

### Scoring Rubric (AI-Judged)
| Score | Criteria |
|-------|---------|
| 90-100 | Clear, detailed use-of-proceeds with specific amounts per category; well-justified alignment with growth strategy; realistic timeline and milestones; ROI projections for each use category; strong strategic rationale |
| 70-89 | Clear use-of-proceeds with general categories; aligned with business strategy; reasonable timeline; some ROI consideration |
| 50-69 | General use-of-proceeds statement; some alignment with strategy; vague on specifics and timeline |
| 30-49 | Vague use-of-proceeds; lacks specific allocation; weak connection to growth strategy; no timeline |
| 0-29 | No use-of-proceeds articulated; or plans are unrealistic/contradictory |

### Input Data to Evaluate
- Capital intentions (raise amount, purpose)
- Growth plans and strategy
- Capex plans
- Budget and projections
- Current cash position and runway

Assess the clarity, specificity, strategic alignment, and credibility of the company's
use-of-proceeds plan. Score each factor and provide detailed reasoning.
"""


# ---------------------------------------------------------------------------
# D6: Governance & Compliance — 9-item checklist
# ---------------------------------------------------------------------------

_D6_CHECKLIST = {
    "audited_accounts": {"yes": 12, "partial": 6, "no": 0},
    "independent_board_member": {"yes": 12, "partial": 6, "no": 0},
    "proper_accounting_system": {"yes": 12, "partial": 6, "no": 0},
    "tax_compliance": {"yes": 12, "partial": 6, "no": 0},
    "statutory_filings_current": {"yes": 10, "partial": 5, "no": 0},
    "company_secretary_appointed": {"yes": 10, "partial": 5, "no": 0},
    "no_litigation_pending": {"yes": 10, "partial": 5, "no": 0},
    "regulatory_licenses_valid": {"yes": 12, "partial": 6, "no": 0},
    "anti_corruption_policy": {"yes": 10, "partial": 5, "no": 0},
}


def _score_d6(intake_data: dict, metrics: dict) -> DimensionScore:
    """D6: Governance & Compliance — 9-item checklist."""
    audit = intake_data.get("audit", {}) or {}
    audit_info = audit.get("audit_info", {}) if isinstance(audit, dict) else {}

    items: dict[str, str] = {}
    # Derive from available data
    items["audited_accounts"] = "yes" if (audit_info.get("has_audited_accounts") if isinstance(audit_info, dict) else False) else "no"
    items["proper_accounting_system"] = "yes" if (audit_info.get("accounting_standard") if isinstance(audit_info, dict) else None) in ("mfrs", "ifrs", "mpers") else "no"

    # These can't be fully determined from Stage 2 alone — use reasonable defaults
    items["independent_board_member"] = "partial"
    items["tax_compliance"] = "partial"
    items["statutory_filings_current"] = "partial"
    items["company_secretary_appointed"] = "partial"
    items["no_litigation_pending"] = "partial"
    items["regulatory_licenses_valid"] = "partial"
    items["anti_corruption_policy"] = "partial"

    score = checklist_score(items, _D6_CHECKLIST)
    return DimensionScore(
        dimension_number=6, dimension_name="Governance & Compliance",
        score=float(score), weight=0.15, scoring_method="checklist",
        calculation_detail={"items": items, "note": "Some items default to partial — full assessment requires Stage 3"},
        ai_reasoning=None,
    )


# ---------------------------------------------------------------------------
# D7: Documentation Readiness — 10-item checklist
# ---------------------------------------------------------------------------

_D7_CHECKLIST = {
    "audited_financial_statements": {"yes": 12, "partial": 6, "no": 0},
    "management_accounts": {"yes": 10, "partial": 5, "no": 0},
    "business_plan": {"yes": 10, "partial": 5, "no": 0},
    "financial_projections": {"yes": 10, "partial": 5, "no": 0},
    "shareholder_agreement": {"yes": 10, "partial": 5, "no": 0},
    "company_constitution": {"yes": 10, "partial": 5, "no": 0},
    "org_chart": {"yes": 8, "partial": 4, "no": 0},
    "cap_table": {"yes": 10, "partial": 5, "no": 0},
    "use_of_proceeds_doc": {"yes": 10, "partial": 5, "no": 0},
    "key_contracts": {"yes": 10, "partial": 5, "no": 0},
}


def _score_d7(intake_data: dict) -> DimensionScore:
    """D7: Documentation Readiness — 10-item checklist."""
    audit = intake_data.get("audit", {}) or {}
    audit_info = audit.get("audit_info", {}) if isinstance(audit, dict) else {}
    funding = intake_data.get("funding", {}) or {}
    projections = intake_data.get("projections", {}) or {}

    items: dict[str, str] = {}
    items["audited_financial_statements"] = "yes" if (audit_info.get("has_audited_accounts") if isinstance(audit_info, dict) else False) else "no"
    items["financial_projections"] = "yes" if projections.get("projections") else "no"
    items["shareholder_agreement"] = "yes" if funding.get("has_shareholder_agreement") else "no"
    items["cap_table"] = "yes" if funding.get("current_shareholders") else "no"

    # Defaults for items we can't determine from Stage 2
    items["management_accounts"] = "partial"
    items["business_plan"] = "partial"
    items["company_constitution"] = "partial"
    items["org_chart"] = "partial"
    items["use_of_proceeds_doc"] = "partial"
    items["key_contracts"] = "partial"

    score = checklist_score(items, _D7_CHECKLIST)
    return DimensionScore(
        dimension_number=7, dimension_name="Documentation Readiness",
        score=float(score), weight=0.10, scoring_method="checklist",
        calculation_detail={"items": items},
        ai_reasoning=None,
    )


# ---------------------------------------------------------------------------
# Investor type recommendation
# ---------------------------------------------------------------------------

def _recommend_investor(metrics: dict, total_score: float) -> dict[str, Any]:
    """Recommend investor types based on company profile and financing readiness."""
    pat = float(metrics.get("pat_latest", 0) or 0)
    rev = float(metrics.get("revenue_latest", 0) or 0)
    roe = float(metrics.get("roe_t0", 0) or 0)

    recommendations = []
    primary = None

    # IPO readiness
    if pat >= 6 and total_score >= 70:
        recommendations.append({
            "type": "IPO",
            "market": "Bursa Main Market" if pat >= 8 else "Bursa ACE Market",
            "readiness": "high",
            "rationale": f"PAT RM{pat}M meets listing threshold; strong financing readiness score",
        })
        primary = "IPO"

    # PE
    if pat >= 3 and rev >= 20 and total_score >= 55:
        recommendations.append({
            "type": "Private Equity",
            "readiness": "high" if total_score >= 70 else "moderate",
            "rationale": "Sufficient scale and profitability for PE consideration",
        })
        if not primary:
            primary = "Private Equity"

    # VC
    if rev >= 5 and float(metrics.get("revenue_cagr_3yr", 0) or 0) > 20:
        recommendations.append({
            "type": "Venture Capital",
            "readiness": "high" if total_score >= 60 else "moderate",
            "rationale": "High growth profile attractive to VC investors",
        })
        if not primary:
            primary = "Venture Capital"

    # Strategic investor
    if rev >= 10:
        recommendations.append({
            "type": "Strategic Investor",
            "readiness": "moderate",
            "rationale": "Sufficient scale for strategic partnership or investment",
        })
        if not primary:
            primary = "Strategic Investor"

    # Bank / debt
    if float(metrics.get("current_ratio_t0", 0) or 0) > 1.2 and pat > 0:
        recommendations.append({
            "type": "Bank Financing",
            "readiness": "high" if float(metrics.get("interest_coverage_t0", 0) or 0) > 3 else "moderate",
            "rationale": "Adequate liquidity and profitability for bank consideration",
        })

    if not recommendations:
        recommendations.append({
            "type": "Angel / Friends & Family",
            "readiness": "moderate",
            "rationale": "Company is at early stage; institutional investors unlikely at current scale",
        })
        primary = "Angel / Friends & Family"

    return {
        "primary_recommendation": primary,
        "all_recommendations": recommendations,
    }


def _assess_debt_equity(metrics: dict) -> dict[str, Any]:
    """Assess optimal debt vs equity mix."""
    gearing = float(metrics.get("net_gearing_t0", 0) or 0)
    interest_cov = float(metrics.get("interest_coverage_t0", 0) or 0)
    ocf_margin = float(metrics.get("operating_cf_margin_t0", 0) or 0)
    roe = float(metrics.get("roe_t0", 0) or 0)

    if gearing < 30 and interest_cov > 5 and ocf_margin > 10:
        recommendation = "debt_capacity_available"
        detail = "Low leverage with strong cash flows — debt capacity available for growth financing"
    elif gearing < 60 and interest_cov > 3:
        recommendation = "balanced"
        detail = "Moderate leverage — consider balanced debt/equity mix"
    elif gearing > 100 or interest_cov < 1.5:
        recommendation = "equity_preferred"
        detail = "High leverage or weak debt servicing — equity funding preferred to deleverage"
    else:
        recommendation = "mixed"
        detail = "Review on case-by-case basis considering growth plans and market conditions"

    return {
        "recommendation": recommendation,
        "detail": detail,
        "current_gearing": gearing,
        "interest_coverage": interest_cov,
        "operating_cf_margin": ocf_margin,
    }


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class FinancingScorer:
    """Module 4: Financing Structure — 7 dimensions + investor recommendation."""

    def __init__(self, client=None) -> None:
        self._client = client or get_ai_client()
        self._ai_scorer = AIScorer(self._client)

    async def score(
        self,
        intake_data: dict[str, Any],
        metrics: dict[str, Any],
        research_data: dict[str, Any] | None = None,
        progress_callback: Callable | None = None,
    ) -> ModuleResult:
        """Run all 7 dimensions and produce the module result."""

        async def _progress(msg: str):
            if progress_callback:
                await progress_callback(f"Scoring Financing: {msg}")

        # Extract latest financials for D1
        inc = intake_data.get("income_statement", {}) or {}
        year_t0 = inc.get("year_t0", {}) or {}
        metrics_with_latest = {
            **metrics,
            "pat_latest": year_t0.get("profit_after_tax", 0),
            "revenue_latest": year_t0.get("total_revenue", 0),
        }

        # D1-D4: deterministic
        await _progress("Enterprise stage readiness...")
        d1 = _score_d1(metrics_with_latest)
        await _progress("Financial track record...")
        d2 = _score_d2(intake_data, metrics)
        await _progress("Cash flow health...")
        d3 = _score_d3(metrics)
        await _progress("Equity structure clarity...")
        d4 = _score_d4(intake_data)

        # D5: AI-judged
        await _progress("Use-of-proceeds clarity (AI analysis)...")
        d5 = await self._score_d5(intake_data, metrics)

        # D6-D7: checklist
        await _progress("Governance & compliance...")
        d6 = _score_d6(intake_data, metrics)
        await _progress("Documentation readiness...")
        d7 = _score_d7(intake_data)

        dimensions = [d1, d2, d3, d4, d5, d6, d7]

        # Weighted total
        total = sum(d["score"] * d["weight"] for d in dimensions)
        total_score = max(0.0, min(100.0, round(total, 2)))

        # Investor recommendation
        investor_rec = _recommend_investor(metrics_with_latest, total_score)
        debt_equity = _assess_debt_equity(metrics)

        return ModuleResult(
            module_number=4,
            module_name="Financing Structure",
            dimensions=dimensions,
            total_score=total_score,
            rating=_rating(total_score),
            investor_recommendation=investor_rec,
            debt_equity_assessment=debt_equity,
        )

    async def _score_d5(
        self,
        intake_data: dict[str, Any],
        metrics: dict[str, Any],
    ) -> DimensionScore:
        """D5: Use-of-Proceeds Clarity — AI-judged."""
        # Gather relevant input
        projections = intake_data.get("projections", {}) or {}
        funding = intake_data.get("funding", {}) or {}

        # Also look for Stage 1 capital intentions
        capital_intentions = intake_data.get("capital_intentions", {}) or {}
        growth_plans = intake_data.get("growth_plans", {}) or {}

        input_data = {
            "capital_intentions": capital_intentions,
            "growth_plans": growth_plans,
            "projections": projections.get("projections", []),
            "capex_plans": projections.get("capex_plans", []),
            "key_growth_drivers": projections.get("key_growth_drivers", []),
            "current_cash": metrics.get("cash_runway_months"),
            "revenue_latest": metrics.get("revenue_latest", 0),
            "total_raised": funding.get("total_raised_to_date"),
            "funding_rounds": funding.get("funding_rounds", []),
        }

        try:
            result = await self._client.score_dimension(
                dimension_name="Use-of-Proceeds Clarity",
                rubric=USE_OF_PROCEEDS_RUBRIC,
                input_data=input_data,
            )
            score = float(max(0, min(100, result.get("score", 50))))
            reasoning = result.get("reasoning", "")
        except Exception as exc:
            logger.warning("AI scoring for D5 failed: %s", exc)
            score = 50.0
            reasoning = f"AI scoring unavailable: {exc}"

        return DimensionScore(
            dimension_number=5, dimension_name="Use-of-Proceeds Clarity",
            score=score, weight=0.15, scoring_method="ai",
            calculation_detail={"ai_input_keys": list(input_data.keys())},
            ai_reasoning=reasoning,
        )
