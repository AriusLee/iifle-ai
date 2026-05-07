"""
Scoring engine for the V2.1 45-question Unicorn Diagnostic Questionnaire.

Maps answers to 6 module scores + overall score + enterprise stage classification.

V2.1 changes (over V2):
- 45 questions (Q01-Q35 + Q36-Q45) — adds 10 SME bank-loan readiness questions
  inside Section E, mapped to bank underwriting metrics (DSCR, gearing, CCRIS,
  bank statements, revenue/profit trend).
- Block E now has two sub-blocks: E1 equity readiness (Q26-Q32, unchanged) and
  E2 bank-loan readiness (Q36-Q45, new). Both feed Module 4 with rebalanced
  weights (50% equity / 50% bank-loan).

V2 layout:
- Block A (Q01-Q08) → Stage classification
- Block B (Q09-Q13) → Module 1: Gene Structure
- Block C (Q14-Q20) → Module 2: Business Model
- Block D (Q21-Q25) → Module 3: Valuation
- Block E (Q26-Q32 + Q36-Q45) → Module 4: Financing (equity + bank-loan)
- Block F (Q33-Q34) → Module 5: Exit + Module 6: Listing
- Q35 → Report personalization (multi-select, no scoring)
"""

from decimal import Decimal

# ── Answer-to-score mappings ──────────────────────────────────────────────────
# Each question maps answer text → numeric score (0-100 scale).
# Q03 is classification only (industry), no score.
# Q32 is classification only (biggest obstacle), no score.
# Q35 is multi-select for report personalization, no score.

# Client requirement: standardized scoring ladder
# 5-option questions: 10 / 30 / 50 / 70 / 90
# 6-option questions: 10 / 25 / 40 / 60 / 75 / 90
# 4-option questions: 10 / 40 / 70 / 90
# Classification questions (Q03, Q23, Q32): not scored
# Q14 (revenue source): non-linear (business model quality varies by type)

