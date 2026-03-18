from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


# ─── Section A: Company Profile ───


class RegistrationDetails(BaseModel):
    legal_name: str = Field(max_length=500)
    registration_number: str
    date_of_incorporation: date
    company_type: Literal["sdn_bhd", "berhad", "llp", "sole_prop", "partnership"]
    registered_address: str
    operating_address: str | None = None
    website: str | None = None
    country_of_incorporation: Literal["malaysia", "singapore", "others"] = "malaysia"
    other_jurisdictions: list[str] = []


class IndustryClassification(BaseModel):
    primary_industry: Literal["fnb", "it", "manufacturing", "retail", "logistics", "property", "services", "others"]
    sub_industry: str
    msic_code: str | None = None
    brief_description: str = Field(max_length=500)


class CompanyScale(BaseModel):
    total_employees: int = Field(ge=0)
    num_branches: int | None = None
    operating_since: int = Field(ge=1800, le=2100)
    geographic_coverage: list[Literal["local", "national", "regional", "international"]]
    countries_of_operation: list[str] = []


# ─── Section B: Founder & Leadership ───


class FounderProfile(BaseModel):
    name: str
    age: int = Field(ge=18, le=120)
    nationality: str
    highest_education: Literal["secondary", "diploma", "degree", "masters", "phd", "professional", "emba"]
    education_institution: str | None = None
    years_in_industry: int = Field(ge=0)
    years_business_experience: int = Field(ge=0)
    previous_companies_founded: int = 0
    previous_exit_experience: Literal["none", "sold", "listed", "both"] = "none"
    emba_status: Literal["none", "in_progress", "completed"] = "none"
    emba_program: str | None = None


class CoFounder(BaseModel):
    name: str
    role: str
    ownership_pct: float = Field(ge=0, le=100)
    years_with_company: int = Field(ge=0)
    expertise: str


class ManagementMember(BaseModel):
    position: str
    name: str | None = None
    years_in_role: int | None = None
    years_with_company: int | None = None
    background: str | None = None


class Succession(BaseModel):
    has_succession_plan: Literal["yes", "in_progress", "no"]
    management_stable_3yr: Literal["yes", "mostly", "no"]
    key_person: str
    key_person_contingency: str = Field(max_length=300)


# ─── Section C: Products & Services ───


class ProductOffering(BaseModel):
    name: str
    type: Literal["product", "service", "subscription", "license"]
    revenue_share_pct: float = Field(ge=0, le=100)
    gross_margin_pct: float | None = Field(default=None, ge=0, le=100)
    growth_trend: Literal["growing", "stable", "declining"]


class ProductCompetitiveness(BaseModel):
    differentiation: str = Field(max_length=500)
    ip_type: list[Literal["none", "patents", "trademarks", "trade_secrets", "proprietary_tech"]]
    num_patents: int | None = None
    rd_spending: float | None = None
    certifications: str | None = None


class CustomerProfile(BaseModel):
    customer_type: Literal["b2b", "b2c", "b2g", "mixed"]
    active_customers: int = Field(ge=0)
    top1_revenue_pct: float = Field(ge=0, le=100)
    top5_revenue_pct: float = Field(ge=0, le=100)
    top10_revenue_pct: float | None = Field(default=None, ge=0, le=100)
    avg_relationship_length: Literal["lt_1yr", "1_3yr", "3_5yr", "5plus"]
    retention_rate: float | None = Field(default=None, ge=0, le=100)
    long_term_contracts: Literal["none", "some", "majority", "all"]


class SupplyChain(BaseModel):
    num_key_suppliers: int = Field(ge=0)
    single_supplier_dependency: Literal["none", "low", "moderate", "high", "critical"]
    supplier_agreements_documented: Literal["all", "most", "some", "none"]


# ─── Section D: Business Model ───


class RevenueModel(BaseModel):
    description: str = Field(max_length=300)
    model_types: list[
        Literal[
            "product_sales", "service_fees", "subscription", "commission", "licensing", "franchise", "rental", "others"
        ]
    ]
    recurring_revenue_pct: float = Field(ge=0, le=100)
    is_seasonal: Literal["not_seasonal", "mildly", "highly"]
    peak_months: list[int] = []


class Scalability(BaseModel):
    replicable: Literal["easily", "with_effort", "difficult", "no"]
    documented_sops: Literal["comprehensive", "partial", "minimal", "none"]
    central_facility: Literal["yes", "planned", "no", "na"] | None = None
    training_weeks: int = Field(ge=0)
    expansion_plan_3yr: str = Field(max_length=300)


class CompetitiveLandscape(BaseModel):
    top3_competitors: list[str] = Field(min_length=1, max_length=3)
    estimated_market_share: Literal[
        "lt_1pct", "1_5pct", "5_10pct", "10_25pct", "25_50pct", "gt_50pct", "unknown"
    ]
    segment_leader: bool
    segment_leader_detail: str | None = None
    competitive_advantages: list[
        Literal["price", "quality", "brand", "technology", "speed", "service", "location", "network", "others"]
    ]
    barriers_to_entry: Literal["very_high", "high", "moderate", "low", "none"]


