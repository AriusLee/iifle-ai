"""
Module 3: Valuation Scoring — 8-Star System + valuation methodology + ROE decomposition.

Stars:
  1. Growth (revenue CAGR + PAT CAGR)          — threshold
  2. Profitability (GP, EBIT, net, ROA, ROE)   — threshold
  3. Operational Efficiency (5 metrics)          — threshold
  4. Credit Standing (5 metrics)                 — threshold
  5. Consistency (CV across 12 metrics, 3yr)     — rule
  6. Sustainability (trend direction, 3yr)       — rule
  7. Ideal Position (12 absolute benchmarks)     — rule
  8. Industry Benchmark (peer comparison)        — ai

Each star is scored 0-100, then mapped to 0 or 1 (star earned if ≥60).
Module total = weighted average of all 8 star scores.

Weights: S1:15%, S2:20%, S3:15%, S4:15%, S5:10%, S6:10%, S7:10%, S8:5%
"""

from __future__ import annotations

import asyncio
import logging
import statistics
from typing import Any, Callable, TypedDict

from app.services.ai.provider import get_ai_client
from app.services.scoring.ai_scorer import AIScorer, DimensionResult
from app.services.scoring.rule_based import threshold_score

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
    stars_earned: int
    total_score: float
    rating: str
    valuation_method: str | None
    roe_decomposition: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Star metadata
# ---------------------------------------------------------------------------

STARS = [
    (1, "Growth", 0.15, "threshold"),
    (2, "Profitability", 0.20, "threshold"),
    (3, "Operational Efficiency", 0.15, "threshold"),
    (4, "Credit Standing", 0.15, "threshold"),
    (5, "Consistency", 0.10, "rule"),
    (6, "Sustainability", 0.10, "rule"),
    (7, "Ideal Position", 0.10, "rule"),
    (8, "Industry Benchmark", 0.05, "ai"),
]


def _rating(score: float, stars: int) -> str:
    if stars >= 7:
        return "Premium"
    if stars >= 5:
        return "Strong"
    if stars >= 3:
        return "Fair"
    if stars >= 1:
        return "Weak"
    return "Distressed"


# ---------------------------------------------------------------------------
# Threshold tables for Stars 1-4
# ---------------------------------------------------------------------------

_REVENUE_CAGR = [
    (lambda v: v > 30, 100), (lambda v: v > 20, 85), (lambda v: v > 10, 70),
    (lambda v: v > 5, 55), (lambda v: v >= 0, 35), (lambda _: True, 15),
]
_PAT_CAGR = [
    (lambda v: v > 40, 100), (lambda v: v > 25, 85), (lambda v: v > 15, 70),
    (lambda v: v > 5, 55), (lambda v: v >= 0, 35), (lambda _: True, 15),
]

# Star 2 sub-metrics
_GP_MARGIN = [
    (lambda v: v > 50, 100), (lambda v: v > 35, 85), (lambda v: v > 20, 70),
    (lambda v: v > 10, 50), (lambda v: v > 0, 30), (lambda _: True, 10),
]
_EBIT_MARGIN = [
    (lambda v: v > 25, 100), (lambda v: v > 15, 85), (lambda v: v > 10, 70),
    (lambda v: v > 5, 50), (lambda v: v > 0, 30), (lambda _: True, 10),
]
_NET_MARGIN = [
    (lambda v: v > 20, 100), (lambda v: v > 15, 85), (lambda v: v > 10, 70),
    (lambda v: v > 5, 50), (lambda v: v > 0, 30), (lambda _: True, 10),
]
_ROA = [
    (lambda v: v > 15, 100), (lambda v: v > 10, 85), (lambda v: v > 6, 70),
    (lambda v: v > 3, 50), (lambda v: v > 0, 30), (lambda _: True, 10),
]
_ROE = [
    (lambda v: v > 25, 100), (lambda v: v > 18, 85), (lambda v: v > 12, 70),
    (lambda v: v > 6, 50), (lambda v: v > 0, 30), (lambda _: True, 10),
]