SCORE_MAP: dict[str, dict[str, int]] = {
    # ══ Block A: Enterprise Profile (Q01-Q08) ═══════════════════════════════
    "Q01": {  # 企业成立多久 (5 options → 10/30/50/70/90)
        "还未正式开始": 10,
        "0–1年": 30,
        "1–3年": 50,
        "3–5年": 70,
        "5年以上": 90,
    },
    "Q02": {  # 创始人行业经验 (5 options)
        "0–1年": 10,
        "1–3年": 30,
        "3–5年": 50,
        "5–10年": 70,
        "10年以上": 90,
    },
    # Q03 is industry classification — no scoring
    "Q04": {  # 年营收区间 (6 options → 10/25/40/60/75/90)
        "还没有稳定营收": 10,
        "100万以下": 25,
        "100万–500万": 40,
        "500万–3000万": 60,
        "3000万–1亿": 75,
        "1亿以上": 90,
    },
    "Q05": {  # 经营利润状态 (5 options)
        "还在亏损": 10,
        "偶尔盈利": 30,
        "已经能稳定成交": 50,
        "持续稳定盈利": 70,
        "盈利能力较强": 90,
    },
    "Q06": {  # 团队规模 (6 options)
        "5人以下": 10,
        "6–10人": 25,
        "11–30人": 40,
        "31–100人": 60,
        "101–300人": 75,
        "300人以上": 90,
    },
    "Q07": {  # 经营状态 (4 options → 10/40/70/90)
        "还在试模式": 10,
        "已经能稳定成交": 40,
        "正在扩张": 70,
        "正在准备融资/资本动作": 90,
    },
    "Q08": {  # 企业更大目标 (5 options)
        "先活下来": 10,
        "先稳定盈利": 30,
        "先复制扩张": 50,
        "先做高估值逻辑": 70,
        "先进入融资/资本路径": 90,
    },

    # ══ Block B: Gene Structure (Q09-Q13) ═══════════════════════════════════
    "Q09": {  # 增长最依赖什么 (5 options)
        "创始人本人": 10,
        "少数销售高手": 30,
        "单一渠道": 30,
        "单一产品": 30,
        "团队与系统共同驱动": 90,
    },
    "Q10": {  # 最大驱动力 (5 options)
        "创始人个人能力": 10,
        "创始人+少数核心骨干": 30,
        "核心团队": 50,
        "团队+组织机制": 70,
        "已开始系统化运转": 90,
    },
    "Q11": {  # 企业定位清晰度 (5 options)
        "还比较模糊": 10,
        "大致清楚": 30,
        "较清楚": 50,
        "清楚且差异化明显": 70,
        "已形成行业标签/品牌认知": 90,
    },
    "Q12": {  # 离开创始人能否运转 (5 options)
        "几乎不能": 10,
        "较难": 30,
        "一部分可以": 50,
        "大部分可以": 70,
        "基本可以": 90,
    },
    "Q13": {  # 是否有管理层 (5 options)
        "没有": 10,
        "有少数核心骨干": 30,
        "有基础管理层": 50,
        "有较成熟管理层": 70,
        "已有系统化管理团队+决策机制": 90,
    },

    # ══ Block C: Business Model (Q14-Q20) ═══════════════════════════════════
    "Q14": {  # 收入来源 (6 options — non-linear by business model quality)
        "单次交易": 10,
        "项目制收入": 30,
        "长期复购": 50,
        "多种收入组合": 60,
        "平台抽成": 75,
        "订阅/月费": 90,
    },
    "Q15": {  # 复制成功率 (5 options)
        "很低几乎靠人": 10,
        "有机会但不稳定": 30,
        "中等部分可复制": 50,
        "较高已有初步方法": 70,
        "很高已有成熟SOP": 90,
    },
    "Q16": {  # 成交标准化 (5 options)
        "基本没有": 10,
        "有一些经验但不稳定": 30,
        "有基础流程": 50,
        "已有可训练SOP": 70,
        "已能复制给不同团队": 90,
    },
    "Q17": {  # 交付独立性 (5 options)
        "不能": 10,
        "较难": 30,
        "一部分可以": 50,
        "大部分可以": 70,
        "基本完全可以": 90,
    },
    "Q18": {  # 客户复购/转介绍 (5 options)
        "很少": 10,
        "偶尔": 30,
        "一般": 50,
        "较高": 70,
        "很高": 90,
    },
    "Q19": {  # 客户来源 (5 options)
        "主要靠创始人/熟人资源": 10,
        "主要靠转介绍": 30,
        "主要靠销售主动开发": 50,
        "主要靠渠道/平台/品牌流量": 70,
        "多渠道较均衡": 90,
    },
    "Q20": {  # 已验证增长信号 (5 options)
        "没有": 10,
        "有尝试但未验证": 30,
        "有少量验证": 50,
        "有明显验证": 70,
        "已形成区域复制基础": 90,
    },

    # ══ Block D: Valuation (Q21-Q25) ════════════════════════════════════════
    "Q21": {  # 增长方式 (6 options)
        "多开店 / 多开点": 25,
        "增加销售团队": 25,
        "增加经销商 / 渠道": 40,
        "产品升级与客户复购": 60,
        "区域扩张 / 跨国复制": 75,
        "平台化连接更多角色": 90,
    },
    "Q22": {  # 市场机会 (6 options)
        "目前还不清楚": 10,
        "本地刚需市场": 25,
        "区域连锁机会": 40,
        "全国性品牌机会": 60,
        "东南亚机会": 75,
        "全球性机会": 90,
    },
    # Q23 is classification (capital priority) — scored but non-linear
    "Q23": {
        "暂时还不清楚": 10,
        "门店 / 网点扩张": 30,
        "获客": 50,
        "团队建设": 50,
        "供应链 / 交付能力": 50,
        "品牌与市场": 70,
        "系统 / 技术": 70,
    },
    "Q24": {  # 增长核心逻辑 (4 options → 10/40/70/90)
        "稳定营收": 10,
        "成本优化": 40,
        "多城市复制": 70,
        "强品牌/流量/平台效应": 90,
    },
    "Q25": {  # 企业类型 (5 options)
        "靠老板赚钱的经营型公司": 10,
        "靠产品赚钱的业务型公司": 30,
        "可复制的成长型公司": 50,
        "可融资的资本型公司": 70,
        "具备平台化潜力的高估值公司": 90,
    },

    # ══ Block E: Financing (Q26-Q32) ════════════════════════════════════════
    "Q26": {  # 股权结构清晰度 (5 options)
        "没有": 10,
        "大致有，但不清楚": 30,
        "基本清楚": 50,
        "较清晰": 70,
        "非常清晰": 90,
    },
    "Q27": {  # 股东类型 (5 options)
        "全部创始人持有": 10,
        "有历史口头安排": 30,
        "有少量外部股东": 50,
        "有2轮以上投资人": 70,
        "有多轮投资人+员工持股计划": 90,
    },
    "Q28": {  # 财务规范化 (5 options)
        "没有": 10,
        "只有内部账": 30,
        "有基础财务报表": 50,
        "有1年年度审计": 70,
        "有2–3年审计 / 较规范财务体系": 90,
    },
    "Q29": {  # 资本动作意向 (6 options)
        "暂时不融资，先经营": 10,
        "想梳理商业模式": 25,
        "想做融资准备": 40,
        "想正式融资": 60,
        "想做并购 / 被并购准备": 75,
        "想走向上市路径": 90,
    },
    "Q30": {  # 融资时间预期 (4 options)
        "1年后再看": 10,
        "6–12个月": 40,
        "3–6个月内": 70,
        "已经在推进": 90,
    },
    "Q31": {  # 资本准备状态 (5 options)
        "还没开始准备": 10,
        "有想法但没材料": 30,
        "有基础资料但不完整": 50,
        "已开始系统整理融资资料": 70,
        "已能进入 BP / 路演准备": 90,
    },
    # Q32 is classification only (biggest obstacle) — no scoring

    # ══ Block E2: SME Bank-Loan Readiness (Q36-Q45) ════════════════════════
    # Bucketed against the bank's 5 core SME-loan criteria from the
    # "Bank Loan General Criterias" reference: DSCR > 1.0x, gearing < 3.0x,
    # credit-card utilisation < 70%, revenue/profit uptrend, healthy bank
    # statements (no bound cheque, ending balance 5-20% of deposits).
    # All on the standard 5-bucket 10/30/50/70/90 ladder.
    "Q36": {  # Latest PBT margin
        "亏损 / 负 PBT": 10,
        "盈亏平衡 (利润率 0–3%)": 30,
        "利润率 3–8%": 50,
        "利润率 8–15%": 70,
        "利润率 > 15%": 90,
    },
    "Q37": {  # Director's personal credit-card utilisation (bank red-line >70%)
        "> 70% (银行不接受)": 10,
        "50–70%": 30,
        "30–50%": 50,
        "10–30%": 70,
        "< 10% 或不使用信用卡": 90,
    },
    "Q38": {  # Ongoing legal cases
        "是，公司和董事都有": 10,
        "是，仅公司有": 30,
        "是，仅董事个人有": 30,
        "历史上有但已结案": 70,
        "完全没有": 90,
    },
    "Q39": {  # Years incorporated (bank min >1yr)
        "< 1 年 (低于银行最低要求)": 10,
        "1–2 年": 30,
        "2–3 年": 50,
        "3–5 年": 70,
        "> 5 年": 90,
    },
    "Q40": {  # Average month-end bank balance (bank prefers 5-20% of deposits)
        "几乎为零或负 (经常透支)": 10,
        "< 5% 月入": 30,
        "5–10% 月入": 50,
        "10–20% 月入 (银行偏好区间)": 90,  # bank sweet spot — top score
        "> 20% 月入": 70,                 # excessive idle cash, slightly below sweet spot
    },
    "Q41": {  # Gearing ratio (total borrowings / equity, bank red-line >3.0x)
        "> 3.0x (违反银行准则)": 10,
        "2.0–3.0x": 30,
        "1.0–2.0x": 50,
        "0.5–1.0x": 70,
        "< 0.5x 或无借贷": 90,
    },
    "Q42": {  # DSCR (EBITDA / annual borrowing commitments, bank red-line <1.0x)
        "< 1.0x (无法覆盖偿债)": 10,
        "1.0–1.25x (勉强覆盖)": 30,
        "1.25–1.5x": 50,
        "1.5–2.0x": 70,
        "> 2.0x (强偿债能力)": 90,
    },
    "Q43": {  # Latest shareholder equity (absolute scale)
        "负值 (技术性资不抵债)": 10,
        "< RM 50 万": 30,
        "RM 50 万 – 200 万": 50,
        "RM 200 万 – 1000 万": 70,
        "> RM 1000 万": 90,
    },
    "Q44": {  # CCRIS / late-payment record
        "经常迟缴 / CCRIS 不良记录": 10,
        "近 12 个月内有迟缴": 30,
        "近 12 个月无迟缴，更早曾有": 50,
        "近 24 个月无迟缴": 70,
        "从未迟缴": 90,
    },
    "Q45": {  # Revenue & profit trend (bank requires uptrend or stable)
        "双双下降": 10,
        "波动较大，无明显趋势": 30,
        "大致持平": 50,
        "稳定增长": 70,
        "持续高速增长": 90,
    },

    # ══ Block F: Exit + Listing (Q33-Q34) ══════════════════════════════════
    "Q33": {  # 退出方向 (5 options)
        "长期经营，不谈退出": 10,
        "未来股权交易": 30,
        "未来兼并收购": 50,
        "未来融资后再退出": 70,
        "未来上市退出": 90,
    },
    "Q34": {  # 上市准备状态 (5 options)
        "还非常早，不应现在讨论": 10,
        "先把经营和模式跑顺": 30,
        "可以开始补治理 / 财务 / 股权基础": 50,
        "可以开始做上市前体检": 70,
        "已开始认真思考上市路径": 90,
    },
    # Q35 is multi-select for report personalization — no scoring
}

