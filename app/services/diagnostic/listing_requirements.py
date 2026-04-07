"""
Listing requirements reference data for the Unicorn Diagnostic Report.

Mirrors the customer-facing TypeScript module at
``customer/src/lib/listing-requirements.ts`` and exposes the same tier
auto-pick logic. Used by report_generator.py to embed deterministic
side-by-side requirement tables (Bursa Malaysia SC vs US NASDAQ / SEC)
into the diagnostic PDF — the numbers are hard-coded here, the AI only
writes narrative commentary on top of them.

Tier pairs by enterprise stage:
    概念萌芽期 / 初创探索期 / 模式验证期  →  ACE Market   +  NASDAQ Capital Market
    规模扩张期                            →  Main Market  +  NASDAQ Global Market
    资本进阶期                            →  Main Market  +  NASDAQ Global Select
"""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Criterion:
    key: str  # canonical key — used to align across jurisdictions
    label_zh: str
    label_en: str
    value_zh: str
    value_en: str


# Canonical row order + display labels for the comparison table.
# Each row maps a semantic key to a bilingual label. Rows where a jurisdiction
# has no requirement render as "—" rather than being omitted.
CANONICAL_ROWS: list[tuple[str, str, str]] = [
    ("profit", "盈利要求", "Profit / Income"),
    ("equity", "股东权益", "Stockholders' Equity"),
    ("revenue", "营收要求", "Revenue"),
    ("market_value", "公众持股市值", "Market Value of Public Float"),
    ("history", "经营年限", "Operating History"),
    ("public_spread", "公众持股比例", "Public Spread / Shares"),
    ("shareholders", "公众股东人数", "Public Shareholders"),
    ("price", "最低股价", "Minimum Bid Price"),
    ("sponsor", "保荐人要求", "Sponsor Requirement"),
    ("governance", "公司治理", "Corporate Governance"),
    ("reporting", "财务披露", "Financial Reporting"),
]


@dataclass
class ListingTier:
    code: str
    jurisdiction: Literal["MY", "US"]
    regulator: Literal["SC", "SEC"]
    exchange_zh: str
    exchange_en: str
    board_zh: str
    board_en: str
    tagline_zh: str
    tagline_en: str
    criteria: list[Criterion]


# ── Bursa Malaysia ────────────────────────────────────────────────────────────

ACE_MARKET = ListingTier(
    code="BURSA_ACE",
    jurisdiction="MY",
    regulator="SC",
    exchange_zh="马来西亚证券交易所",
    exchange_en="Bursa Malaysia",
    board_zh="ACE 创业板",
    board_en="ACE Market",
    tagline_zh="面向具备成长潜力的中小企业，无强制盈利门槛，以保荐人制度为核心。",
    tagline_en="For high-growth SMEs. No mandatory profit threshold; sponsor-driven admission.",
    criteria=[
        Criterion("profit", "盈利要求", "Profit Requirement", "无强制要求", "None mandated"),
        Criterion("revenue", "营收要求", "Revenue Requirement", "无强制要求", "None mandated"),
        Criterion("history", "经营年限", "Operating History", "无强制要求", "Not strictly required"),
        Criterion("sponsor", "保荐人", "Sponsor", "必须委任授权保荐人，上市后至少 3 年", "Authorised Sponsor required, minimum 3 years post-listing"),
        Criterion("public_spread", "公众持股", "Public Spread", "≥ 25% 已发行股本", "≥ 25% of issued share capital"),
        Criterion("shareholders", "公众股东人数", "Public Shareholders", "≥ 200 名（每人持股 ≥ 100 股）", "≥ 200 holders (≥ 100 shares each)"),
        Criterion("governance", "董事会治理", "Board Governance", "≥ 1/3 独立董事，须设审计委员会", "≥ 1/3 independent directors; audit committee required"),
    ],
)

