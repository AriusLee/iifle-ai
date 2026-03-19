"""
Stage 2 Intake Schemas — Financial Engine (~120 fields across 9 sections A-I).

Sections:
  A: Audited Financial Statements (upload + audit info)
  B: Detailed Income Statement (revenue breakdown, cost structure, 3yr)
  C: Detailed Balance Sheet (full line items, 3yr)
  D: Cash Flow Details (operating, investing, financing, 3yr)
  E: Working Capital Details (receivables aging, inventory, borrowings)
  F: Peer Comparison Data (comparable companies, benchmarks)
  G: Budget & Projections (current budget, 5yr projections, capex)
  H: Funding History & Equity (rounds, shareholding, agreements)
  I: Related Party Transactions
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ─── Section A: Audited Financial Statements ───


class AuditInfo(BaseModel):
    has_audited_accounts: bool
    years_audited: int = Field(ge=0, le=50)
    auditor_name: str | None = None
    auditor_firm: str | None = None
    aob_registered: Literal["yes", "no", "unknown"] = "unknown"
    accounting_standard: Literal["mpers", "mfrs", "ifrs", "unknown"] = "unknown"
    audit_opinion: Literal["unqualified", "qualified", "adverse", "disclaimer", "unknown"] = "unknown"
    audit_qualifications: str | None = None
    latest_audit_fy_end: str | None = None  # e.g. "2025-12-31"
    management_letter_issues: str | None = None


class AuditedDocuments(BaseModel):
    """References to uploaded audited report documents."""
    document_ids: list[str] = []  # UUIDs of uploaded documents
    years_covered: list[int] = []  # e.g. [2023, 2024, 2025]


class SectionA(BaseModel):
    audit_info: AuditInfo | None = None
    audited_documents: AuditedDocuments | None = None


# ─── Section B: Detailed Income Statement (3yr) ───


class IncomeStatementYear(BaseModel):
    fiscal_year: int
    # Revenue breakdown
    total_revenue: float
    revenue_streams: list[RevenueStream] = []
    other_income: float = 0
    # Cost structure
    cost_of_goods_sold: float = 0
    gross_profit: float = 0
    # Operating expenses breakdown
    staff_costs: float = 0
    rental_expenses: float = 0
    depreciation_amortization: float = 0
    marketing_expenses: float = 0
    administrative_expenses: float = 0
    other_operating_expenses: float = 0
    total_operating_expenses: float = 0
    # Operating profit
    ebitda: float = 0
    ebit: float = 0
    # Below the line
    interest_income: float = 0
    interest_expense: float = 0
    net_finance_cost: float = 0
    exceptional_items: float = 0
    profit_before_tax: float = 0
    tax_expense: float = 0
    profit_after_tax: float = 0
    # Per share (if applicable)
    earnings_per_share: float | None = None
    dividend_per_share: float | None = None


class RevenueStream(BaseModel):
    name: str
    amount: float
    pct_of_total: float = Field(ge=0, le=100)
    growth_yoy_pct: float | None = None


class SectionB(BaseModel):
    fy_end_month: int = Field(ge=1, le=12)
    year_t2: IncomeStatementYear | None = None  # oldest
    year_t1: IncomeStatementYear | None = None
    year_t0: IncomeStatementYear | None = None  # most recent


# ─── Section C: Detailed Balance Sheet (3yr) ───


class BalanceSheetYear(BaseModel):
    fiscal_year: int
    # Current assets
    cash_and_equivalents: float = 0
    trade_receivables: float = 0
    other_receivables: float = 0
    inventory: float = 0
    prepayments: float = 0
    other_current_assets: float = 0
    total_current_assets: float = 0
    # Non-current assets
    property_plant_equipment: float = 0
    right_of_use_assets: float = 0
    intangible_assets: float = 0
    goodwill: float = 0
    investment_properties: float = 0
    investments: float = 0
    deferred_tax_assets: float = 0
    other_non_current_assets: float = 0
    total_non_current_assets: float = 0
    total_assets: float = 0
    # Current liabilities
    trade_payables: float = 0
    other_payables: float = 0
    short_term_borrowings: float = 0
    lease_liabilities_current: float = 0
    tax_payable: float = 0
    other_current_liabilities: float = 0
    total_current_liabilities: float = 0
    # Non-current liabilities
    long_term_borrowings: float = 0
    lease_liabilities_non_current: float = 0
    deferred_tax_liabilities: float = 0
    provisions: float = 0
    other_non_current_liabilities: float = 0
    total_non_current_liabilities: float = 0
    total_liabilities: float = 0
    # Equity
    paid_up_capital: float = 0
    share_premium: float = 0
    retained_earnings: float = 0
    other_reserves: float = 0
    non_controlling_interests: float = 0
    total_equity: float = 0


class SectionC(BaseModel):
    year_t2: BalanceSheetYear | None = None
    year_t1: BalanceSheetYear | None = None
    year_t0: BalanceSheetYear | None = None


# ─── Section D: Cash Flow Details (3yr) ───


class CashFlowYear(BaseModel):
    fiscal_year: int
    # Operating activities
    profit_before_tax: float = 0
    depreciation_amortization: float = 0
    interest_expense: float = 0
    interest_income: float = 0
    working_capital_changes: float = 0
    tax_paid: float = 0
    net_operating_cash_flow: float = 0
    # Investing activities
    capex: float = 0
    acquisition_of_subsidiaries: float = 0
    proceeds_from_disposal: float = 0
    other_investing: float = 0
    net_investing_cash_flow: float = 0
    # Financing activities
    proceeds_from_borrowings: float = 0
    repayment_of_borrowings: float = 0
    lease_payments: float = 0
    dividends_paid: float = 0
    proceeds_from_equity: float = 0
    other_financing: float = 0
    net_financing_cash_flow: float = 0
    # Summary
    net_change_in_cash: float = 0
    opening_cash: float = 0
    closing_cash: float = 0
    free_cash_flow: float = 0  # operating CF - capex


class SectionD(BaseModel):
    year_t2: CashFlowYear | None = None
    year_t1: CashFlowYear | None = None
    year_t0: CashFlowYear | None = None


# ─── Section E: Working Capital Details ───


class ReceivablesAging(BaseModel):
    current_0_30: float = 0
    days_31_60: float = 0
    days_61_90: float = 0
    days_91_120: float = 0
    over_120_days: float = 0
    total_receivables: float = 0
    provision_for_doubtful_debts: float = 0


class InventoryBreakdown(BaseModel):
    raw_materials: float = 0
    work_in_progress: float = 0
    finished_goods: float = 0
    consumables: float = 0
    total_inventory: float = 0
    obsolete_provision: float = 0


class BorrowingDetail(BaseModel):
    lender: str
    facility_type: Literal[
        "term_loan", "revolving_credit", "overdraft", "trade_finance",
        "hire_purchase", "leasing", "bond", "other"
    ]
    facility_limit: float
    outstanding_amount: float
    interest_rate: float  # annual %
    maturity_date: str | None = None
    collateral: str | None = None
    is_secured: bool = True


class SectionE(BaseModel):
    receivables_aging: ReceivablesAging | None = None
    inventory_breakdown: InventoryBreakdown | None = None
    borrowings: list[BorrowingDetail] = []
    total_credit_facilities: float | None = None
    total_utilized: float | None = None
    average_collection_days: float | None = None
    average_inventory_days: float | None = None
    average_payable_days: float | None = None


# ─── Section F: Peer Comparison Data ───


class ComparableCompany(BaseModel):
    name: str
    ticker: str | None = None
    market: str | None = None  # e.g. "Bursa Main", "Bursa ACE", "SGX"
    revenue: float | None = None
    pat: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    ev_ebitda: float | None = None
    gross_margin_pct: float | None = None
    net_margin_pct: float | None = None
    roe_pct: float | None = None


class IndustryBenchmarks(BaseModel):
    industry: str
    gross_margin_median: float | None = None
    net_margin_median: float | None = None
    roe_median: float | None = None
    pe_median: float | None = None
    ev_ebitda_median: float | None = None
    revenue_growth_median: float | None = None
    current_ratio_median: float | None = None
    debt_equity_median: float | None = None


class SectionF(BaseModel):
    comparable_companies: list[ComparableCompany] = []
    industry_benchmarks: IndustryBenchmarks | None = None
    data_source: str | None = None  # e.g. "Bloomberg", "Capital IQ", "manual"
    data_as_of: str | None = None


# ─── Section G: Budget & Projections ───


class ProjectionYear(BaseModel):
    year: int
    projected_revenue: float
    projected_cogs: float | None = None
    projected_gross_profit: float | None = None
    projected_operating_expenses: float | None = None
    projected_ebitda: float | None = None
    projected_pat: float | None = None
    projected_capex: float | None = None
    projected_headcount: int | None = None
    key_assumptions: str | None = None


class CapexPlan(BaseModel):
    description: str
    amount: float
    year: int
    category: Literal[
        "property", "equipment", "technology", "vehicles",
        "renovation", "other"
    ]
    funding_source: Literal[
        "internal_cash", "bank_loan", "equity", "lease", "other"
    ] = "internal_cash"


class SectionG(BaseModel):
    current_year_budget_revenue: float | None = None
    current_year_budget_pat: float | None = None
    projections: list[ProjectionYear] = []
    capex_plans: list[CapexPlan] = []
    projection_methodology: str | None = None  # "bottom_up", "top_down", "hybrid"
    key_growth_drivers: list[str] = []
    key_risks: list[str] = []


# ─── Section H: Funding History & Equity ───


class FundingRound(BaseModel):
    round_name: str  # e.g. "Seed", "Series A", "Pre-IPO"
    date: str | None = None
    amount_raised: float
    currency: str = "MYR"
    investor_names: list[str] = []
    investor_types: list[Literal[
        "angel", "vc", "pe", "strategic", "government", "family_office", "other"
    ]] = []
    pre_money_valuation: float | None = None
    post_money_valuation: float | None = None
    equity_given_pct: float | None = None
    instrument_type: Literal[
        "ordinary_shares", "preference_shares", "convertible_note",
        "safe", "rcps", "other"
    ] = "ordinary_shares"


class Shareholder(BaseModel):
    name: str
    type: Literal["founder", "co_founder", "investor", "employee", "family", "corporate", "other"]
    shares_held: int | None = None
    ownership_pct: float = Field(ge=0, le=100)
    is_director: bool = False
    nationality: str | None = None


class SectionH(BaseModel):
    funding_rounds: list[FundingRound] = []
    total_raised_to_date: float | None = None
    current_shareholders: list[Shareholder] = []
    total_shares_issued: int | None = None
    paid_up_capital: float | None = None
    has_shareholder_agreement: bool | None = None
    has_esos_plan: bool | None = None
    esos_pool_pct: float | None = None
    has_convertible_instruments: bool | None = None
    convertible_details: str | None = None


# ─── Section I: Related Party Transactions ───


class RelatedPartyTransaction(BaseModel):
    related_party_name: str
    relationship: Literal[
        "director", "shareholder", "family_member", "subsidiary",
        "associate", "common_director", "other"
    ]
    transaction_type: Literal[
        "sales", "purchases", "management_fee", "rental", "loan",
        "guarantee", "service", "other"
    ]
    amount: float
    currency: str = "MYR"
    is_recurring: bool = True
    is_arms_length: Literal["yes", "no", "unknown"] = "unknown"
    documentation_status: Literal["formal_agreement", "informal", "none"] = "none"
    description: str | None = None


class SectionI(BaseModel):
    has_related_party_transactions: bool = False
    transactions: list[RelatedPartyTransaction] = []
    total_rpt_amount: float | None = None
    rpt_as_pct_of_revenue: float | None = None
    has_rpt_policy: bool = False


# ─── Top-Level Stage 2 Schema ───


class Stage2Data(BaseModel):
    # Section A: Audited Financial Statements
    audit: SectionA | None = None
    # Section B: Detailed Income Statement
    income_statement: SectionB | None = None
    # Section C: Detailed Balance Sheet
    balance_sheet: SectionC | None = None
    # Section D: Cash Flow Details
    cash_flow: SectionD | None = None
    # Section E: Working Capital Details
    working_capital: SectionE | None = None
    # Section F: Peer Comparison Data
    peers: SectionF | None = None
    # Section G: Budget & Projections
    projections: SectionG | None = None
    # Section H: Funding History & Equity
    funding: SectionH | None = None
    # Section I: Related Party Transactions
    related_party: SectionI | None = None


# ─── Auto-Calculation Engine ───


class CalculatedMetrics(BaseModel):
    """Auto-calculated financial ratios and metrics from raw Stage 2 inputs."""
    # Growth metrics
    revenue_cagr_3yr: float | None = None
    pat_cagr_3yr: float | None = None
    revenue_yoy_t1: float | None = None
    revenue_yoy_t0: float | None = None
    # Profitability
    gross_margin_t0: float | None = None
    gross_margin_t1: float | None = None
    gross_margin_t2: float | None = None
    ebit_margin_t0: float | None = None
    net_margin_t0: float | None = None
    net_margin_t1: float | None = None
    net_margin_t2: float | None = None
    roa_t0: float | None = None
    roe_t0: float | None = None
    # Efficiency
    asset_turnover_t0: float | None = None
    inventory_days_t0: float | None = None
    receivable_days_t0: float | None = None
    payable_days_t0: float | None = None
    cash_conversion_cycle_t0: float | None = None
    # Credit standing
    current_ratio_t0: float | None = None
    quick_ratio_t0: float | None = None
    interest_coverage_t0: float | None = None
    net_gearing_t0: float | None = None
    dscr_t0: float | None = None
    debt_equity_t0: float | None = None
    # Cash flow
    operating_cf_margin_t0: float | None = None
    free_cash_flow_t0: float | None = None
    cash_runway_months: float | None = None
    # ROE decomposition (DuPont)
    dupont_net_margin: float | None = None
    dupont_asset_turnover: float | None = None
    dupont_equity_multiplier: float | None = None


def calculate_metrics(data: Stage2Data) -> CalculatedMetrics:
    """Compute all financial ratios from raw Stage 2 intake data."""
    m = CalculatedMetrics()
    bs = data.balance_sheet
    inc = data.income_statement
    cf = data.cash_flow

    # --- Growth metrics ---
    if inc and inc.year_t0 and inc.year_t2:
        rev_t0 = inc.year_t0.total_revenue
        rev_t2 = inc.year_t2.total_revenue
        if rev_t2 and rev_t2 > 0:
            m.revenue_cagr_3yr = (((rev_t0 / rev_t2) ** (1 / 2)) - 1) * 100

        pat_t0 = inc.year_t0.profit_after_tax
        pat_t2 = inc.year_t2.profit_after_tax
        if pat_t2 and pat_t2 > 0 and pat_t0 > 0:
            m.pat_cagr_3yr = (((pat_t0 / pat_t2) ** (1 / 2)) - 1) * 100

    if inc and inc.year_t0 and inc.year_t1:
        rev_t0 = inc.year_t0.total_revenue
        rev_t1 = inc.year_t1.total_revenue
        if rev_t1 and rev_t1 > 0:
            m.revenue_yoy_t0 = ((rev_t0 - rev_t1) / abs(rev_t1)) * 100

    if inc and inc.year_t1 and inc.year_t2:
        rev_t1 = inc.year_t1.total_revenue
        rev_t2 = inc.year_t2.total_revenue
        if rev_t2 and rev_t2 > 0:
            m.revenue_yoy_t1 = ((rev_t1 - rev_t2) / abs(rev_t2)) * 100

    # --- Profitability ---
    for year_attr, suffix in [("year_t0", "t0"), ("year_t1", "t1"), ("year_t2", "t2")]:
        yr = getattr(inc, year_attr, None) if inc else None
        if yr and yr.total_revenue and yr.total_revenue > 0:
            gm = (yr.gross_profit / yr.total_revenue) * 100
            setattr(m, f"gross_margin_{suffix}", round(gm, 2))
            nm = (yr.profit_after_tax / yr.total_revenue) * 100
            setattr(m, f"net_margin_{suffix}", round(nm, 2))

    if inc and inc.year_t0 and inc.year_t0.total_revenue > 0:
        yr = inc.year_t0
        m.ebit_margin_t0 = round((yr.ebit / yr.total_revenue) * 100, 2)

    if inc and inc.year_t0 and bs and bs.year_t0:
        if bs.year_t0.total_assets and bs.year_t0.total_assets > 0:
            m.roa_t0 = round((inc.year_t0.profit_after_tax / bs.year_t0.total_assets) * 100, 2)
        if bs.year_t0.total_equity and bs.year_t0.total_equity > 0:
            m.roe_t0 = round((inc.year_t0.profit_after_tax / bs.year_t0.total_equity) * 100, 2)

    # --- Efficiency ---
    if inc and inc.year_t0 and bs and bs.year_t0:
        rev = inc.year_t0.total_revenue
        cogs = inc.year_t0.cost_of_goods_sold
        if bs.year_t0.total_assets and bs.year_t0.total_assets > 0:
            m.asset_turnover_t0 = round(rev / bs.year_t0.total_assets, 2)
        if cogs and cogs > 0:
            if bs.year_t0.inventory:
                m.inventory_days_t0 = round((bs.year_t0.inventory / cogs) * 365, 1)
        if rev > 0:
            if bs.year_t0.trade_receivables:
                m.receivable_days_t0 = round((bs.year_t0.trade_receivables / rev) * 365, 1)
        if cogs and cogs > 0 and bs.year_t0.trade_payables:
            m.payable_days_t0 = round((bs.year_t0.trade_payables / cogs) * 365, 1)

        # CCC
        inv_d = m.inventory_days_t0 or 0
        rec_d = m.receivable_days_t0 or 0
        pay_d = m.payable_days_t0 or 0
        m.cash_conversion_cycle_t0 = round(inv_d + rec_d - pay_d, 1)

    # --- Credit standing ---
    if bs and bs.year_t0:
        b = bs.year_t0
        if b.total_current_liabilities and b.total_current_liabilities > 0:
            m.current_ratio_t0 = round(b.total_current_assets / b.total_current_liabilities, 2)
            quick_assets = b.total_current_assets - (b.inventory or 0)
            m.quick_ratio_t0 = round(quick_assets / b.total_current_liabilities, 2)

        if b.total_equity and b.total_equity > 0:
            total_debt = b.short_term_borrowings + b.long_term_borrowings
            net_debt = total_debt - b.cash_and_equivalents
            m.net_gearing_t0 = round((net_debt / b.total_equity) * 100, 2)
            m.debt_equity_t0 = round((b.total_liabilities / b.total_equity) * 100, 2)

    if inc and inc.year_t0 and inc.year_t0.interest_expense and inc.year_t0.interest_expense > 0:
        m.interest_coverage_t0 = round(inc.year_t0.ebit / inc.year_t0.interest_expense, 2)

    # DSCR (simplified: operating CF / total debt service)
    if cf and cf.year_t0 and inc and inc.year_t0:
        debt_service = abs(inc.year_t0.interest_expense) + abs(cf.year_t0.repayment_of_borrowings)
        if debt_service > 0:
            m.dscr_t0 = round(cf.year_t0.net_operating_cash_flow / debt_service, 2)

    # --- Cash flow metrics ---
    if cf and cf.year_t0:
        c = cf.year_t0
        if inc and inc.year_t0 and inc.year_t0.total_revenue > 0:
            m.operating_cf_margin_t0 = round(
                (c.net_operating_cash_flow / inc.year_t0.total_revenue) * 100, 2
            )
        m.free_cash_flow_t0 = c.free_cash_flow

    if bs and bs.year_t0 and inc and inc.year_t0:
        monthly_opex = abs(inc.year_t0.total_operating_expenses) / 12
        if monthly_opex > 0:
            m.cash_runway_months = round(bs.year_t0.cash_and_equivalents / monthly_opex, 1)

    # --- DuPont decomposition ---
    if m.net_margin_t0 is not None:
        m.dupont_net_margin = m.net_margin_t0
    if m.asset_turnover_t0 is not None:
        m.dupont_asset_turnover = m.asset_turnover_t0
    if bs and bs.year_t0 and bs.year_t0.total_equity and bs.year_t0.total_equity > 0:
        m.dupont_equity_multiplier = round(
            bs.year_t0.total_assets / bs.year_t0.total_equity, 2
        )

    return m