# ── Module definitions ────────────────────────────────────────────────────────
# Which questions feed into which module, with weights per question.

MODULES = {
    1: {
        "name_zh": "基因结构",
        "name_en": "Gene Structure",
        "questions": {
            "Q09": 0.15,   # Growth dependency (lowered: overlap with founder dependency)
            "Q10": 0.20,   # Main driving force (keep high)
            "Q11": 0.20,   # Positioning clarity (raised per client)
            "Q12": 0.20,   # Run without founder (keep)
            "Q13": 0.25,   # Management layer (raised: emphasize succession capability)
        },
    },
    2: {
        "name_zh": "商业模式结构",
        "name_en": "Business Model",
        "questions": {
            "Q14": 0.10,   # Revenue source (keep)
            "Q15": 0.20,   # Replication success (keep high)
            "Q16": 0.15,   # Sales standardization (keep)
            "Q17": 0.15,   # Delivery independence (keep)
            "Q18": 0.15,   # Customer retention (raised per client)
            "Q19": 0.05,   # Customer source (lowered per client)
            "Q20": 0.20,   # Growth validation (keep high)
        },
    },
    3: {
        "name_zh": "估值结构",
        "name_en": "Valuation",
        "questions": {
            "Q21": 0.20,   # Growth method (keep)
            "Q22": 0.25,   # Market opportunity (raised per client)
            "Q23": 0.05,   # Capital priority (lowered per client)
            "Q24": 0.30,   # Growth core logic (raised per client)
            "Q25": 0.20,   # Enterprise type (lowered: self-perception bias)
        },
    },
    4: {
        "name_zh": "融资结构",
        "name_en": "Financing",
        # V2.1: financing now combines equity-readiness (E1, Q26-Q32) and
        # bank-loan-readiness (E2, Q36-Q45) into a single module score.
        # Weight split is 50/50 — the two pathways are equally important
        # and orthogonal (most SMEs need both at different stages).
        # Within each half, weights mirror the bank's emphasis (DSCR + CCRIS
        # heaviest on the loan side; equity clarity + financial standardization
        # heaviest on the equity side).
        "questions": {
            # E1 · Equity readiness — 50% of module (prior weights × 0.5)
            "Q26": 0.125,  # Equity structure clarity
            "Q27": 0.05,   # Shareholder type
            "Q28": 0.15,   # Financial standardization (key readiness indicator)
            "Q29": 0.025,  # Capital action intent (intent ≠ capability)
            "Q30": 0.025,  # Fundraising timeline (intent ≠ capability)
            "Q31": 0.125,  # Capital readiness
            # E2 · SME Bank-Loan readiness — 50% of module
            "Q36": 0.06,   # PBT margin
            "Q37": 0.04,   # Credit-card utilisation
            "Q38": 0.05,   # Ongoing legal cases
            "Q39": 0.03,   # Years incorporated (overlaps with Q01, lower weight)
            "Q40": 0.05,   # Bank statement ending balance
            "Q41": 0.06,   # Gearing ratio
            "Q42": 0.07,   # DSCR (single most important bank metric)
            "Q43": 0.04,   # Shareholder equity (absolute scale)
            "Q44": 0.05,   # CCRIS / late-payment record
            "Q45": 0.05,   # Revenue & profit trend
        },
    },
    5: {
        "name_zh": "退出结构",
        "name_en": "Exit",
        "questions": {
            "Q33": 0.50,   # Exit direction
            "Q34": 0.50,   # IPO readiness
        },
    },
    6: {
        "name_zh": "上市结构",
        "name_en": "Listing",
        # NOTE: Module 6 uses shared questions but is displayed as reference only.
        # It does NOT contribute to the main overall score (see MODULE_WEIGHTS).
        "questions": {
            "Q28": 0.25,   # Financial standardization (shared with M4)
            "Q31": 0.20,   # Capital readiness (shared with M4)
            "Q34": 0.55,   # IPO readiness (shared with M5)
        },
    },
}

# Overall module weights for the main score
# Client feedback: Exit/Listing are forward-looking reference dimensions,
# should not dominate Phase 1 score. Module 6 excluded from main total
# (displayed as reference only) to avoid shared-question double-counting.
MODULE_WEIGHTS = {
    1: 0.20,  # Gene (keep)
    2: 0.28,  # Business Model (raised: core of replicability)
    3: 0.22,  # Valuation (raised: growth potential)
    4: 0.20,  # Financing (raised: readiness focus)
    5: 0.05,  # Exit (lowered: forward-looking reference)
    6: 0.05,  # Listing (lowered: forward-looking reference, shared questions)
}

# ── Enterprise stage classification ──────────────────────────────────────────

# Client feedback: raise objective maturity indicators, lower subjective ambition
STAGE_QUESTIONS = ["Q01", "Q02", "Q04", "Q05", "Q06", "Q07", "Q08"]
STAGE_WEIGHTS = {
    "Q01": 0.10,  # Years established (keep)
    "Q02": 0.05,  # Founder experience (lowered: subjective background)
    "Q04": 0.25,  # Revenue range (raised: objective maturity)
    "Q05": 0.20,  # Profit status (keep)
    "Q06": 0.15,  # Team size (raised: org maturity)
    "Q07": 0.15,  # Business state (keep)
    "Q08": 0.10,  # Current goal (lowered: subjective ambition)
}