MAIN_MARKET = ListingTier(
    code="BURSA_MAIN",
    jurisdiction="MY",
    regulator="SC",
    exchange_zh="马来西亚证券交易所",
    exchange_en="Bursa Malaysia",
    board_zh="主板（盈利测试）",
    board_en="Main Market (Profit Test)",
    tagline_zh="面向已实现稳定盈利的成熟企业，盈利、规模、治理三方面均有明确门槛。",
    tagline_en="For mature, profitable companies. Hard thresholds on earnings, size, and governance.",
    criteria=[
        Criterion("profit", "盈利要求", "Profit Requirement", "过去 3–5 年累计税后净利 ≥ RM 20M，最近一年税后净利 ≥ RM 6M（连续 3–5 年盈利）", "Aggregate PAT ≥ RM 20M over 3–5 yrs; latest year PAT ≥ RM 6M (3–5 consecutive profitable yrs)"),
        Criterion("history", "经营年限", "Operating History", "同一管理层下经营 ≥ 3–5 年", "≥ 3–5 yrs under same management"),
        Criterion("public_spread", "公众持股", "Public Spread", "≥ 25% 已发行股本", "≥ 25% of issued share capital"),
        Criterion("shareholders", "公众股东人数", "Public Shareholders", "≥ 1,000 名", "≥ 1,000 holders"),
        Criterion("governance", "董事会治理", "Board Governance", "≥ 1/3 独立董事，须设审计、提名、薪酬委员会", "≥ 1/3 independent directors; audit, nomination, remuneration committees"),
        Criterion("reporting", "财务披露", "Financial Reporting", "上市前 3 年经审计财务报表（MFRS / IFRS）", "3 yrs of audited financial statements (MFRS / IFRS) prior to listing"),
    ],
)

# ── United States — NASDAQ tiers ──────────────────────────────────────────────

NASDAQ_CAPITAL = ListingTier(
    code="NASDAQ_CAPITAL",
    jurisdiction="US",
    regulator="SEC",
    exchange_zh="美国 NASDAQ 交易所",
    exchange_en="NASDAQ",
    board_zh="NASDAQ Capital Market（入门板）",
    board_en="NASDAQ Capital Market",
    tagline_zh="美国 NASDAQ 三层结构中门槛最低的入门板，适合早期阶段的企业。",
    tagline_en="Entry tier of NASDAQ's three-tier structure. Suited to earlier-stage companies.",
    criteria=[
        Criterion("profit", "盈利要求（任选一项标准）", "Profit Requirement (one standard)", "净利润标准：最近一财年净利润 ≥ USD 750K", "Net Income standard: latest fiscal year net income ≥ USD 750K"),
        Criterion("equity", "股东权益", "Stockholders' Equity", "股东权益标准：≥ USD 5M", "Equity standard: ≥ USD 5M"),
        Criterion("market_value", "公众持股市值", "Market Value of Public Float", "≥ USD 15M（净利润标准下 ≥ USD 5M）", "≥ USD 15M (≥ USD 5M under net income standard)"),
        Criterion("history", "经营年限", "Operating History", "≥ 2 年", "≥ 2 years"),
        Criterion("public_spread", "公众持股数量", "Publicly Held Shares", "≥ 1,000,000 股", "≥ 1,000,000 shares"),
        Criterion("shareholders", "公众股东人数", "Round-lot Holders", "≥ 300 名整手股东", "≥ 300 round-lot holders"),
        Criterion("price", "最低股价", "Minimum Bid Price", "≥ USD 4.00", "≥ USD 4.00"),
        Criterion("governance", "公司治理", "Corporate Governance", "独立董事多数席位 + 审计委员会（萨班斯法案合规）", "Majority independent board + audit committee (SOX compliant)"),
    ],
)