# Star 3 sub-metrics
_ASSET_TURNOVER = [
    (lambda v: v > 2.0, 100), (lambda v: v > 1.5, 85), (lambda v: v > 1.0, 70),
    (lambda v: v > 0.5, 50), (lambda v: v > 0, 30), (lambda _: True, 10),
]
_INVENTORY_DAYS = [
    (lambda v: v < 30, 100), (lambda v: v < 60, 80), (lambda v: v < 90, 60),
    (lambda v: v < 120, 40), (lambda _: True, 20),
]
_RECEIVABLE_DAYS = [
    (lambda v: v < 30, 100), (lambda v: v < 60, 80), (lambda v: v < 90, 60),
    (lambda v: v < 120, 40), (lambda _: True, 20),
]
_PAYABLE_DAYS = [
    (lambda v: v > 60, 100), (lambda v: v > 45, 80), (lambda v: v > 30, 60),
    (lambda v: v > 15, 40), (lambda _: True, 20),
]
_CCC = [
    (lambda v: v < 30, 100), (lambda v: v < 60, 80), (lambda v: v < 90, 60),
    (lambda v: v < 120, 40), (lambda _: True, 20),
]

# Star 4 sub-metrics
_CURRENT_RATIO = [
    (lambda v: v > 2.5, 100), (lambda v: v > 2.0, 85), (lambda v: v > 1.5, 70),
    (lambda v: v > 1.0, 50), (lambda v: v > 0.5, 30), (lambda _: True, 10),
]
_INTEREST_COVERAGE = [
    (lambda v: v > 8, 100), (lambda v: v > 5, 85), (lambda v: v > 3, 70),
    (lambda v: v > 1.5, 50), (lambda v: v > 1, 30), (lambda _: True, 10),
]
_NET_GEARING = [
    (lambda v: v < 0, 100),   # net cash
    (lambda v: v < 30, 85), (lambda v: v < 60, 70),
    (lambda v: v < 100, 50), (lambda v: v < 150, 30), (lambda _: True, 10),
]
_DSCR = [
    (lambda v: v > 3, 100), (lambda v: v > 2, 85), (lambda v: v > 1.5, 70),
    (lambda v: v > 1, 50), (lambda v: v > 0.5, 30), (lambda _: True, 10),
]
_LEVERAGE = [
    (lambda v: v < 50, 100), (lambda v: v < 100, 85), (lambda v: v < 150, 70),
    (lambda v: v < 200, 50), (lambda v: v < 300, 30), (lambda _: True, 10),
]

# Star 7 ideal position benchmarks
_IDEAL_BENCHMARKS: list[tuple[str, Callable[[float], bool]]] = [
    ("revenue_cagr_3yr", lambda v: v > 15),
    ("pat_cagr_3yr", lambda v: v > 15),
    ("gross_margin_t0", lambda v: v > 30),
    ("net_margin_t0", lambda v: v > 10),
    ("roe_t0", lambda v: v > 15),
    ("roa_t0", lambda v: v > 8),
    ("current_ratio_t0", lambda v: v > 1.5),
    ("interest_coverage_t0", lambda v: v > 3),
    ("net_gearing_t0", lambda v: v < 60),
    ("asset_turnover_t0", lambda v: v > 1.0),
    ("cash_conversion_cycle_t0", lambda v: v < 60),
    ("operating_cf_margin_t0", lambda v: v > 10),
]


# ---------------------------------------------------------------------------
# Industry benchmark AI rubric
# ---------------------------------------------------------------------------

INDUSTRY_BENCHMARK_RUBRIC = """\
## Star 8: Industry Benchmark (Valuation Module)

### Scoring Rubric (AI-Judged, using peer comparison data)
| Score | Criteria |
|-------|---------|
| 90-100 | Company outperforms peers on 10+ of 12 metrics; top quartile across most benchmarks |
| 70-89 | Company outperforms peers on 7-9 metrics; above median on most benchmarks |
| 50-69 | Company is near industry median; performs well on some metrics but lags on others |
| 30-49 | Company underperforms peers on majority of metrics; below median on most benchmarks |
| 0-29 | Company significantly underperforms all or nearly all peers; bottom quartile |

### Metrics to Compare
Revenue growth, gross margin, net margin, ROE, ROA, current ratio, debt/equity,
asset turnover, receivable days, inventory days, cash conversion cycle, operating CF margin.

Use the peer comparison data and industry benchmarks provided.
Score the company's relative position vs peers and provide reasoning.
"""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _safe(metrics: dict, key: str, default: float = 0) -> float:
    v = metrics.get(key)
    if v is None:
        return default
    return float(v)