def classify_enterprise_stage(stage_score: float) -> str:
    """Classify enterprise stage from weighted stage score."""
    if stage_score >= 80:
        return "资本进阶期 (Capital Advancement)"
    elif stage_score >= 60:
        return "规模扩张期 (Scaling Phase)"
    elif stage_score >= 40:
        return "模式验证期 (Model Validation)"
    elif stage_score >= 20:
        return "初创探索期 (Early Exploration)"
    else:
        return "概念萌芽期 (Pre-startup)"


def get_overall_rating(score: float) -> str:
    """Map overall score to a rating label."""
    if score >= 85:
        return "独角兽潜力 (Unicorn Potential)"
    elif score >= 70:
        return "高成长潜力 (High Growth)"
    elif score >= 55:
        return "中等成长潜力 (Moderate Growth)"
    elif score >= 40:
        return "基础成长阶段 (Foundation Stage)"
    else:
        return "早期探索阶段 (Early Stage)"


def get_capital_readiness(score: float) -> str:
    """Map overall score to capital readiness traffic light."""
    if score >= 65:
        return "green"
    elif score >= 45:
        return "amber"
    else:
        return "red"


def get_module_rating(score: float) -> str:
    """Map module score to a rating label."""
    if score >= 80:
        return "Strong"
    elif score >= 60:
        return "Medium"
    elif score >= 40:
        return "Developing"
    else:
        return "Weak"


# ── Core scoring function ────────────────────────────────────────────────────


def _get_answer_score(question: str, answer: str | None) -> float | None:
    """Look up the score for a given answer. Returns None if unanswered or 'other'."""
    if not answer or question not in SCORE_MAP:
        return None
    # Try exact match first
    if answer in SCORE_MAP[question]:
        return float(SCORE_MAP[question][answer])
    # Try fuzzy match (strip whitespace, normalize)
    normalized = answer.strip()
    for key, val in SCORE_MAP[question].items():
        if key.strip() == normalized:
            return float(val)
    # "Other" answers get a middle score
    if "其他" in answer:
        return 40.0
    return 40.0  # default for unrecognized


def score_diagnostic(answers: dict) -> dict:
    """
    Score a complete diagnostic questionnaire.

    Args:
        answers: {"Q01": "3-5年", "Q02": "5-10年", ..., "Q35": [...]}

    Returns:
        {
            "overall_score": 62.5,
            "overall_rating": "中等成长潜力 (Moderate Growth)",
            "enterprise_stage": "模式验证期 (Model Validation)",
            "capital_readiness": "amber",
            "module_scores": {
                "1": {"name_zh": "基因结构", "name_en": "Gene Structure", "score": 72, "rating": "Medium", ...},
                ...
            },
            "stage_score": 55.0,
            "question_scores": {"Q01": 75, "Q02": 75, ...},
            "key_findings": [...]
        }
    """
    # 1. Score individual questions
    question_scores: dict[str, float] = {}
    for q_num in range(1, 46):
        qid = f"Q{q_num:02d}"
        if qid in ("Q03", "Q32"):
            continue  # classification only
        answer = answers.get(qid)
        score = _get_answer_score(qid, answer)
        if score is not None:
            question_scores[qid] = score

    # 2. Calculate enterprise stage
    stage_score = 0.0
    stage_weight_sum = 0.0
    for qid, weight in STAGE_WEIGHTS.items():
        if qid in question_scores:
            stage_score += question_scores[qid] * weight
            stage_weight_sum += weight
    if stage_weight_sum > 0:
        stage_score = stage_score / stage_weight_sum * 1.0  # normalize
    enterprise_stage = classify_enterprise_stage(stage_score)

    # 3. Calculate module scores
    module_results = {}
    for mod_num, mod_def in MODULES.items():
        weighted_sum = 0.0
        weight_sum = 0.0
        q_details = {}

        for qid, weight in mod_def["questions"].items():
            if qid in question_scores:
                weighted_sum += question_scores[qid] * weight
                weight_sum += weight
                q_details[qid] = {
                    "answer": answers.get(qid, ""),
                    "score": question_scores[qid],
                    "weight": weight,
                }

        mod_score = (weighted_sum / weight_sum) if weight_sum > 0 else 0.0
        module_results[str(mod_num)] = {
            "name_zh": mod_def["name_zh"],
            "name_en": mod_def["name_en"],
            "score": round(mod_score, 1),
            "rating": get_module_rating(mod_score),
            "questions": q_details,
        }

    # 4. Calculate overall score
    overall_score = 0.0
    overall_weight_sum = 0.0
    for mod_num, weight in MODULE_WEIGHTS.items():
        mod_data = module_results.get(str(mod_num))
        if mod_data and mod_data["score"] > 0:
            overall_score += mod_data["score"] * weight
            overall_weight_sum += weight
    if overall_weight_sum > 0:
        overall_score = overall_score / overall_weight_sum

    # 5. Detect key findings
    key_findings = _detect_findings(answers, question_scores, module_results)

    return {
        "overall_score": round(overall_score, 1),
        "overall_rating": get_overall_rating(overall_score),
        "enterprise_stage": enterprise_stage,
        "capital_readiness": get_capital_readiness(overall_score),
        "module_scores": module_results,
        "stage_score": round(stage_score, 1),
        "question_scores": {k: round(v, 1) for k, v in question_scores.items()},
        "key_findings": key_findings,
        "industry": answers.get("Q03", ""),
        "biggest_obstacle": answers.get("Q32", ""),
        "report_focus": answers.get("Q35", []),
    }