NASDAQ_GLOBAL = ListingTier(
    code="NASDAQ_GLOBAL",
    jurisdiction="US",
    regulator="SEC",
    exchange_zh="美国 NASDAQ 交易所",
    exchange_en="NASDAQ",
    board_zh="NASDAQ Global Market（中阶板）",
    board_en="NASDAQ Global Market",
    tagline_zh="面向已具备稳定盈利和一定规模的成长型企业。",
    tagline_en="For growth companies with established earnings and meaningful scale.",
    criteria=[
        Criterion("profit", "盈利要求", "Income Standard", "持续经营税前利润 ≥ USD 1M（最近一年或最近 3 年中的 2 年）", "Pre-tax income from continuing operations ≥ USD 1M (latest yr or 2 of last 3)"),
        Criterion("equity", "股东权益", "Stockholders' Equity", "≥ USD 15M", "≥ USD 15M"),
        Criterion("market_value", "公众持股市值", "Market Value of Public Float", "≥ USD 8M", "≥ USD 8M"),
        Criterion("public_spread", "公众持股数量", "Publicly Held Shares", "≥ 1,100,000 股", "≥ 1,100,000 shares"),
        Criterion("shareholders", "公众股东人数", "Round-lot Holders", "≥ 400 名整手股东", "≥ 400 round-lot holders"),
        Criterion("price", "最低股价", "Minimum Bid Price", "≥ USD 4.00", "≥ USD 4.00"),
        Criterion("governance", "公司治理", "Corporate Governance", "独立董事多数席位 + 审计/提名/薪酬委员会（SOX 合规）", "Majority independent board + audit/nomination/comp committees (SOX)"),
        Criterion("reporting", "财务披露", "Financial Reporting", "US GAAP 或 IFRS 审计；季报 + 年报 (10-Q / 10-K)", "Audited US GAAP or IFRS; quarterly + annual filings (10-Q / 10-K)"),
    ],
)

NASDAQ_GLOBAL_SELECT = ListingTier(
    code="NASDAQ_GLOBAL_SELECT",
    jurisdiction="US",
    regulator="SEC",
    exchange_zh="美国 NASDAQ 交易所",
    exchange_en="NASDAQ",
    board_zh="NASDAQ Global Select（旗舰板）",
    board_en="NASDAQ Global Select Market",
    tagline_zh="NASDAQ 三层中要求最严苛的旗舰板，对标全球大型成熟企业。",
    tagline_en="NASDAQ's most stringent tier — peer to large, established global companies.",
    criteria=[
        Criterion("profit", "盈利要求（最常用标准）", "Earnings Standard", "过去 3 年累计税前利润 ≥ USD 11M，且最近 2 年每年 ≥ USD 2.2M", "Aggregate pre-tax earnings ≥ USD 11M over 3 yrs; ≥ USD 2.2M each of latest 2"),
        Criterion("market_value", "公众持股市值", "Market Value of Public Float", "≥ USD 45M", "≥ USD 45M"),
        Criterion("public_spread", "公众持股数量", "Publicly Held Shares", "≥ 1,250,000 股", "≥ 1,250,000 shares"),
        Criterion("shareholders", "公众股东人数", "Round-lot Holders", "≥ 450 名整手股东，或 ≥ 2,200 名总股东", "≥ 450 round-lot holders, or ≥ 2,200 total holders"),
        Criterion("price", "最低股价", "Minimum Bid Price", "≥ USD 4.00", "≥ USD 4.00"),
        Criterion("governance", "公司治理", "Corporate Governance", "独立董事多数席位 + 审计/提名/薪酬委员会（SOX 全面合规）", "Majority independent board + audit/nomination/comp committees (full SOX)"),
        Criterion("reporting", "财务披露", "Financial Reporting", "US GAAP 或 IFRS 审计；季报 + 年报 (10-Q / 10-K)，具备投资级合规水准", "Audited US GAAP or IFRS; quarterly + annual filings; investor-grade compliance"),
    ],
)


@dataclass
class TierPair:
    my: ListingTier
    us: ListingTier
    rationale_zh: str
    rationale_en: str


_EARLY_PAIR = TierPair(
    my=ACE_MARKET,
    us=NASDAQ_CAPITAL,
    rationale_zh=(
        "当前阶段企业以模式验证和稳定经营为重点，尚未达到主板/旗舰板的盈利门槛。"
        "我们对标的是两个市场中「门槛最低的入门通道」——马来西亚 ACE 创业板和美国 NASDAQ Capital Market。"
    ),
    rationale_en=(
        "At this stage the priority is model validation and stable operations — well before main-board / flagship-tier earnings thresholds. "
        "We benchmark against the entry tier of each market: Bursa ACE Market and NASDAQ Capital Market."
    ),
)