def _score_star1(metrics: dict) -> DimensionScore:
    """Star 1: Growth — revenue CAGR + PAT CAGR."""
    rev = threshold_score(_safe(metrics, "revenue_cagr_3yr"), _REVENUE_CAGR)
    pat = threshold_score(_safe(metrics, "pat_cagr_3yr"), _PAT_CAGR)
    score = round(rev * 0.50 + pat * 0.50)
    return DimensionScore(
        dimension_number=1, dimension_name="Growth",
        score=float(score), weight=0.15, scoring_method="threshold",
        calculation_detail={
            "revenue_cagr_score": rev, "pat_cagr_score": pat,
            "revenue_cagr": _safe(metrics, "revenue_cagr_3yr"),
            "pat_cagr": _safe(metrics, "pat_cagr_3yr"),
        },
        ai_reasoning=None,
    )


def _score_star2(metrics: dict) -> DimensionScore:
    """Star 2: Profitability — 5 metrics."""
    gp = threshold_score(_safe(metrics, "gross_margin_t0"), _GP_MARGIN)
    ebit = threshold_score(_safe(metrics, "ebit_margin_t0"), _EBIT_MARGIN)
    net = threshold_score(_safe(metrics, "net_margin_t0"), _NET_MARGIN)
    roa = threshold_score(_safe(metrics, "roa_t0"), _ROA)
    roe = threshold_score(_safe(metrics, "roe_t0"), _ROE)
    score = round(gp * 0.20 + ebit * 0.20 + net * 0.20 + roa * 0.20 + roe * 0.20)
    return DimensionScore(
        dimension_number=2, dimension_name="Profitability",
        score=float(score), weight=0.20, scoring_method="threshold",
        calculation_detail={
            "gp_margin_score": gp, "ebit_margin_score": ebit,
            "net_margin_score": net, "roa_score": roa, "roe_score": roe,
        },
        ai_reasoning=None,
    )


def _score_star3(metrics: dict) -> DimensionScore:
    """Star 3: Operational Efficiency — 5 metrics."""
    at = threshold_score(_safe(metrics, "asset_turnover_t0"), _ASSET_TURNOVER)
    inv = threshold_score(_safe(metrics, "inventory_days_t0", 999), _INVENTORY_DAYS)
    rec = threshold_score(_safe(metrics, "receivable_days_t0", 999), _RECEIVABLE_DAYS)
    pay = threshold_score(_safe(metrics, "payable_days_t0"), _PAYABLE_DAYS)
    ccc = threshold_score(_safe(metrics, "cash_conversion_cycle_t0", 999), _CCC)
    score = round(at * 0.20 + inv * 0.20 + rec * 0.20 + pay * 0.20 + ccc * 0.20)
    return DimensionScore(
        dimension_number=3, dimension_name="Operational Efficiency",
        score=float(score), weight=0.15, scoring_method="threshold",
        calculation_detail={
            "asset_turnover_score": at, "inventory_days_score": inv,
            "receivable_days_score": rec, "payable_days_score": pay, "ccc_score": ccc,
        },
        ai_reasoning=None,
    )


def _score_star4(metrics: dict) -> DimensionScore:
    """Star 4: Credit Standing — 5 metrics."""
    cr = threshold_score(_safe(metrics, "current_ratio_t0"), _CURRENT_RATIO)
    ic = threshold_score(_safe(metrics, "interest_coverage_t0"), _INTEREST_COVERAGE)
    ng = threshold_score(_safe(metrics, "net_gearing_t0", 999), _NET_GEARING)
    dscr = threshold_score(_safe(metrics, "dscr_t0"), _DSCR)
    lev = threshold_score(_safe(metrics, "debt_equity_t0", 999), _LEVERAGE)
    score = round(cr * 0.20 + ic * 0.20 + ng * 0.20 + dscr * 0.20 + lev * 0.20)
    return DimensionScore(
        dimension_number=4, dimension_name="Credit Standing",
        score=float(score), weight=0.15, scoring_method="threshold",
        calculation_detail={
            "current_ratio_score": cr, "interest_coverage_score": ic,
            "net_gearing_score": ng, "dscr_score": dscr, "leverage_score": lev,
        },
        ai_reasoning=None,
    )