def _detect_findings(
    answers: dict, scores: dict[str, float], modules: dict
) -> list[dict]:
    """Detect key findings and bottlenecks from questionnaire answers."""
    findings = []

    # Founder dependency — check gene-related questions
    q09 = scores.get("Q09", 50)
    q11 = scores.get("Q11", 50)
    q13 = scores.get("Q13", 50)
    if q09 <= 25 or q13 <= 30:
        findings.append({
            "type": "bottleneck",
            "severity": "high",
            "title_zh": "创始人依赖度过高",
            "title_en": "High Founder Dependency",
            "description_zh": "企业增长和运营高度依赖创始人个人，缺乏组织化驱动力。这是做大做强的最大障碍之一。",
            "description_en": "Enterprise growth and operations heavily depend on the founder. Lack of organizational structure is a key barrier to scaling.",
            "module": 1,
        })

    # Low replicability
    q12 = scores.get("Q12", 50)
    if q11 <= 30 or q12 <= 25:
        findings.append({
            "type": "bottleneck",
            "severity": "high",
            "title_zh": "商业模式可复制性低",
            "title_en": "Low Business Model Replicability",
            "description_zh": "企业缺乏标准化流程和SOP，复制到新市场的成功率低。需要先建立可复制的运营体系。",
            "description_en": "Lack of standardized processes and SOPs. Low replication success rate to new markets.",
            "module": 1,
        })

    # Revenue model risk
    q10 = scores.get("Q10", 50)
    q14 = scores.get("Q14", 50)
    if q10 <= 30 and q14 <= 30:
        findings.append({
            "type": "bottleneck",
            "severity": "medium",
            "title_zh": "收入结构单一且复购率低",
            "title_en": "Single Revenue Stream with Low Retention",
            "description_zh": "收入依赖单次交易，客户复购率低。建议建立订阅或复购机制，提升收入可预测性。",
            "description_en": "Revenue relies on one-time transactions with low customer retention.",
            "module": 1,
        })

    # Growth validation weakness (new Q20)
    q20 = scores.get("Q20", 50)
    if q20 <= 25:
        findings.append({
            "type": "gap",
            "severity": "medium",
            "title_zh": "增长模式尚未验证",
            "title_en": "Growth Model Not Yet Validated",
            "description_zh": "企业的增长模式尚未得到市场验证，建议先在小范围内验证可复制性后再推进扩张。",
            "description_en": "Growth model has not been validated by the market. Consider small-scale validation before expansion.",
            "module": 2,
        })

    # Financial/governance gap
    q21 = scores.get("Q21", 50)
    q22 = scores.get("Q22", 50)
    if q22 <= 40:
        findings.append({
            "type": "gap",
            "severity": "high" if q22 <= 20 else "medium",
            "title_zh": "财务规范化程度不足",
            "title_en": "Insufficient Financial Standardization",
            "description_zh": "缺乏规范化财务体系或审计基础，这将严重限制融资和上市的可能性。",
            "description_en": "Lack of standardized financials or audit foundation limits fundraising and listing possibilities.",
            "module": 3,
        })

    if q21 <= 25:
        findings.append({
            "type": "gap",
            "severity": "medium",
            "title_zh": "股权结构不清晰",
            "title_en": "Unclear Equity Structure",
            "description_zh": "股权结构尚未清晰化，这是进入资本路径的前提条件。建议尽快梳理。",
            "description_en": "Equity structure not yet clarified — a prerequisite for capital pathway.",
            "module": 3,
        })

    # Shareholder structure risk (new Q27)
    q27 = scores.get("Q27", 50)
    if q27 <= 30:
        findings.append({
            "type": "gap",
            "severity": "medium",
            "title_zh": "股东结构单一或不规范",
            "title_en": "Simple or Informal Shareholder Structure",
            "description_zh": "股东结构过于单一或仅有口头安排，缺乏正式化的股权协议，影响融资吸引力。",
            "description_en": "Shareholder structure is too simple or based on informal arrangements, affecting fundraising appeal.",
            "module": 4,
        })

    # Financing readiness gap
    q28 = scores.get("Q28", 50)
    q30 = scores.get("Q30", 50)
    if q28 <= 25 and q30 >= 70:
        findings.append({
            "type": "bottleneck",
            "severity": "high",
            "title_zh": "融资准备与时间线不匹配",
            "title_en": "Financing Preparation Mismatched with Timeline",
            "description_zh": "融资时间线较紧迫但融资材料准备不足，建议立即启动BP和融资材料的系统化整理。",
            "description_en": "Fundraising timeline is urgent but preparation materials are insufficient. Start BP and material preparation immediately.",
            "module": 4,
        })

    # Strong potential signals
    overall_bm = modules.get("2", {}).get("score", 0)
    overall_valuation = modules.get("3", {}).get("score", 0)
    if overall_bm >= 70 and overall_valuation >= 65:
        findings.append({
            "type": "strength",
            "severity": "low",
            "title_zh": "商业模式成熟度高，具备规模化潜力",
            "title_en": "Mature Business Model with Scaling Potential",
            "description_zh": "商业模式已具备较高成熟度和可复制性，结合增长潜力，适合进入资本化加速阶段。",
            "description_en": "Business model shows high maturity and replicability. Combined with growth potential, ready for capital acceleration.",
            "module": 2,
        })

    gene = modules.get("1", {}).get("score", 0)
    if gene >= 75:
        findings.append({
            "type": "strength",
            "severity": "low",
            "title_zh": "企业基因强劲",
            "title_en": "Strong Enterprise DNA",
            "description_zh": "企业已具备组织化运营能力，创始人依赖度较低，团队驱动力强。是做大的基础。",
            "description_en": "Enterprise has strong organizational capability with low founder dependency.",
            "module": 1,
        })

    return findings


# ── Section-to-module mapping ───────────────────────────────────────────────

SECTION_MODULE_MAP: dict[str, list[int]] = {
    "a": [],          # Stage classification only, no module
    "b": [1],         # Gene Structure
    "c": [2],         # Business Model
    "d": [3],         # Valuation
    "e": [4],         # Financing
    "f": [5, 6],      # Exit + Listing (Module 6 uses shared questions)
}

# Which questions belong to each section
SECTION_QUESTIONS: dict[str, list[str]] = {
    "a": ["Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08"],
    "b": ["Q09", "Q10", "Q11", "Q12", "Q13"],
    "c": ["Q14", "Q15", "Q16", "Q17", "Q18", "Q19", "Q20"],
    "d": ["Q21", "Q22", "Q23", "Q24", "Q25"],
    "e": [
        # E1 · Equity readiness
        "Q26", "Q27", "Q28", "Q29", "Q30", "Q31", "Q32",
        # E2 · SME Bank-Loan readiness
        "Q36", "Q37", "Q38", "Q39", "Q40", "Q41", "Q42", "Q43", "Q44", "Q45",
    ],
    "f": ["Q33", "Q34", "Q35"],
}

