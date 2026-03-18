"""
Rule-based (deterministic) scoring functions for quantitative dimensions.

All scores are integers 0-100. Threshold tables are sourced directly from the
IIFLE scoring rubrics (knowledge-base/12-scoring-rubrics/).
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def threshold_score(value: float, thresholds: list[tuple[Any, int]]) -> int:
    """Score *value* against an ordered list of ``(check, score)`` pairs.

    Each *check* is a callable ``(float) -> bool`` evaluated top-to-bottom;
    the first match wins.  If nothing matches the last entry's score is
    returned as fallback.

    Example::

        threshold_score(35.0, [
            (lambda v: v > 50, 100),
            (lambda v: v > 30, 85),
            (lambda v: v > 15, 70),
            ...
        ])
    """
    for check, score in thresholds:
        if callable(check) and check(value):
            return score
    # Fallback to last entry
    return thresholds[-1][1] if thresholds else 0


def checklist_score(
    items: dict[str, str],
    scoring_map: dict[str, dict[str, int]],
) -> int:
    """Score a checklist where each item has a ``"yes" | "partial" | "no"`` value.

    *scoring_map* maps factor names to dicts like
    ``{"yes": 20, "partial": 10, "no": 0}``.

    Missing items default to ``"no"``.
    """
    total = 0
    for factor, levels in scoring_map.items():
        answer = (items.get(factor) or "no").lower().strip()
        total += levels.get(answer, levels.get("no", 0))
    return max(0, min(100, total))


# ---------------------------------------------------------------------------
# Revenue Growth CAGR  (Gene D7 — 40 % of Growth dimension, also BM D2 30 %)
# ---------------------------------------------------------------------------

_REVENUE_CAGR_THRESHOLDS: list[tuple[Any, int]] = [
    (lambda v: v > 50, 100),
    (lambda v: v > 30, 85),
    (lambda v: v > 15, 70),
    (lambda v: v > 10, 55),
    (lambda v: v > 5, 40),
    (lambda v: v >= 0, 25),
    (lambda _: True, 10),  # negative
]


def score_revenue_growth_cagr(cagr_pct: float) -> int:
    """Score 3-year revenue CAGR using Gene D7 / BM D2 thresholds."""
    return threshold_score(cagr_pct, _REVENUE_CAGR_THRESHOLDS)


# ---------------------------------------------------------------------------
# YoY Revenue Growth (BM D2 — Revenue Growth sub-dimension, 30 %)
# ---------------------------------------------------------------------------

_YOY_REVENUE_THRESHOLDS: list[tuple[Any, int]] = [
    (lambda v: v > 50, 100),
    (lambda v: v > 30, 85),
    (lambda v: v > 15, 70),
    (lambda v: v > 5, 50),
    (lambda v: v >= 0, 35),
    (lambda _: True, 15),  # negative
]


def score_yoy_revenue_growth(yoy_pct: float) -> int:
    """Score latest-year YoY revenue growth (BM D2)."""
    return threshold_score(yoy_pct, _YOY_REVENUE_THRESHOLDS)


# ---------------------------------------------------------------------------
# PAT Trajectory  (Gene D7 — 40 % of Growth dimension)
# ---------------------------------------------------------------------------

def score_pat_trajectory(pat_values: list[float]) -> int:
    """Score PAT trajectory from a list of annual PAT values (RM millions).

    Values should be ordered oldest → newest.  The most recent PAT and the
    overall trend determine the score band.
    """
    if not pat_values:
        return 10

    latest = pat_values[-1]
    is_growing = len(pat_values) >= 2 and pat_values[-1] > pat_values[-2]

    # Check against Main Market targets (RM 6M / 7M / 8M consecutive)
    if len(pat_values) >= 3 and pat_values[-3] >= 6 and pat_values[-2] >= 7 and pat_values[-1] >= 8:
        return 100
    if len(pat_values) >= 3 and all(p >= 6 for p in pat_values[-3:]):
        return 85

    # ACE Market targets (RM 3M / 4M / 5M consecutive)
    if len(pat_values) >= 3 and pat_values[-3] >= 3 and pat_values[-2] >= 4 and pat_values[-1] >= 5:
        return 70
    if len(pat_values) >= 3 and all(p >= 3 for p in pat_values[-3:]):
        return 55

    if 1 <= latest < 3 and is_growing:
        return 40
    if latest < 1 and is_growing:
        return 25

    # Declining or negative
    return 10


# ---------------------------------------------------------------------------
# Customer Concentration  (BM D1)
# ---------------------------------------------------------------------------

_TOP1_THRESHOLDS: list[tuple[Any, int]] = [
    (lambda v: v < 10, 100),
    (lambda v: v < 20, 80),
    (lambda v: v < 30, 60),
    (lambda v: v < 50, 40),
    (lambda _: True, 15),  # >= 50 %
]

_TOP5_THRESHOLDS: list[tuple[Any, int]] = [
    (lambda v: v < 30, 100),
    (lambda v: v < 50, 75),
    (lambda v: v < 70, 50),
    (lambda _: True, 25),  # >= 70 %
]


def score_customer_concentration(top1_pct: float, top5_pct: float) -> tuple[int, int]:
    """Return ``(top1_score, top5_score)`` for BM D1."""
    return (
        threshold_score(top1_pct, _TOP1_THRESHOLDS),
        threshold_score(top5_pct, _TOP5_THRESHOLDS),
    )


# ---------------------------------------------------------------------------
# Customer Quality (BM D1 — 20 % of dimension)
# ---------------------------------------------------------------------------

def score_customer_quality(
    avg_relationship_years: float | None,
    retention_rate_pct: float | None,
    long_term_contracts: str | None,  # "majority" | "some" | "none"
) -> int:
    """Score customer quality factors (BM D1 — 20% of Customer Analysis).

    Each factor contributes up to 20 points (max 60, normalised to 100).
    """
    total = 0

    # Relationship length
    if avg_relationship_years is not None:
        if avg_relationship_years > 3:
            total += 20
        elif avg_relationship_years >= 1:
            total += 12
        else:
            total += 5

    # Retention rate
    if retention_rate_pct is not None:
        if retention_rate_pct > 80:
            total += 20
        elif retention_rate_pct >= 60:
            total += 12
        else:
            total += 5

    # Long-term contracts
    ltc = (long_term_contracts or "none").lower().strip()
    if ltc == "majority":
        total += 20
    elif ltc == "some":
        total += 12
    else:
        total += 5

    # Normalise: max raw = 60 → 100
    return max(0, min(100, round(total * 100 / 60)))


# ---------------------------------------------------------------------------
# Revenue Diversification  (BM D2 — 30 % of Revenue Model)
# ---------------------------------------------------------------------------

def score_revenue_diversification(num_streams: int, max_stream_pct: float) -> int:
    """Score revenue stream diversification (BM D2)."""
    if num_streams >= 4 and max_stream_pct <= 40:
        return 100
    if num_streams >= 3:
        return 80
    if num_streams >= 2:
        return 60
    return 30  # single stream > 80 %


# ---------------------------------------------------------------------------
# Revenue Quality  (BM D2 — 40 % of Revenue Model)
# ---------------------------------------------------------------------------

_REVENUE_QUALITY_MAP: dict[str, int] = {
    "subscription": 100,
    "saas": 100,
    "long_term_contract": 85,
    "repeat_purchase": 70,
    "project_based": 50,
    "one_time": 30,
    "seasonal": 15,
}


def score_revenue_quality(model_type: str) -> int:
    """Score revenue quality based on business model type (BM D2)."""
    key = model_type.lower().strip().replace(" ", "_").replace("-", "_")
    return _REVENUE_QUALITY_MAP.get(key, 50)


# ---------------------------------------------------------------------------
# Gross Margin — industry-adjusted  (BM D3 — 40 % of Profitability)
# ---------------------------------------------------------------------------

_GROSS_MARGIN_THRESHOLDS: dict[str, list[tuple[Any, int]]] = {
    "services": [
        (lambda v: v > 60, 100),
        (lambda v: v > 40, 80),
        (lambda v: v > 25, 60),
        (lambda v: v > 15, 40),
        (lambda _: True, 20),
    ],
    "tech": [
        (lambda v: v > 60, 100),
        (lambda v: v > 40, 80),
        (lambda v: v > 25, 60),
        (lambda v: v > 15, 40),
        (lambda _: True, 20),
    ],
    "f&b": [
        (lambda v: v > 50, 100),
        (lambda v: v > 35, 80),
        (lambda v: v > 20, 60),
        (lambda v: v > 10, 40),
        (lambda _: True, 20),
    ],
    "retail": [
        (lambda v: v > 50, 100),
        (lambda v: v > 35, 80),
        (lambda v: v > 20, 60),
        (lambda v: v > 10, 40),
        (lambda _: True, 20),
    ],
    "manufacturing": [
        (lambda v: v > 35, 100),
        (lambda v: v > 25, 80),
        (lambda v: v > 15, 60),
        (lambda v: v > 8, 40),
        (lambda _: True, 20),
    ],
    "logistics": [
        (lambda v: v > 25, 100),
        (lambda v: v > 18, 80),
        (lambda v: v > 12, 60),
        (lambda v: v > 5, 40),
        (lambda _: True, 20),
    ],
    "trading": [
        (lambda v: v > 15, 100),
        (lambda v: v > 10, 80),
        (lambda v: v > 5, 60),
        (lambda v: v > 2, 40),
        (lambda _: True, 20),
    ],
}

# Default thresholds for unknown industries
_GROSS_MARGIN_DEFAULT = [
    (lambda v: v > 40, 100),
    (lambda v: v > 25, 80),
    (lambda v: v > 15, 60),
    (lambda v: v > 8, 40),
    (lambda _: True, 20),
]


def score_gross_margin(margin_pct: float, industry: str) -> int:
    """Score gross margin with industry-specific thresholds (BM D3)."""
    key = industry.lower().strip()
    thresholds = _GROSS_MARGIN_THRESHOLDS.get(key, _GROSS_MARGIN_DEFAULT)
    return threshold_score(margin_pct, thresholds)


# ---------------------------------------------------------------------------
# Net Margin  (BM D3 — 30 % of Profitability)
# ---------------------------------------------------------------------------

_NET_MARGIN_THRESHOLDS: list[tuple[Any, int]] = [
    (lambda v: v > 20, 100),
    (lambda v: v > 15, 85),
    (lambda v: v > 10, 70),
    (lambda v: v > 5, 50),
    (lambda v: v > 1, 30),
    (lambda _: True, 10),  # < 1 % or negative
]


def score_net_margin(margin_pct: float) -> int:
    """Score net profit margin (BM D3)."""
    return threshold_score(margin_pct, _NET_MARGIN_THRESHOLDS)


# ---------------------------------------------------------------------------
# Per Capita Efficiency Trend  (BM D3 — 30 % of Profitability)
# ---------------------------------------------------------------------------

_EFFICIENCY_TREND_THRESHOLDS: list[tuple[Any, int]] = [
    (lambda v: v > 15, 100),
    (lambda v: v > 5, 75),
    (lambda v: v > -5, 50),
    (lambda _: True, 25),  # declining
]


def score_efficiency_trend(revenue_per_employee_cagr: float) -> int:
    """Score revenue-per-employee 3-year CAGR trend (BM D3)."""
    return threshold_score(revenue_per_employee_cagr, _EFFICIENCY_TREND_THRESHOLDS)


# ---------------------------------------------------------------------------
# Recurring Revenue  (BM D7)
# ---------------------------------------------------------------------------

_RECURRING_THRESHOLDS: list[tuple[Any, int]] = [
    (lambda v: v > 80, 100),
    (lambda v: v > 60, 85),
    (lambda v: v > 40, 70),
    (lambda v: v > 20, 50),
    (lambda v: v > 10, 35),
    (lambda _: True, 15),  # < 10 %
]


def score_recurring_revenue(recurring_pct: float) -> int:
    """Score recurring revenue as % of total (BM D7)."""
    return threshold_score(recurring_pct, _RECURRING_THRESHOLDS)


# ---------------------------------------------------------------------------
# Replicability Checklist (Gene D5 / BM D5)
# ---------------------------------------------------------------------------

_GENE_REPLICABILITY_MAP: dict[str, dict[str, int]] = {
    "sops_documented": {"yes": 20, "partial": 10, "no": 0},
    "training_system": {"yes": 20, "partial": 10, "no": 0},
    "quality_control": {"yes": 20, "partial": 10, "no": 0},
    "geographic_expansion": {"yes": 20, "partial": 10, "no": 0},
    "central_facility": {"yes": 10, "partial": 5, "no": 0},
    "franchise_model_ready": {"yes": 10, "partial": 5, "no": 0},
}

_BM_REPLICABILITY_MAP: dict[str, dict[str, int]] = {
    "sops_documented": {"yes": 20, "partial": 10, "no": 0},
    "trainable_in_4_weeks": {"yes": 20, "partial": 10, "no": 0},
    "central_facility": {"yes": 20, "partial": 10, "no": 0},
    "replicated_2_plus_locations": {"yes": 20, "partial": 10, "no": 0},
    "quality_consistent": {"yes": 20, "partial": 10, "no": 0},
}


def score_replicability_checklist(items: dict[str, str], module: str = "gene") -> int:
    """Score the replicability checklist for Gene D5 or BM D5.

    *module*: ``"gene"`` or ``"bm"`` selects the appropriate scoring map.
    """
    scoring_map = _GENE_REPLICABILITY_MAP if module == "gene" else _BM_REPLICABILITY_MAP
    return checklist_score(items, scoring_map)


# ---------------------------------------------------------------------------
# Team Foundation  (Gene D6)
# ---------------------------------------------------------------------------

def score_team_foundation(
    org_data: dict[str, str],
    talent_data: dict[str, str],
    culture_data: dict[str, str],
) -> int:
    """Score Gene D6: Team Foundation (checklist + rubric hybrid).

    Returns a score 0-100 blended from three sub-sections.
    """
    # --- Organisation Structure (40 %) ---
    org_map = {
        "org_chart": {"clear": 20, "partial": 10, "none": 0},
        "key_positions": {"all_filled": 20, "most_filled": 12, "major_gaps": 0},
    }
    org_score = checklist_score(org_data, org_map)  # max raw 40
    # Normalise to 100
    org_score_norm = min(100, round(org_score * 100 / 40))

    # --- Talent System (35 %) ---
    talent_map = {
        "de_cai_gang_alignment": {"strong": 15, "partial": 8, "none": 0},
        "training_program": {"systematic": 10, "periodic": 5, "none": 0},
        "employee_turnover": {"low": 10, "moderate": 5, "high": 0},
    }
    # Translate friendly values
    turnover_raw = talent_data.get("employee_turnover", "high")
    if isinstance(turnover_raw, (int, float)):
        if turnover_raw < 15:
            talent_data_norm = {**talent_data, "employee_turnover": "low"}
        elif turnover_raw <= 30:
            talent_data_norm = {**talent_data, "employee_turnover": "moderate"}
        else:
            talent_data_norm = {**talent_data, "employee_turnover": "high"}
    else:
        talent_data_norm = dict(talent_data)

    talent_score = checklist_score(talent_data_norm, talent_map)  # max raw 35
    talent_score_norm = min(100, round(talent_score * 100 / 35))

    # --- Culture (25 %) ---
    culture_map = {
        "vision_mission_values": {"documented_lived": 15, "some_documented": 8, "none": 0},
        "equity_incentive": {"in_place": 10, "planned": 5, "none": 0},
    }
    culture_score = checklist_score(culture_data, culture_map)  # max raw 25
    culture_score_norm = min(100, round(culture_score * 100 / 25))

    # Weighted blend
    blended = (org_score_norm * 0.40) + (talent_score_norm * 0.35) + (culture_score_norm * 0.25)
    return max(0, min(100, round(blended)))


# ---------------------------------------------------------------------------
# Growth Potential  (Gene D7 — composite)
# ---------------------------------------------------------------------------

def score_growth_potential(
    revenue_cagr: float,
    pat_values: list[float],
    capital_leverage: str,  # "high" | "medium" | "low"
) -> int:
    """Score Gene D7: Growth Potential (threshold-based composite).

    Sub-dimensions: Revenue CAGR (40 %), PAT trajectory (40 %),
    Capital leverage potential (20 %).
    """
    rev_score = score_revenue_growth_cagr(revenue_cagr)
    pat_score = score_pat_trajectory(pat_values)

    cap_map = {"high": 100, "medium": 60, "low": 30}
    cap_score = cap_map.get(capital_leverage.lower().strip(), 30)

    composite = (rev_score * 0.40) + (pat_score * 0.40) + (cap_score * 0.20)
    return max(0, min(100, round(composite)))


# ---------------------------------------------------------------------------
# Moat Scoring  (Gene D4 helper — used alongside AI scorer)
# ---------------------------------------------------------------------------

_MOAT_MAX_POINTS: dict[str, dict[str, int]] = {
    "brand": {"strong": 20, "medium": 12, "weak": 5, "absent": 0},
    "technology_ip": {"strong": 20, "medium": 12, "weak": 5, "absent": 0},
    "scale_cost": {"strong": 15, "medium": 10, "weak": 5, "absent": 0},
    "network_effects": {"strong": 20, "medium": 12, "weak": 5, "absent": 0},
    "switching_costs": {"strong": 15, "medium": 10, "weak": 5, "absent": 0},
    "regulatory_license": {"strong": 10, "medium": 7, "weak": 3, "absent": 0},
    "supply_chain": {"strong": 10, "medium": 7, "weak": 3, "absent": 0},
}


def score_moat(moats: dict[str, str]) -> int:
    """Score enterprise differentiation moat types (Gene D4).

    *moats*: ``{"brand": "strong", "technology_ip": "medium", ...}``

    Returns 0-100 (capped).
    """
    total = 0
    for moat_type, levels in _MOAT_MAX_POINTS.items():
        level = moats.get(moat_type, "absent").lower().strip()
        total += levels.get(level, 0)
    return min(100, total)


# ---------------------------------------------------------------------------
# Gene 9-Item Checklist Modifier
# ---------------------------------------------------------------------------

def gene_checklist_modifier(items_met: int) -> int:
    """Return the bonus/penalty modifier for the Gene 9-item checklist.

    | Items Met | Modifier |
    |-----------|----------|
    | 9/9       | +5       |
    | 7-8       | +2       |
    | 5-6       | 0        |
    | 3-4       | -5       |
    | 0-2       | -10      |
    """
    if items_met >= 9:
        return 5
    if items_met >= 7:
        return 2
    if items_met >= 5:
        return 0
    if items_met >= 3:
        return -5
    return -10