def _score_star5(metrics_3yr: list[dict]) -> DimensionScore:
    """Star 5: Consistency — coefficient of variation across 12 metrics over 3yr.

    Lower CV = more consistent = higher score.
    """
    if len(metrics_3yr) < 2:
        return DimensionScore(
            dimension_number=5, dimension_name="Consistency",
            score=30.0, weight=0.10, scoring_method="rule",
            calculation_detail={"note": "Insufficient data (need 2+ years)"},
            ai_reasoning=None,
        )

    cv_metrics = [
        "gross_margin", "net_margin", "roe", "roa",
        "current_ratio", "asset_turnover", "receivable_days",
        "inventory_days", "payable_days", "revenue_yoy",
        "operating_cf_margin", "interest_coverage",
    ]

    cv_values = []
    detail: dict[str, float] = {}
    for metric_name in cv_metrics:
        values = []
        for yr_metrics in metrics_3yr:
            v = yr_metrics.get(metric_name)
            if v is not None and isinstance(v, (int, float)):
                values.append(float(v))
        if len(values) >= 2:
            mean = statistics.mean(values)
            if abs(mean) > 0.01:
                cv = statistics.stdev(values) / abs(mean)
                cv_values.append(cv)
                detail[f"cv_{metric_name}"] = round(cv, 4)

    if not cv_values:
        avg_cv = 1.0
    else:
        avg_cv = statistics.mean(cv_values)

    # Lower CV → higher score
    cv_thresholds = [
        (lambda v: v < 0.05, 100), (lambda v: v < 0.10, 85),
        (lambda v: v < 0.20, 70), (lambda v: v < 0.35, 55),
        (lambda v: v < 0.50, 40), (lambda _: True, 20),
    ]
    score = threshold_score(avg_cv, cv_thresholds)

    return DimensionScore(
        dimension_number=5, dimension_name="Consistency",
        score=float(score), weight=0.10, scoring_method="rule",
        calculation_detail={"avg_cv": round(avg_cv, 4), **detail},
        ai_reasoning=None,
    )


def _score_star6(metrics_3yr: list[dict]) -> DimensionScore:
    """Star 6: Sustainability — trend direction analysis over 3yr.

    Counts how many of 12 metrics are improving vs declining.
    """
    if len(metrics_3yr) < 2:
        return DimensionScore(
            dimension_number=6, dimension_name="Sustainability",
            score=30.0, weight=0.10, scoring_method="rule",
            calculation_detail={"note": "Insufficient data"},
            ai_reasoning=None,
        )

    # For these metrics, higher = better
    higher_better = [
        "gross_margin", "net_margin", "roe", "roa",
        "current_ratio", "asset_turnover", "interest_coverage",
        "operating_cf_margin",
    ]
    # For these metrics, lower = better
    lower_better = [
        "receivable_days", "inventory_days", "cash_conversion_cycle",
        "net_gearing",
    ]

    improving = 0
    stable = 0
    declining = 0
    detail: dict[str, str] = {}

    for metric in higher_better + lower_better:
        values = []
        for yr_metrics in metrics_3yr:
            v = yr_metrics.get(metric)
            if v is not None:
                values.append(float(v))
        if len(values) >= 2:
            trend = values[-1] - values[0]
            is_higher_better = metric in higher_better
            if abs(trend) < 0.5:
                stable += 1
                detail[metric] = "stable"
            elif (trend > 0 and is_higher_better) or (trend < 0 and not is_higher_better):
                improving += 1
                detail[metric] = "improving"
            else:
                declining += 1
                detail[metric] = "declining"

    total = improving + stable + declining
    if total == 0:
        score = 30.0
    else:
        # Score based on improvement ratio
        improve_ratio = (improving + stable * 0.5) / total
        score = round(improve_ratio * 100)

    return DimensionScore(
        dimension_number=6, dimension_name="Sustainability",
        score=float(max(0, min(100, score))), weight=0.10, scoring_method="rule",
        calculation_detail={
            "improving": improving, "stable": stable, "declining": declining,
            **detail,
        },
        ai_reasoning=None,
    )