_SCALING_PAIR = TierPair(
    my=MAIN_MARKET,
    us=NASDAQ_GLOBAL,
    rationale_zh=(
        "企业已进入规模扩张阶段，盈利与营收开始具备主板级潜力。"
        "我们对标的是马来西亚主板（盈利测试）和美国 NASDAQ Global Market 中阶板。"
    ),
    rationale_en=(
        "The company is scaling, with earnings and revenue approaching main-board territory. "
        "We benchmark against Bursa Main Market (Profit Test) and NASDAQ Global Market."
    ),
)

_CAPITAL_READY_PAIR = TierPair(
    my=MAIN_MARKET,
    us=NASDAQ_GLOBAL_SELECT,
    rationale_zh=(
        "企业已具备资本化条件，可以认真评估两地最严苛的旗舰上市路径。"
        "我们对标的是马来西亚主板和美国 NASDAQ Global Select 旗舰板。"
    ),
    rationale_en=(
        "The company is capital-ready and can credibly evaluate flagship listing pathways in both markets. "
        "We benchmark against Bursa Main Market and NASDAQ Global Select."
    ),
)


def pick_tiers_for_stage(stage: str | None) -> TierPair:
    """Auto-pick the appropriate Bursa + NASDAQ tier pair based on enterprise stage."""
    s = stage or ""
    if "资本进阶" in s:
        return _CAPITAL_READY_PAIR
    if "规模扩张" in s:
        return _SCALING_PAIR
    return _EARLY_PAIR


def render_markdown_comparison(pair: TierPair, language: str = "cn") -> str:
    """
    Render the picked tier pair as a side-by-side markdown table aligned by
    canonical criterion key. Rows where one jurisdiction has no requirement
    render as "—". The PDF generator's markdown 'tables' extension renders
    this cleanly in the final report PDF.
    """
    is_cn = language == "cn"
    my_header = pair.my.board_zh if is_cn else pair.my.board_en
    us_header = pair.us.board_zh if is_cn else pair.us.board_en
    col_header = "对比项" if is_cn else "Criterion"

    my_by_key = {c.key: c for c in pair.my.criteria}
    us_by_key = {c.key: c for c in pair.us.criteria}

    def val(c: Criterion | None) -> str:
        if c is None:
            return "—"
        return c.value_zh if is_cn else c.value_en

    lines: list[str] = []
    lines.append(f"| {col_header} | 🇲🇾 {my_header} | 🇺🇸 {us_header} |")
    lines.append("| --- | --- | --- |")
    for key, label_zh, label_en in CANONICAL_ROWS:
        my_c = my_by_key.get(key)
        us_c = us_by_key.get(key)
        # Skip rows where neither side has data
        if my_c is None and us_c is None:
            continue
        label = label_zh if is_cn else label_en
        lines.append(f"| **{label}** | {val(my_c)} | {val(us_c)} |")

    return "\n".join(lines)


def to_dict(pair: TierPair) -> dict:
    """Serialize a tier pair into a JSON-safe dict for content_data storage."""
    def tier_dict(t: ListingTier) -> dict:
        return {
            "code": t.code,
            "jurisdiction": t.jurisdiction,
            "regulator": t.regulator,
            "exchange_zh": t.exchange_zh,
            "exchange_en": t.exchange_en,
            "board_zh": t.board_zh,
            "board_en": t.board_en,
            "tagline_zh": t.tagline_zh,
            "tagline_en": t.tagline_en,
            "criteria": [
                {
                    "label_zh": c.label_zh,
                    "label_en": c.label_en,
                    "value_zh": c.value_zh,
                    "value_en": c.value_en,
                }
                for c in t.criteria
            ],
        }

    return {
        "my": tier_dict(pair.my),
        "us": tier_dict(pair.us),
        "rationale_zh": pair.rationale_zh,
        "rationale_en": pair.rationale_en,
    }