# ─── Section E: Basic Financials ───


class YearlyFinancials(BaseModel):
    revenue: float
    cogs: float
    operating_expenses: float
    pbt: float
    pat: float


class BasicFinancials(BaseModel):
    fy_end_month: int = Field(ge=1, le=12)
    year_t2: YearlyFinancials
    year_t1: YearlyFinancials
    year_t0: YearlyFinancials


class BalanceSheet(BaseModel):
    cash: float
    receivables: float
    inventory: float | None = None
    current_assets: float
    fixed_assets: float
    total_assets: float
    current_liabilities: float
    bank_borrowings: float
    total_liabilities: float
    paid_up_capital: float


class CashFlowBasics(BaseModel):
    cash_flow_positive: Literal["yes_consistently", "sometimes", "no"]
    monthly_opex: float
    current_cash: float
    customer_pay_days: int = Field(ge=0)
    supplier_pay_days: int = Field(ge=0)


class AuditStatus(BaseModel):
    has_audited: bool
    years_audited: int | None = None
    auditor_name: str | None = None
    aob_registered: Literal["yes", "no", "unknown"] | None = None
    accounting_standard: Literal["mpers", "mfrs", "unknown"]


# ─── Section F: Growth & Ambition ───


class GrowthPlans(BaseModel):
    revenue_target_yr1: float
    revenue_target_yr3: float
    revenue_target_yr5: float | None = None
    growth_strategy: list[
        Literal["organic", "new_products", "new_markets", "acquisitions", "franchising", "online", "partnerships"]
    ]
    biggest_obstacle: str = Field(max_length=300)


class CapitalIntentions(BaseModel):
    looking_to_raise: Literal["yes_actively", "considering", "not_now", "no"]
    raise_amount: float | None = None
    raise_purpose: list[
        Literal["expansion", "working_capital", "rd", "ma", "debt_repayment", "ipo_prep", "others"]
    ] = []
    prior_funding: list[
        Literal["never", "angel", "vc", "pe", "bank_loan", "government_grant", "others"]
    ] = []
    prior_amount: float | None = None


class IPOAspiration(BaseModel):
    interest: Literal["within_3yr", "within_5yr", "interested_unsure", "not_interested", "dont_know"]
    preferred_markets: list[str] = []
    engaged_advisors: Literal["yes", "in_discussions", "no"] | None = None
    biggest_barrier: str | None = None


class ExitPreference(BaseModel):
    long_term_goal: Literal["keep_forever", "ipo", "sell", "next_generation", "dont_know"]
    liquidity_timeline: Literal["1_2yr", "3_5yr", "5_10yr", "no_timeline"] | None = None


# ─── Section G: Team & Organization ───


class OrgMaturity(BaseModel):
    formal_org_chart: Literal["yes", "partial", "no"]
    num_departments: int = Field(ge=0)
    performance_reviews: Literal["quarterly", "semi_annually", "annually", "rarely", "never"]
    training_program: Literal["systematic_733", "periodic", "adhoc", "none"]
    turnover_rate: float | None = Field(default=None, ge=0, le=100)
    hr_policies: Literal["comprehensive", "basic", "none"]


class CultureValues(BaseModel):
    documented_vmv: Literal["all_three", "some", "none"]
    vision: str | None = None
    mission: str | None = None
    core_values: str | None = None


# ─── Top-Level Stage 1 Schema ───


class Stage1Data(BaseModel):
    # Section A: Company Profile
    registration: RegistrationDetails | None = None
    industry: IndustryClassification | None = None
    scale: CompanyScale | None = None
    # Section B: Founder & Leadership
    founder: FounderProfile | None = None
    co_founders: list[CoFounder] = []
    management_team: list[ManagementMember] = []
    succession: Succession | None = None
    # Section C: Products & Services
    products: list[ProductOffering] = []
    product_competitiveness: ProductCompetitiveness | None = None
    customers: CustomerProfile | None = None
    supply_chain: SupplyChain | None = None
    # Section D: Business Model
    revenue_model: RevenueModel | None = None
    scalability: Scalability | None = None
    competitive_landscape: CompetitiveLandscape | None = None
    # Section E: Basic Financials
    financials: BasicFinancials | None = None
    balance_sheet: BalanceSheet | None = None
    cash_flow: CashFlowBasics | None = None
    audit_status: AuditStatus | None = None
    # Section F: Growth & Ambition
    growth_plans: GrowthPlans | None = None
    capital_intentions: CapitalIntentions | None = None
    ipo_aspiration: IPOAspiration | None = None
    exit_preference: ExitPreference | None = None
    # Section G: Team & Organization
    org_maturity: OrgMaturity | None = None
    culture: CultureValues | None = None