def _score_star7(metrics: dict) -> DimensionScore:
    """Star 7: Ideal Position — 12 absolute benchmark tests."""
    passed = 0
    results: dict[str, bool] = {}

    for metric_name, check_fn in _IDEAL_BENCHMARKS:
        val = metrics.get(metric_name)
        if val is not None:
            try:
                result = check_fn(float(val))
            except (TypeError, ValueError):
                result = False
        else:
            result = False
        results[metric_name] = result
        if result:
            passed += 1

    total_tests = len(_IDEAL_BENCHMARKS)
    score = round((passed / total_tests) * 100) if total_tests > 0 else 0

    return DimensionScore(
        dimension_number=7, dimension_name="Ideal Position",
        score=float(score), weight=0.10, scoring_method="rule",
        calculation_detail={"passed": passed, "total": total_tests, "results": results},
        ai_reasoning=None,
    )


# ---------------------------------------------------------------------------
# Valuation methodology + ROE decomposition helpers
# ---------------------------------------------------------------------------

def select_valuation_method(metrics: dict, industry: str) -> str:
    """Select appropriate valuation methodology based on company profile."""
    pat = _safe(metrics, "net_margin_t0")
    has_assets = _safe(metrics, "total_assets", 0) > 0
    industry_lower = industry.lower()

    # Asset-heavy → NAV approach primary
    if industry_lower in ("property", "mining", "plantation", "infrastructure"):
        return "nav"
    # Negative earnings → asset-based or revenue multiple
    if pat <= 0:
        return "nav" if has_assets else "revenue_multiple"
    # High growth tech → DCF
    rev_cagr = _safe(metrics, "revenue_cagr_3yr")
    if rev_cagr > 20 and industry_lower in ("it", "tech", "saas", "platform"):
        return "dcf"
    # Default → comparable company multiples
    return "comparable_multiples"


