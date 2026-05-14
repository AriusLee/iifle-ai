"""
Listing requirements reference data for the Unicorn Diagnostic Report.

Mirrors the customer-facing TypeScript module at
``customer/src/lib/listing-requirements.ts`` and exposes the same tier
auto-pick logic. Used by report_generator.py to embed deterministic
side-by-side requirement tables (MY / HK / US) into the diagnostic PDF
— the numbers are hard-coded here, the AI only writes narrative
commentary on top of them.

Tier sets by enterprise stage:
    概念萌芽期 / 初创探索期 / 模式验证期  →  ACE Market   +  HKEX GEM         +  NASDAQ Capital
    规模扩张期                            →  Main Market  +  HKEX Main Board  +  NASDAQ Global Market
    资本进阶期                            →  Main Market  +  HKEX Main Board  +  NASDAQ Global Select

The user's Q33 (退出方向) answer drives which column is highlighted as
the customer's preferred listing market.
"""

from dataclasses import dataclass
from typing import Literal

Jurisdiction = Literal["MY", "HK", "US"]


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
    jurisdiction: Jurisdiction
    regulator: Literal["SC", "SFC", "SEC"]
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

# ── Hong Kong — HKEX tiers ────────────────────────────────────────────────────

HKEX_GEM = ListingTier(
    code="HKEX_GEM",
    jurisdiction="HK",
    regulator="SFC",
    exchange_zh="香港交易所",
    exchange_en="HKEX",
    board_zh="GEM 创业板",
    board_en="GEM (Growth Enterprise Market)",
    tagline_zh="面向具备成长潜力的中小型企业，采用现金流测试，无强制盈利门槛。",
    tagline_en="For high-growth SMEs. Cash-flow test in lieu of mandatory profit threshold.",
    criteria=[
        Criterion("profit", "盈利要求", "Profit Requirement", "无强制盈利要求", "No mandatory profit threshold"),
        Criterion("revenue", "现金流测试", "Cash-Flow Test", "上市前 2 个财年合计经营现金流 ≥ HK$30M", "Aggregate positive operating cash flow ≥ HK$30M over 2 preceding financial years"),
        Criterion("market_value", "上市时市值", "Market Cap at Listing", "≥ HK$150M", "≥ HK$150M"),
        Criterion("history", "经营年限", "Operating History", "≥ 2 个财年同一管理层", "≥ 2 financial years under same management"),
        Criterion("public_spread", "公众持股", "Public Float", "≥ 25% 已发行股本", "≥ 25% of issued share capital"),
        Criterion("shareholders", "公众股东人数", "Public Shareholders", "≥ 100 名", "≥ 100 holders"),
        Criterion("sponsor", "保荐人", "Sponsor", "必须委任 HKEX 授权保荐人", "HKEX-licensed sponsor required"),
        Criterion("governance", "公司治理", "Corporate Governance", "≥ 3 名独立非执行董事（占 1/3 席位）+ 审计委员会", "≥ 3 INEDs (≥ 1/3 of board) + audit committee"),
    ],
)