# Findings are assigned to sections based on which section's questions they primarily depend on
_FINDING_SECTIONS: dict[str, list[str]] = {
    # Section B findings (depend on Q09-Q13)
    "b": ["founder_dependency", "low_replicability"],
    # Section C findings (depend on Q14-Q20, plus cross-check with B)
    "c": ["revenue_model_risk", "growth_validation"],
    # Section D findings (depend on Q21-Q25)
    "d": ["financial_gap", "equity_gap"],
    # Section E findings (depend on Q26-Q32)
    "e": ["shareholder_risk", "financing_mismatch"],
    # Cross-module strengths (checked when later module is scored)
    "c_cross": ["bm_valuation_strength"],
    "b_cross": ["gene_strength"],
}


def _detect_section_findings(
    answers: dict, scores: dict[str, float], modules: dict, section_key: str
) -> list[dict]:
    """Detect findings relevant to a specific section."""
    findings: list[dict] = []

    if section_key == "b":
        q09 = scores.get("Q09", 50)
        q13 = scores.get("Q13", 50)
        if q09 <= 25 or q13 <= 30:
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "创始人依赖度过高", "title_en": "High Founder Dependency",
                "description_zh": "企业增长和运营高度依赖创始人个人，缺乏组织化驱动力。这是做大做强的最大障碍之一。",
                "description_en": "Enterprise growth and operations heavily depend on the founder. Lack of organizational structure is a key barrier to scaling.",
                "module": 1,
            })
        q11 = scores.get("Q11", 50)
        q12 = scores.get("Q12", 50)
        if q11 <= 30 or q12 <= 25:
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "商业模式可复制性低", "title_en": "Low Business Model Replicability",
                "description_zh": "企业缺乏标准化流程和SOP，复制到新市场的成功率低。需要先建立可复制的运营体系。",
                "description_en": "Lack of standardized processes and SOPs. Low replication success rate to new markets.",
                "module": 1,
            })
        # Gene strength
        gene = modules.get("1", {}).get("score", 0)
        if gene >= 75:
            findings.append({
                "type": "strength", "severity": "low",
                "title_zh": "企业基因强劲", "title_en": "Strong Enterprise DNA",
                "description_zh": "企业已具备组织化运营能力，创始人依赖度较低，团队驱动力强。是做大的基础。",
                "description_en": "Enterprise has strong organizational capability with low founder dependency.",
                "module": 1,
            })

    elif section_key == "c":
        q10 = scores.get("Q10", 50)
        q14 = scores.get("Q14", 50)
        if q10 <= 30 and q14 <= 30:
            findings.append({
                "type": "bottleneck", "severity": "medium",
                "title_zh": "收入结构单一且复购率低", "title_en": "Single Revenue Stream with Low Retention",
                "description_zh": "收入依赖单次交易，客户复购率低。建议建立订阅或复购机制，提升收入可预测性。",
                "description_en": "Revenue relies on one-time transactions with low customer retention.",
                "module": 1,
            })
        q20 = scores.get("Q20", 50)
        if q20 <= 25:
            findings.append({
                "type": "gap", "severity": "medium",
                "title_zh": "增长模式尚未验证", "title_en": "Growth Model Not Yet Validated",
                "description_zh": "企业的增长模式尚未得到市场验证，建议先在小范围内验证可复制性后再推进扩张。",
                "description_en": "Growth model has not been validated by the market. Consider small-scale validation before expansion.",
                "module": 2,
            })

    elif section_key == "d":
        q22 = scores.get("Q22", 50)
        if q22 <= 40:
            findings.append({
                "type": "gap", "severity": "high" if q22 <= 20 else "medium",
                "title_zh": "财务规范化程度不足", "title_en": "Insufficient Financial Standardization",
                "description_zh": "缺乏规范化财务体系或审计基础，这将严重限制融资和上市的可能性。",
                "description_en": "Lack of standardized financials or audit foundation limits fundraising and listing possibilities.",
                "module": 3,
            })
        q21 = scores.get("Q21", 50)
        if q21 <= 25:
            findings.append({
                "type": "gap", "severity": "medium",
                "title_zh": "股权结构不清晰", "title_en": "Unclear Equity Structure",
                "description_zh": "股权结构尚未清晰化，这是进入资本路径的前提条件。建议尽快梳理。",
                "description_en": "Equity structure not yet clarified — a prerequisite for capital pathway.",
                "module": 3,
            })
        # Cross-module: BM + Valuation strength
        overall_bm = modules.get("2", {}).get("score", 0)
        overall_valuation = modules.get("3", {}).get("score", 0)
        if overall_bm >= 70 and overall_valuation >= 65:
            findings.append({
                "type": "strength", "severity": "low",
                "title_zh": "商业模式成熟度高，具备规模化潜力", "title_en": "Mature Business Model with Scaling Potential",
                "description_zh": "商业模式已具备较高成熟度和可复制性，结合增长潜力，适合进入资本化加速阶段。",
                "description_en": "Business model shows high maturity and replicability. Combined with growth potential, ready for capital acceleration.",
                "module": 2,
            })

    elif section_key == "e":
        # ── E1 · Equity readiness findings ──────────────────────────────
        q27 = scores.get("Q27", 50)
        if q27 <= 30:
            findings.append({
                "type": "gap", "severity": "medium",
                "title_zh": "股东结构单一或不规范", "title_en": "Simple or Informal Shareholder Structure",
                "description_zh": "股东结构过于单一或仅有口头安排，缺乏正式化的股权协议，影响融资吸引力。",
                "description_en": "Shareholder structure is too simple or based on informal arrangements, affecting fundraising appeal.",
                "module": 4,
            })
        q28 = scores.get("Q28", 50)
        q30 = scores.get("Q30", 50)
        if q28 <= 25 and q30 >= 70:
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "融资准备与时间线不匹配", "title_en": "Financing Preparation Mismatched with Timeline",
                "description_zh": "融资时间线较紧迫但融资材料准备不足，建议立即启动BP和融资材料的系统化整理。",
                "description_en": "Fundraising timeline is urgent but preparation materials are insufficient. Start BP and material preparation immediately.",
                "module": 4,
            })

        # ── E2 · SME Bank-Loan red-flag findings ────────────────────────
        # These mirror the bank's 5 core SME-loan criteria. Each red-line
        # answer fires a specific high-severity finding so the customer sees
        # an actionable card even if the AI narrative misses it.
        q37 = scores.get("Q37", 50)
        if q37 <= 10:  # credit-card utilisation > 70% → bank red-line
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "董事信用卡使用率超过 70%（银行红线）",
                "title_en": "Director Credit-Card Utilisation Above 70% (Bank Red-Line)",
                "description_zh": "银行将此视为个人现金流压力的直接信号，会直接拒批。建议在递件前 3–6 个月将所有持卡余额降到额度 30% 以下，并保留至少 2 个月对账单证明。",
                "description_en": "Banks treat this as a direct signal of personal cash-flow stress and will reject the application. Bring every card below 30% utilisation 3–6 months before submission and retain ≥2 months of statements as proof.",
                "module": 4,
            })

        q38 = scores.get("Q38", 50)
        if q38 <= 30:  # ongoing legal cases (company or director)
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "公司或董事存在进行中的法律诉讼",
                "title_en": "Active Legal Cases Against Company or Directors",
                "description_zh": "银行 CTOS/法务尽调阶段会直接发现并拒批。建议先咨询律师评估和解或撤诉路径，结案后再申请；如果是商业纠纷，准备一份独立的解释信和担保文件。",
                "description_en": "Banks discover this during CTOS/legal due diligence and reject outright. Consult counsel on settlement or dismissal first, then apply post-resolution; for commercial disputes, prepare a separate explanation letter and indemnity.",
                "module": 4,
            })

        q41 = scores.get("Q41", 50)
        if q41 <= 10:  # gearing > 3.0x — fails bank's gearing test
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "资产负债率超过 3.0 倍（违反银行准则）",
                "title_en": "Gearing Ratio Above 3.0x (Fails Bank Criterion)",
                "description_zh": "银行硬性要求资产负债率 < 3.0x。建议（1）注资增加股东权益，（2）将部分股东借款转为股本，（3）偿还高息短期借贷压低分子；任一动作落实后再递件。",
                "description_en": "Banks require gearing < 3.0x. Options: (1) inject capital to raise equity, (2) convert shareholder loans to equity, (3) pay down high-interest short-term debt to lower the numerator. Apply only after one of these is in place.",
                "module": 4,
            })

        q42 = scores.get("Q42", 50)
        if q42 <= 30:  # DSCR < 1.25x — barely or cannot cover debt service
            sev = "high" if q42 <= 10 else "medium"
            findings.append({
                "type": "bottleneck", "severity": sev,
                "title_zh": "DSCR 低于 1.25 倍（偿债能力不足）",
                "title_en": "DSCR Below 1.25x (Insufficient Debt-Service Capacity)",
                "description_zh": "DSCR = EBITDA ÷ 年度偿债，银行最低 1.0x，安全 1.5x+。建议（1）压低偿债分母——延长还款期或合并贷款，（2）抬高 EBITDA 分子——剥离亏损业务、提高毛利。先把 DSCR 拉到 1.5x 再申请新贷款。",
                "description_en": "DSCR = EBITDA ÷ annual debt service; bank floor is 1.0x, comfortable is 1.5x+. Either lower the denominator (extend tenure, consolidate loans) or raise EBITDA (cut loss-making lines, lift margin). Get DSCR to 1.5x before requesting new facilities.",
                "module": 4,
            })

        q43 = scores.get("Q43", 50)
        if q43 <= 10:  # negative equity — technical insolvency
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "股东权益为负（技术性资不抵债）",
                "title_en": "Negative Shareholder Equity (Technically Insolvent)",
                "description_zh": "账面已资不抵债，银行视为最高风险。先做股东注资或债转股将权益翻正，同步审计公司，否则任何贷款申请都会被驳回。",
                "description_en": "The company is technically insolvent on paper — banks treat this as the highest risk tier. Inject capital or convert debt to equity to flip equity positive, and run a fresh audit. Otherwise every loan application will be rejected.",
                "module": 4,
            })

        q44 = scores.get("Q44", 50)
        if q44 <= 10:  # CCRIS adverse / frequent late — bank red-line
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "现有借贷频繁迟缴 / CCRIS 不良记录",
                "title_en": "Frequent Late Payments / Adverse CCRIS Record",
                "description_zh": "CCRIS 不良记录是银行最关键的拒批信号之一。建议（1）立刻清算所有逾期，（2）保持至少 12 个月按时还款记录后再申请，（3）期间避免任何新增贷款查询。这一项无法绕过，只能用时间修复。",
                "description_en": "Adverse CCRIS is one of the strongest auto-reject signals. (1) Clear every overdue immediately, (2) maintain ≥12 months of on-time payments before reapplying, (3) avoid any new credit enquiries in that window. This cannot be shortcut — only time fixes it.",
                "module": 4,
            })
        elif q44 <= 30:  # late within last 12 months — recoverable but flagged
            findings.append({
                "type": "gap", "severity": "medium",
                "title_zh": "近 12 个月内有迟缴记录",
                "title_en": "Late Payment Within Last 12 Months",
                "description_zh": "近期迟缴会显著降低批贷概率，但比 CCRIS 不良记录可挽救。建议（1）从现在起严格按时还款，建立 12 个月清白记录，（2）若是单次错过且有合理理由，准备书面说明附在申请中，（3）避免短期内多次贷款查询拉低评分。",
                "description_en": "Recent late payments significantly lower approval probability but are recoverable (unlike adverse CCRIS). (1) Maintain strict on-time payments to build a 12-month clean record, (2) if it was a one-off with a justifiable reason, attach a written explanation, (3) avoid multiple credit enquiries that further depress the score.",
                "module": 4,
            })

        q45 = scores.get("Q45", 50)
        if q45 <= 10:  # revenue & profit declining — fails bank trend criterion
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "营收和利润处于下降趋势（违反银行准则）",
                "title_en": "Revenue & Profit on a Decline (Fails Bank Criterion)",
                "description_zh": "银行准则明确要求营收/利润上升或稳定。下降趋势会被视为生意走下坡的信号。建议（1）找到下滑根源（行业、竞争、产品老化）并先稳住，（2）至少做出 2 个连续季度的回升数据再申请，（3）申请时附上回升解释和未来 12 个月的现金流预测。",
                "description_en": "The bank explicitly requires uptrend or stable revenue/profit. A decline signals a business in deterioration. (1) Diagnose the root cause (industry, competition, product) and stabilise first, (2) build at least 2 consecutive quarters of recovery data before applying, (3) attach a recovery narrative and 12-month forward cash-flow projection with the application.",
                "module": 4,
            })

        q40 = scores.get("Q40", 50)
        if q40 <= 10:  # near-zero / overdrawn ending balance
            findings.append({
                "type": "bottleneck", "severity": "high",
                "title_zh": "银行月结单月末余额接近零或经常透支",
                "title_en": "Near-Zero or Overdrawn Bank Statement Ending Balance",
                "description_zh": "银行调阅 6 个月流水时若月末经常归零或透支，会直接判定现金流不健康。建议在申请前 6 个月开始保留每月入账的 5–20% 作为月末余额，避免任何退票或透支。",
                "description_en": "When banks pull 6 months of statements and see chronically zero or overdrawn ending balances, they conclude cash flow is unhealthy. Starting 6 months pre-application, hold 5–20% of monthly deposits as ending balance and avoid any bounced cheques or overdrafts.",
                "module": 4,
            })

        q39 = scores.get("Q39", 50)
        if q39 <= 10:  # incorporated < 1 year — below bank minimum
            findings.append({
                "type": "gap", "severity": "high",
                "title_zh": "公司注册不满 1 年（低于银行最低要求）",
                "title_en": "Company Incorporated < 1 Year (Below Bank Minimum)",
                "description_zh": "几乎所有 SME 银行贷款要求营业满 1 年以上。在此之前可考虑（1）股东个人贷款，（2）信用卡 / 透支额度，（3）政府担保的早期 SME 计划（如 BSN、TEKUN），（4）等待并积累 12 个月银行流水后再申请正式 SME 贷款。",
                "description_en": "Nearly all SME bank loans require 1+ year of operations. Until then consider: (1) shareholder personal loans, (2) credit card / overdraft facilities, (3) government-backed early-stage SME schemes (BSN, TEKUN), (4) wait and accumulate 12 months of bank statements before applying for formal SME loans.",
                "module": 4,
            })

        # ── E2 · Strength when bank-loan readiness is genuinely strong ──
        if (
            scores.get("Q42", 0) >= 70    # DSCR ≥ 1.5x
            and scores.get("Q41", 0) >= 70  # gearing < 1.0x
            and scores.get("Q44", 0) >= 70  # 24+ months clean
            and scores.get("Q45", 0) >= 70  # revenue/profit uptrend
            and scores.get("Q43", 0) >= 50  # equity ≥ RM 500K
        ):
            findings.append({
                "type": "strength", "severity": "low",
                "title_zh": "银行 SME 贷款已具备申请条件",
                "title_en": "Bank-Loan-Ready by SME Underwriting Standards",
                "description_zh": "DSCR、资产负债率、CCRIS、营收趋势、股东权益均通过银行核心准则。建议在 3 个月内主动接洽 2–3 家银行做利率比价，把杠杆用在扩张而不是补现金流。",
                "description_en": "DSCR, gearing, CCRIS, revenue trend, and equity all clear the bank's core thresholds. Approach 2–3 banks within 3 months to compare rates and deploy the leverage for expansion rather than cash-flow patching.",
                "module": 4,
            })

    return findings


