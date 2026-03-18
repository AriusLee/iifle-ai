"""
Auto-detection rules for Stage 1 flags.

These flags surface critical issues early, before detailed scoring, so that
analysts can triage and prioritise.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AutoFlagData(TypedDict):
    flag_type: str
    severity: str  # "critical" | "high" | "medium" | "low"
    description: str
    source_field: str | None
    source_value: str | None


def detect_stage1_flags(intake_data: dict[str, Any]) -> list[AutoFlagData]:
    """Run 8 deterministic rules against intake data and return any flags found."""
    flags: list[AutoFlagData] = []

    # ---------------------------------------------------------------
    # 1. Top 1 customer > 30% → customer_concentration_risk (high)
    # ---------------------------------------------------------------
    top1 = _safe_float(intake_data.get("top1_customer_pct"))
    if top1 is not None and top1 > 30:
        flags.append(AutoFlagData(
            flag_type="customer_concentration_risk",
            severity="high",
            description=(
                f"Top 1 customer accounts for {top1:.0f}% of revenue. "
                "Concentration above 30% poses significant risk to revenue stability."
            ),
            source_field="top1_customer_pct",
            source_value=str(top1),
        ))

    # ---------------------------------------------------------------
    # 2. Management tenure < 3 years → management_continuity_risk (medium)
    # ---------------------------------------------------------------
    tenure = _safe_float(intake_data.get("management_stability_years"))
    if tenure is not None and tenure < 3:
        flags.append(AutoFlagData(
            flag_type="management_continuity_risk",
            severity="medium",
            description=(
                f"Management team tenure is {tenure:.1f} years. "
                "Less than 3 years indicates potential continuity risk."
            ),
            source_field="management_stability_years",
            source_value=str(tenure),
        ))

    # ---------------------------------------------------------------
    # 3. No audited reports → financial_credibility_gap (high)
    # ---------------------------------------------------------------
    has_audit = str(intake_data.get("has_audited_reports", "")).lower()
    if has_audit in ("no", "false", "0", ""):
        # Also check years_of_audited_reports
        audit_years = _safe_float(intake_data.get("years_of_audited_reports"))
        if audit_years is None or audit_years == 0:
            flags.append(AutoFlagData(
                flag_type="financial_credibility_gap",
                severity="high",
                description=(
                    "Company has no audited financial reports. "
                    "This is a fundamental gap for capital-market readiness."
                ),
                source_field="has_audited_reports",
                source_value=has_audit or "not provided",
            ))

    # ---------------------------------------------------------------
    # 4. Founder holds all key roles → key_person_dependency (high)
    # ---------------------------------------------------------------
    founder_roles = intake_data.get("founder_roles") or []
    kpd = str(intake_data.get("key_person_dependency", "")).lower()
    if (isinstance(founder_roles, list) and len(founder_roles) >= 3) or kpd in ("high", "critical"):
        role_count = len(founder_roles) if isinstance(founder_roles, list) else "multiple"
        flags.append(AutoFlagData(
            flag_type="key_person_dependency",
            severity="high",
            description=(
                f"Founder holds {role_count} key roles. "
                "Entire business operation depends on a single person."
            ),
            source_field="founder_roles",
            source_value=str(founder_roles) if founder_roles else kpd,
        ))

    # ---------------------------------------------------------------
    # 5. Revenue declining YoY → growth_concern (high)
    # ---------------------------------------------------------------
    yoy = _safe_float(intake_data.get("yoy_revenue_growth"))
    if yoy is not None and yoy < 0:
        flags.append(AutoFlagData(
            flag_type="growth_concern",
            severity="high",
            description=(
                f"Revenue is declining year-over-year ({yoy:+.1f}%). "
                "Negative growth trajectory raises concerns for investors."
            ),
            source_field="yoy_revenue_growth",
            source_value=str(yoy),
        ))
    else:
        # Also check from revenue values list
        revenues = intake_data.get("annual_revenues") or []
        if isinstance(revenues, list) and len(revenues) >= 2:
            try:
                vals = [float(v) for v in revenues[-2:] if v is not None]
                if len(vals) == 2 and vals[1] < vals[0]:
                    flags.append(AutoFlagData(
                        flag_type="growth_concern",
                        severity="high",
                        description=(
                            f"Revenue declined from {vals[0]:.1f} to {vals[1]:.1f} in latest year."
                        ),
                        source_field="annual_revenues",
                        source_value=str(vals),
                    ))
            except (TypeError, ValueError):
                pass

    # ---------------------------------------------------------------
    # 6. Cash runway < 6 months → liquidity_warning (critical)
    # ---------------------------------------------------------------
    runway = _safe_float(intake_data.get("cash_runway_months"))
    if runway is not None and runway < 6:
        flags.append(AutoFlagData(
            flag_type="liquidity_warning",
            severity="critical",
            description=(
                f"Cash runway is approximately {runway:.0f} months. "
                "Less than 6 months of runway is a critical liquidity risk."
            ),
            source_field="cash_runway_months",
            source_value=str(runway),
        ))

    # ---------------------------------------------------------------
    # 7. No SOPs documented → scalability_barrier (medium)
    # ---------------------------------------------------------------
    sops = str(intake_data.get("sops_documented", "")).lower()
    if sops in ("no", "false", "0", "none", ""):
        flags.append(AutoFlagData(
            flag_type="scalability_barrier",
            severity="medium",
            description=(
                "No documented Standard Operating Procedures (SOPs). "
                "This limits the company's ability to replicate and scale operations."
            ),
            source_field="sops_documented",
            source_value=sops or "not provided",
        ))

    # ---------------------------------------------------------------
    # 8. No IP/patents → differentiation_risk (low)
    # ---------------------------------------------------------------
    has_ip = str(intake_data.get("ip_patents", intake_data.get("has_ip_patents", ""))).lower()
    if has_ip in ("no", "false", "0", "none", ""):
        flags.append(AutoFlagData(
            flag_type="differentiation_risk",
            severity="low",
            description=(
                "No intellectual property or patents identified. "
                "Company may lack sustainable competitive differentiation."
            ),
            source_field="ip_patents",
            source_value=has_ip or "not provided",
        ))

    return flags


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
