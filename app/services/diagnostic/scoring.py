"""
Scoring engine for the V2 35-question Unicorn Diagnostic Questionnaire.

Maps answers to 6 module scores + overall score + enterprise stage classification.

V2 changes:
- 35 questions (Q01-Q35) instead of 27
- 6 blocks (A-F) with updated module mappings
- Block A (Q01-Q06) → Stage classification
- Block B (Q07-Q14) → Module 1: Gene Structure
- Block C (Q15-Q20) → Module 2: Business Model
- Block D (Q21-Q25) → Module 3: Valuation
- Block E (Q26-Q32) → Module 4: Financing
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
        "questions": {
            "Q26": 0.25,   # Equity structure (raised: readiness > intent)
            "Q27": 0.10,   # Shareholder type (lowered per client)
            "Q28": 0.30,   # Financial standardization (raised: key readiness indicator)
            "Q29": 0.05,   # Capital action intent (lowered: intent ≠ capability)
            "Q30": 0.05,   # Fundraising timeline (lowered: intent ≠ capability)
            "Q31": 0.25,   # Capital readiness (raised per client)
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
    for q_num in range(1, 35):
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
