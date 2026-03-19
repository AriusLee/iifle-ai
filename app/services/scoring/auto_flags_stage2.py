"""
Auto-detection rules for Stage 2 flags — 10 financial patterns.

These flags detect issues in the detailed financial data that require
attention before or during Module 3 & 4 scoring.
"""

from __future__ import annotations

from typing import Any

from app.services.scoring.auto_flags import AutoFlagData, _safe_float


def detect_stage2_flags(
    intake_data: dict[str, Any],
    metrics: dict[str, Any],
) -> list[AutoFlagData]:
    """Run 10 deterministic rules against Stage 2 data and calculated metrics."""
    flags: list[AutoFlagData] = []

    # ───────────────────────────────────────────────────────────────────
    # 1. Declining gross margins (3yr trend) → margin_erosion (high)
    # ───────────────────────────────────────────────────────────────────
    gm_t0 = _safe_float(metrics.get("gross_margin_t0"))
    gm_t2 = _safe_float(metrics.get("gross_margin_t2"))
    if gm_t0 is not None and gm_t2 is not None and gm_t0 < gm_t2 - 3:
        flags.append(AutoFlagData(
            flag_type="margin_erosion",
            severity="high",
            description=(
                f"Gross margin declined from {gm_t2:.1f}% to {gm_t0:.1f}% over 3 years. "
                "Indicates pricing pressure or cost escalation."
            ),
            source_field="gross_margin",
            source_value=f"{gm_t2:.1f}% → {gm_t0:.1f}%",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 2. Negative operating cash flow → cash_flow_concern (critical)
    # ───────────────────────────────────────────────────────────────────
    ocf = _safe_float(metrics.get("operating_cf_margin_t0"))
    if ocf is not None and ocf < 0:
        flags.append(AutoFlagData(
            flag_type="cash_flow_concern",
            severity="critical",
            description=(
                f"Operating cash flow margin is negative ({ocf:.1f}%). "
                "Company is burning cash from operations."
            ),
            source_field="operating_cf_margin_t0",
            source_value=f"{ocf:.1f}%",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 3. High receivable days > 120 → collection_risk (high)
    # ───────────────────────────────────────────────────────────────────
    rec_days = _safe_float(metrics.get("receivable_days_t0"))
    if rec_days is not None and rec_days > 120:
        flags.append(AutoFlagData(
            flag_type="collection_risk",
            severity="high",
            description=(
                f"Receivable days is {rec_days:.0f} days — significantly above healthy range (< 90 days). "
                "Cash collection may be problematic."
            ),
            source_field="receivable_days_t0",
            source_value=f"{rec_days:.0f} days",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 4. Current ratio < 1.0 → liquidity_risk (critical)
    # ───────────────────────────────────────────────────────────────────
    cr = _safe_float(metrics.get("current_ratio_t0"))
    if cr is not None and cr < 1.0:
        flags.append(AutoFlagData(
            flag_type="liquidity_risk",
            severity="critical",
            description=(
                f"Current ratio is {cr:.2f} (below 1.0). "
                "Company may not be able to meet short-term obligations."
            ),
            source_field="current_ratio_t0",
            source_value=f"{cr:.2f}",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 5. Net gearing > 150% → over_leveraged (high)
    # ───────────────────────────────────────────────────────────────────
    gearing = _safe_float(metrics.get("net_gearing_t0"))
    if gearing is not None and gearing > 150:
        flags.append(AutoFlagData(
            flag_type="over_leveraged",
            severity="high",
            description=(
                f"Net gearing is {gearing:.0f}% — well above comfortable range (< 60%). "
                "Company is highly leveraged; debt reduction should be a priority."
            ),
            source_field="net_gearing_t0",
            source_value=f"{gearing:.0f}%",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 6. DSCR < 1.0 → debt_servicing_risk (critical)
    # ───────────────────────────────────────────────────────────────────
    dscr = _safe_float(metrics.get("dscr_t0"))
    if dscr is not None and dscr < 1.0:
        flags.append(AutoFlagData(
            flag_type="debt_servicing_risk",
            severity="critical",
            description=(
                f"Debt service coverage ratio is {dscr:.2f} (below 1.0). "
                "Company cannot fully service its debt from operating cash flows."
            ),
            source_field="dscr_t0",
            source_value=f"{dscr:.2f}",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 7. RPT > 20% of revenue → related_party_concern (high)
    # ───────────────────────────────────────────────────────────────────
    rpt = intake_data.get("related_party", {}) or {}
    rpt_pct = _safe_float(rpt.get("rpt_as_pct_of_revenue"))
    if rpt_pct is not None and rpt_pct > 20:
        flags.append(AutoFlagData(
            flag_type="related_party_concern",
            severity="high",
            description=(
                f"Related party transactions represent {rpt_pct:.1f}% of revenue. "
                "High RPT levels require scrutiny for arms-length pricing and governance."
            ),
            source_field="rpt_as_pct_of_revenue",
            source_value=f"{rpt_pct:.1f}%",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 8. Qualified audit opinion → audit_quality_issue (high)
    # ───────────────────────────────────────────────────────────────────
    audit = intake_data.get("audit", {}) or {}
    audit_info = audit.get("audit_info", {}) if isinstance(audit, dict) else {}
    opinion = (audit_info.get("audit_opinion", "") if isinstance(audit_info, dict) else "").lower()
    if opinion in ("qualified", "adverse", "disclaimer"):
        flags.append(AutoFlagData(
            flag_type="audit_quality_issue",
            severity="critical" if opinion in ("adverse", "disclaimer") else "high",
            description=(
                f"Audit opinion is '{opinion}'. "
                "This significantly impacts financial credibility and investor confidence."
            ),
            source_field="audit_opinion",
            source_value=opinion,
        ))

    # ───────────────────────────────────────────────────────────────────
    # 9. Revenue decline with increasing costs → profitability_squeeze (high)
    # ───────────────────────────────────────────────────────────────────
    rev_yoy = _safe_float(metrics.get("revenue_yoy_t0"))
    nm_t0 = _safe_float(metrics.get("net_margin_t0"))
    nm_t1 = _safe_float(metrics.get("net_margin_t1"))
    if (rev_yoy is not None and rev_yoy < 0 and
            nm_t0 is not None and nm_t1 is not None and nm_t0 < nm_t1):
        flags.append(AutoFlagData(
            flag_type="profitability_squeeze",
            severity="high",
            description=(
                f"Revenue declining ({rev_yoy:+.1f}% YoY) while net margin also declining "
                f"({nm_t1:.1f}% → {nm_t0:.1f}%). Classic profitability squeeze pattern."
            ),
            source_field="revenue_yoy_t0 + net_margin",
            source_value=f"Rev: {rev_yoy:+.1f}%, NM: {nm_t1:.1f}%→{nm_t0:.1f}%",
        ))

    # ───────────────────────────────────────────────────────────────────
    # 10. No financial projections provided → planning_gap (medium)
    # ───────────────────────────────────────────────────────────────────
    projections = intake_data.get("projections", {}) or {}
    projection_list = projections.get("projections", [])
    if not projection_list:
        flags.append(AutoFlagData(
            flag_type="planning_gap",
            severity="medium",
            description=(
                "No financial projections provided. "
                "Investors expect at least 3-5 year revenue and profit projections."
            ),
            source_field="projections",
            source_value="empty",
        ))

    return flags