def roe_decomposition(metrics: dict) -> dict[str, Any]:
    """DuPont ROE decomposition with Horse classification.

    ROE = Net Margin × Asset Turnover × Equity Multiplier

    Horse Classification:
    - Thoroughbred: high margin, high turnover, low leverage
    - Racehorse: high growth, moderate leverage
    - Workhorse: low margin, high turnover
    - Show Horse: high leverage dependent
    """
    net_margin = _safe(metrics, "dupont_net_margin")
    asset_turn = _safe(metrics, "dupont_asset_turnover")
    eq_mult = _safe(metrics, "dupont_equity_multiplier", 1)

    calculated_roe = (net_margin / 100) * asset_turn * eq_mult * 100 if asset_turn > 0 else 0

    # Horse classification
    if net_margin > 10 and asset_turn > 1.0 and eq_mult < 2.5:
        horse = "Thoroughbred"
        horse_desc = "High quality: strong margins, efficient assets, conservative leverage"
    elif _safe(metrics, "revenue_cagr_3yr") > 20 and eq_mult < 3:
        horse = "Racehorse"
        horse_desc = "High growth with moderate leverage; potential but needs monitoring"
    elif net_margin < 5 and asset_turn > 1.5:
        horse = "Workhorse"
        horse_desc = "Low margins compensated by high asset turnover; efficiency-driven"
    elif eq_mult > 3:
        horse = "Show Horse"
        horse_desc = "ROE driven primarily by leverage; higher risk profile"
    else:
        horse = "Unclassified"
        horse_desc = "Mixed profile; no dominant driver"

    return {
        "net_margin_pct": round(net_margin, 2),
        "asset_turnover": round(asset_turn, 2),
        "equity_multiplier": round(eq_mult, 2),
        "calculated_roe": round(calculated_roe, 2),
        "horse_classification": horse,
        "horse_description": horse_desc,
    }


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class ValuationScorer:
    """Module 3: Valuation — 8-star system."""

    def __init__(self, client=None) -> None:
        self._client = client or get_ai_client()
        self._ai_scorer = AIScorer(self._client)

    async def score(
        self,
        intake_data: dict[str, Any],
        metrics: dict[str, Any],
        research_data: dict[str, Any] | None = None,
        metrics_3yr: list[dict[str, Any]] | None = None,
        progress_callback: Callable | None = None,
    ) -> ModuleResult:
        """Run all 8 stars and produce the module result.

        Args:
            intake_data: Raw Stage 2 intake data
            metrics: Calculated metrics (from calculate_metrics)
            research_data: Due diligence research (peers, industry)
            metrics_3yr: List of per-year metric dicts [t2, t1, t0] for CV/trend
            progress_callback: Async callback for progress updates
        """
        if metrics_3yr is None:
            metrics_3yr = []

        async def _progress(msg: str):
            if progress_callback:
                await progress_callback(f"Scoring Valuation: {msg}")

        # Stars 1-4: threshold-based (sync, fast)
        await _progress("Growth metrics...")
        star1 = _score_star1(metrics)
        await _progress("Profitability metrics...")
        star2 = _score_star2(metrics)
        await _progress("Operational efficiency...")
        star3 = _score_star3(metrics)
        await _progress("Credit standing...")
        star4 = _score_star4(metrics)

        # Stars 5-6: rule-based (need 3yr data)
        await _progress("Consistency analysis...")
        star5 = _score_star5(metrics_3yr)
        await _progress("Sustainability trends...")
        star6 = _score_star6(metrics_3yr)

        # Star 7: ideal position
        await _progress("Ideal position benchmarks...")
        star7 = _score_star7(metrics)

        # Star 8: AI-judged industry benchmark
        await _progress("Industry benchmark comparison...")
        star8 = await self._score_star8(metrics, intake_data, research_data)

        dimensions = [star1, star2, star3, star4, star5, star6, star7, star8]

        # Count stars earned (score ≥ 60)
        stars_earned = sum(1 for d in dimensions if d["score"] >= 60)

        # Weighted average
        total = sum(d["score"] * d["weight"] for d in dimensions)
        total_score = max(0.0, min(100.0, round(total, 2)))

        # Valuation method & ROE decomposition
        industry = intake_data.get("primary_industry", intake_data.get("industry", ""))
        val_method = select_valuation_method(metrics, industry)
        roe_decomp = roe_decomposition(metrics)

        return ModuleResult(
            module_number=3,
            module_name="Valuation",
            dimensions=dimensions,
            stars_earned=stars_earned,
            total_score=total_score,
            rating=_rating(total_score, stars_earned),
            valuation_method=val_method,
            roe_decomposition=roe_decomp,
        )

    async def _score_star8(
        self,
        metrics: dict[str, Any],
        intake_data: dict[str, Any],
        research_data: dict[str, Any] | None,
    ) -> DimensionScore:
        """Star 8: Industry Benchmark — AI-judged peer comparison."""
        peer_data = {}
        if research_data:
            peer_data = research_data.get("peers", {})

        # Also pull from Stage 2 Section F if available
        stage2_peers = intake_data.get("peers", {})
        if isinstance(stage2_peers, dict):
            comparable = stage2_peers.get("comparable_companies", [])
            benchmarks = stage2_peers.get("industry_benchmarks")
            if comparable:
                peer_data["comparable_companies_stage2"] = comparable
            if benchmarks:
                peer_data["industry_benchmarks_stage2"] = benchmarks

        input_data = {
            "company_metrics": {
                k: v for k, v in metrics.items()
                if v is not None and k not in ("dupont_net_margin", "dupont_asset_turnover", "dupont_equity_multiplier")
            },
            "peer_data": peer_data,
            "industry": intake_data.get("primary_industry", ""),
        }

        try:
            result = await self._client.score_dimension(
                dimension_name="Industry Benchmark",
                rubric=INDUSTRY_BENCHMARK_RUBRIC,
                input_data=input_data,
            )
            score = float(max(0, min(100, result.get("score", 50))))
            reasoning = result.get("reasoning", "")
        except Exception as exc:
            logger.warning("AI scoring for Star 8 failed: %s", exc)
            score = 50.0
            reasoning = f"AI scoring unavailable: {exc}"

        return DimensionScore(
            dimension_number=8, dimension_name="Industry Benchmark",
            score=score, weight=0.05, scoring_method="ai",
            calculation_detail={"peer_data_available": bool(peer_data)},
            ai_reasoning=reasoning,
        )