def score_section(answers: dict, section_key: str) -> dict:
    """
    Score a single section of the questionnaire.

    Returns:
        {
            "section": "b",
            "enterprise_stage": "...",   # only for section a
            "stage_score": 55.0,         # only for section a
            "module_scores": {"1": {...}},
            "key_findings": [...],
            "industry": "...",           # Q03 from section a
            "biggest_obstacle": "...",   # Q32 from section e
        }
    """
    # Score all available questions
    question_scores: dict[str, float] = {}
    for q_num in range(1, 46):
        qid = f"Q{q_num:02d}"
        if qid in ("Q03", "Q32"):
            continue
        answer = answers.get(qid)
        score = _get_answer_score(qid, answer)
        if score is not None:
            question_scores[qid] = score

    result: dict = {
        "section": section_key,
        "enterprise_stage": None,
        "stage_score": None,
        "module_scores": {},
        "key_findings": [],
        "industry": None,
        "biggest_obstacle": None,
    }

    # Section A: enterprise stage classification
    if section_key == "a":
        stage_score = 0.0
        stage_weight_sum = 0.0
        for qid, weight in STAGE_WEIGHTS.items():
            if qid in question_scores:
                stage_score += question_scores[qid] * weight
                stage_weight_sum += weight
        if stage_weight_sum > 0:
            stage_score = stage_score / stage_weight_sum
        result["enterprise_stage"] = classify_enterprise_stage(stage_score)
        result["stage_score"] = round(stage_score, 1)
        result["industry"] = answers.get("Q03", "")
        return result

    # Sections B-F: score mapped modules
    module_nums = SECTION_MODULE_MAP.get(section_key, [])
    module_results: dict = {}

    for mod_num in module_nums:
        mod_def = MODULES[mod_num]
        weighted_sum = 0.0
        weight_sum = 0.0
        q_details = {}

        for qid, weight in mod_def["questions"].items():
            if qid in question_scores:
                weighted_sum += question_scores[qid] * weight
                weight_sum += weight
                q_details[qid] = {
                    "answer": answers.get(qid, ""),
                    "score": question_scores[qid],
                    "weight": weight,
                }

        mod_score = (weighted_sum / weight_sum) if weight_sum > 0 else 0.0
        module_results[str(mod_num)] = {
            "name_zh": mod_def["name_zh"],
            "name_en": mod_def["name_en"],
            "score": round(mod_score, 1),
            "rating": get_module_rating(mod_score),
            "questions": q_details,
        }

    result["module_scores"] = module_results

    # Detect findings for this section
    # Pass all available module scores (existing + new) for cross-module checks
    result["key_findings"] = _detect_section_findings(
        answers, question_scores, module_results, section_key
    )

    if section_key == "e":
        result["biggest_obstacle"] = answers.get("Q32", "")

    return result


def recalculate_overall(module_scores: dict) -> dict:
    """
    Recalculate overall score from available module scores.
    Normalizes weights based on which modules are present.

    Returns:
        {"overall_score": 62.5, "overall_rating": "...", "capital_readiness": "amber"}
    """
    overall_score = 0.0
    overall_weight_sum = 0.0
    for mod_num, weight in MODULE_WEIGHTS.items():
        mod_data = module_scores.get(str(mod_num))
        if mod_data and mod_data.get("score", 0) > 0:
            overall_score += mod_data["score"] * weight
            overall_weight_sum += weight
    if overall_weight_sum > 0:
        overall_score = overall_score / overall_weight_sum

    return {
        "overall_score": round(overall_score, 1),
        "overall_rating": get_overall_rating(overall_score),
        "capital_readiness": get_capital_readiness(overall_score),
    }