HKEX_MAIN = ListingTier(
    code="HKEX_MAIN",
    jurisdiction="HK",
    regulator="SFC",
    exchange_zh="香港交易所",
    exchange_en="HKEX",
    board_zh="主板（盈利测试）",
    board_en="Main Board (Profit Test)",
    tagline_zh="面向已实现稳定盈利的成熟企业，盈利、市值、治理三方面均有明确门槛。",
    tagline_en="For mature, profitable companies. Hard thresholds on earnings, market cap, and governance.",
    criteria=[
        Criterion("profit", "盈利要求", "Profit Requirement", "过去 3 年累计税后利润 ≥ HK$80M，最近一年 ≥ HK$35M，前两年合计 ≥ HK$45M", "Aggregate PAT ≥ HK$80M over 3 yrs; latest yr ≥ HK$35M; sum of prior 2 yrs ≥ HK$45M"),
        Criterion("market_value", "上市时市值", "Market Cap at Listing", "≥ HK$500M", "≥ HK$500M"),
        Criterion("history", "经营年限", "Operating History", "≥ 3 个财年同一管理层", "≥ 3 financial years under same management"),
        Criterion("public_spread", "公众持股", "Public Float", "≥ 25% 已发行股本（大市值企业可降至 15–25%）", "≥ 25% of issued share capital (15–25% allowed for large caps)"),
        Criterion("shareholders", "公众股东人数", "Public Shareholders", "≥ 300 名", "≥ 300 holders"),
        Criterion("sponsor", "保荐人", "Sponsor", "必须委任 HKEX 授权保荐人，至少提前 2 个月委任", "HKEX-licensed sponsor required, appointed ≥ 2 months before submission"),
        Criterion("governance", "公司治理", "Corporate Governance", "≥ 3 名独立非执行董事（占 1/3 席位）+ 审计/提名/薪酬委员会", "≥ 3 INEDs (≥ 1/3 of board) + audit, nomination, remuneration committees"),
        Criterion("reporting", "财务披露", "Financial Reporting", "上市前 3 年经审计财务报表（HKFRS / IFRS）+ 中期报告", "3 yrs of audited financial statements (HKFRS / IFRS) + interim reporting"),
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
class TierSet:
    """Three-market tier set (MY / HK / US) auto-picked by enterprise stage."""
    my: ListingTier
    hk: ListingTier
    us: ListingTier
    rationale_zh: str
    rationale_en: str


_EARLY_SET = TierSet(
    my=ACE_MARKET,
    hk=HKEX_GEM,
    us=NASDAQ_CAPITAL,
    rationale_zh=(
        "当前阶段企业以模式验证和稳定经营为重点，尚未达到主板/旗舰板的盈利门槛。"
        "我们对标的是三个市场中「门槛最低的入门通道」——马来西亚 ACE 创业板、香港 GEM 创业板和美国 NASDAQ Capital Market。"
    ),
    rationale_en=(
        "At this stage the priority is model validation and stable operations — well before main-board / flagship-tier earnings thresholds. "
        "We benchmark against the entry tier of each market: Bursa ACE Market, HKEX GEM, and NASDAQ Capital Market."
    ),
)

_SCALING_SET = TierSet(
    my=MAIN_MARKET,
    hk=HKEX_MAIN,
    us=NASDAQ_GLOBAL,
    rationale_zh=(
        "企业已进入规模扩张阶段，盈利与营收开始具备主板级潜力。"
        "我们对标的是马来西亚主板（盈利测试）、香港主板（盈利测试）和美国 NASDAQ Global Market 中阶板。"
    ),
    rationale_en=(
        "The company is scaling, with earnings and revenue approaching main-board territory. "
        "We benchmark against Bursa Main Market (Profit Test), HKEX Main Board (Profit Test), and NASDAQ Global Market."
    ),
)

_CAPITAL_READY_SET = TierSet(
    my=MAIN_MARKET,
    hk=HKEX_MAIN,
    us=NASDAQ_GLOBAL_SELECT,
    rationale_zh=(
        "企业已具备资本化条件，可以认真评估三地最严苛的旗舰上市路径。"
        "我们对标的是马来西亚主板、香港主板和美国 NASDAQ Global Select 旗舰板。"
    ),
    rationale_en=(
        "The company is capital-ready and can credibly evaluate flagship listing pathways in all three markets. "
        "We benchmark against Bursa Main Market, HKEX Main Board, and NASDAQ Global Select."
    ),
)


def pick_tiers_for_stage(stage: str | None) -> TierSet:
    """Auto-pick the appropriate MY + HK + US tier set based on enterprise stage."""
    s = stage or ""
    if "资本进阶" in s:
        return _CAPITAL_READY_SET
    if "规模扩张" in s:
        return _SCALING_SET
    return _EARLY_SET


# Q33 (退出方向) answer → preferred listing market. Used to highlight the
# user's chosen column in the comparison table. Non-IPO answers (long-term,
# equity transaction, M&A, fundraise-then-exit) return None — no highlight.
_Q33_TO_JURISDICTION: dict[str, Jurisdiction] = {
    "未来美国上市": "US",
    "未来马来西亚上市": "MY",
    "未来香港上市": "HK",
}


def pick_highlight_from_q33(q33_answer: str | None) -> Jurisdiction | None:
    """Map the user's Q33 exit-direction answer to a jurisdiction to highlight."""
    if not q33_answer:
        return None
    return _Q33_TO_JURISDICTION.get(q33_answer.strip())


def render_markdown_comparison(
    tiers: TierSet,
    language: str = "cn",
    highlight: Jurisdiction | None = None,
) -> str:
    """
    Render the picked tier set as a side-by-side 3-column markdown table aligned by
    canonical criterion key. Rows where no jurisdiction has data are skipped;
    individual blank cells render as "—". The user's chosen market (from Q33)
    is highlighted with a star and bolded header. The PDF generator's markdown
    'tables' extension renders this cleanly in the final report PDF.
    """
    is_cn = language == "cn"
    col_header = "对比项" if is_cn else "Criterion"

    def header(t: ListingTier, flag: str) -> str:
        name = t.board_zh if is_cn else t.board_en
        if highlight == t.jurisdiction:
            return f"⭐ {flag} **{name}**"
        return f"{flag} {name}"

    my_header = header(tiers.my, "🇲🇾")
    hk_header = header(tiers.hk, "🇭🇰")
    us_header = header(tiers.us, "🇺🇸")

    my_by_key = {c.key: c for c in tiers.my.criteria}
    hk_by_key = {c.key: c for c in tiers.hk.criteria}
    us_by_key = {c.key: c for c in tiers.us.criteria}

    def val(c: Criterion | None) -> str:
        if c is None:
            return "—"
        return c.value_zh if is_cn else c.value_en

    lines: list[str] = []
    lines.append(f"| {col_header} | {my_header} | {hk_header} | {us_header} |")
    lines.append("| --- | --- | --- | --- |")
    for key, label_zh, label_en in CANONICAL_ROWS:
        my_c = my_by_key.get(key)
        hk_c = hk_by_key.get(key)
        us_c = us_by_key.get(key)
        # Skip rows where no jurisdiction has data
        if my_c is None and hk_c is None and us_c is None:
            continue
        label = label_zh if is_cn else label_en
        lines.append(f"| **{label}** | {val(my_c)} | {val(hk_c)} | {val(us_c)} |")

    return "\n".join(lines)


def to_dict(tiers: TierSet, highlight: Jurisdiction | None = None) -> dict:
    """Serialize a tier set into a JSON-safe dict for content_data storage."""
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
        "my": tier_dict(tiers.my),
        "hk": tier_dict(tiers.hk),
        "us": tier_dict(tiers.us),
        "highlight": highlight,
        "rationale_zh": tiers.rationale_zh,
        "rationale_en": tiers.rationale_en,
    }
