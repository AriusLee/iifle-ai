"""
Scoring engine for the 27-question Unicorn Diagnostic Questionnaire.

Maps answers to 6 module scores + overall score + enterprise stage classification.
"""

from decimal import Decimal

# ── Answer-to-score mappings ──────────────────────────────────────────────────
# Each question maps answer text → numeric score (0-100 scale).
# Q03 is classification only (industry), no score.
# Q27 is multi-select for report personalization, no score.

SCORE_MAP: dict[str, dict[str, int]] = {
    "Q01": {
        "还未正式开始": 10,
        "0–1年": 25,
        "1–3年": 50,
        "3–5年": 75,
        "5年以上": 90,
    },
    "Q02": {
        "0–1年": 10,
        "1–3年": 30,
        "3–5年": 50,
        "5–10年": 75,
        "10年以上": 95,
    },
    # Q03 is industry classification — no scoring
    "Q04": {
        "还没有稳定营收": 5,
        "100万以下": 20,
        "100万–500万": 40,
        "500万–3000万": 65,
        "3000万–1亿": 85,
        "1亿以上": 98,
    },
    "Q05": {
        "还在试模式": 10,
        "已经能稳定成交": 30,
        "已经稳定盈利": 55,
        "正在扩张": 75,
        "正在准备融资 / 资本动作": 90,
    },
    "Q06": {
        "创始人本人": 10,
        "少数销售高手": 25,
        "单一渠道": 25,
        "单一产品": 25,
        "团队与系统共同驱动": 90,
    },
    "Q07": {
        "创始人个人能力": 10,
        "创始人 + 少数核心骨干": 30,
        "核心团队": 50,
        "团队 + 组织机制": 75,
        "已开始系统化运转": 95,
    },
    "Q08": {
        "还比较模糊": 10,
        "大致清楚": 30,
        "较清楚": 55,
        "清楚且差异化明显": 80,
        "已形成行业标签 / 品牌认知": 95,
    },
    "Q09": {
        "几乎不能": 10,
        "较难": 25,
        "一部分可以": 50,
        "大部分可以": 75,
        "基本可以": 95,
    },
    "Q10": {
        "单次交易": 15,
        "长期复购": 55,
        "订阅 / 月费": 90,
        "项目制收入": 30,
        "平台抽成": 75,
        "多种收入组合": 70,
    },
    "Q11": {
        "很低，几乎靠人": 10,
        "有机会，但不稳定": 30,
        "中等，部分可复制": 50,
        "较高，已有初步方法": 75,
        "很高，已有成熟 SOP": 95,
    },
    "Q12": {
        "基本没有": 10,
        "有一些经验，但不稳定": 25,
        "有基础流程": 50,
        "已有可训练 SOP": 75,
        "已能复制给不同团队": 95,
    },
    "Q13": {
        "不能": 10,
        "较难": 25,
        "一部分可以": 50,
        "大部分可以": 75,
        "基本完全可以": 95,
    },
    "Q14": {
        "很少": 10,
        "偶尔": 30,
        "一般": 50,
        "较高": 75,
        "很高": 95,
    },
    "Q15": {
        "主要靠创始人 / 熟人资源": 10,
        "主要靠转介绍": 30,
        "主要靠销售主动开发": 50,
        "主要靠渠道 / 平台 / 品牌流量": 75,
        "多渠道较均衡": 95,
    },
    "Q16": {
        "多开店 / 多开点": 30,
        "增加销售团队": 30,
        "增加经销商 / 渠道": 50,
        "产品升级与客户复购": 70,
        "平台化连接更多角色": 95,
        "区域扩张 / 跨国复制": 80,
    },
    "Q17": {
        "本地刚需市场": 20,
        "区域连锁机会": 40,
        "全国性品牌机会": 60,
        "东南亚机会": 80,
        "全球性机会": 95,
        "目前还不清楚": 5,
    },
    "Q18": {
        "获客": 55,
        "团队建设": 55,
        "门店 / 网点扩张": 35,
        "系统 / 技术": 75,
        "供应链 / 交付能力": 55,
        "品牌与市场": 70,
        "暂时还不清楚": 5,
    },
    "Q19": {
        "靠老板赚钱的经营型公司": 10,
        "靠产品赚钱的业务型公司": 30,
        "可复制的成长型公司": 55,
        "可融资的资本型公司": 80,
        "具备平台化潜力的高估值公司": 95,
    },
    "Q20": {
        "先活下来": 10,
        "先稳定盈利": 30,
        "先复制扩张": 55,
        "先做高估值逻辑": 80,
        "先进入融资 / 资本路径": 90,
    },
    "Q21": {
        "没有": 10,
        "大致有，但不清楚": 25,
        "基本清楚": 50,
        "较清晰": 75,
        "非常清晰": 95,
    },
    "Q22": {
        "没有": 5,
        "只有内部账": 20,
        "有基础财务报表": 40,
        "有1年年度审计": 60,
        "有2–3年审计 / 较规范财务体系": 80,
        "有5年以上审计 / 较成熟规范体系": 95,
    },
    "Q23": {
        "暂时不融资，先经营": 15,
        "想梳理商业模式": 30,
        "想做融资准备": 55,
        "想正式融资": 75,
        "想做并购 / 被并购准备": 70,
        "想走向上市路径": 95,
    },
    "Q24": {
        "还没开始准备": 10,
        "有想法但没材料": 25,
        "有基础资料但不完整": 45,
        "已开始系统整理融资资料": 70,
        "已能进入 BP / 路演准备": 95,
    },
    "Q25": {
        "长期经营，不谈退出": 15,
        "未来股权交易": 35,
        "未来兼并收购": 55,
        "未来融资后再退出": 75,
        "未来上市退出": 95,
    },
    "Q26": {
        "还非常早，不应现在讨论": 10,
        "先把经营和模式跑顺": 25,
        "可以开始补治理 / 财务 / 股权基础": 50,
        "可以开始做上市前体检": 75,
        "已开始认真思考上市路径": 95,
    },
}

# ── Module definitions ────────────────────────────────────────────────────────
# Which questions feed into which module, with weights per question.

MODULES = {
    1: {
        "name_zh": "基因结构",
        "name_en": "Gene Structure",
        "questions": {
            "Q07": 0.40,
            "Q08": 0.30,
            "Q09": 0.30,
        },
    },
    2: {
        "name_zh": "商业模式结构",
        "name_en": "Business Model",
        "questions": {
            "Q10": 0.20,
            "Q11": 0.20,
            "Q12": 0.15,
            "Q13": 0.15,
            "Q14": 0.15,
            "Q15": 0.15,
        },
    },
    3: {
        "name_zh": "增长与估值潜力",
        "name_en": "Growth & Valuation",
        "questions": {
            "Q16": 0.20,
            "Q17": 0.20,
            "Q18": 0.15,
            "Q19": 0.25,
            "Q20": 0.20,
        },
    },
    4: {
        "name_zh": "融资与资本准备",
        "name_en": "Financing Readiness",
        "questions": {
            "Q21": 0.30,
            "Q22": 0.35,
            "Q23": 0.15,
            "Q24": 0.20,
        },
    },
    5: {
        "name_zh": "退出机制",
        "name_en": "Exit Mechanism",
        "questions": {
            "Q25": 0.50,
            "Q26": 0.50,
        },
    },
    6: {
        "name_zh": "上市准备度",
        "name_en": "Listing Readiness",
        "questions": {
            "Q22": 0.30,
            "Q24": 0.25,
            "Q26": 0.45,
        },
    },
}

# Overall module weights for the final score
MODULE_WEIGHTS = {
    1: 0.20,  # Gene
    2: 0.25,  # Business Model
    3: 0.20,  # Growth & Valuation
    4: 0.15,  # Financing
    5: 0.10,  # Exit
    6: 0.10,  # Listing
}

# ── Enterprise stage classification ──────────────────────────────────────────

STAGE_QUESTIONS = ["Q01", "Q04", "Q05", "Q06", "Q19"]
STAGE_WEIGHTS = {"Q01": 0.15, "Q04": 0.25, "Q05": 0.25, "Q06": 0.15, "Q19": 0.20}


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
        answers: {"Q01": "3-5年", "Q02": "5-10年", ..., "Q27": [...]}

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
    for q_num in range(1, 27):
        qid = f"Q{q_num:02d}"
        if qid == "Q03":
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
        "report_focus": answers.get("Q27", []),
    }


def _detect_findings(
    answers: dict, scores: dict[str, float], modules: dict
) -> list[dict]:
    """Detect key findings and bottlenecks from questionnaire answers."""
    findings = []

    # Founder dependency
    q06 = scores.get("Q06", 50)
    q07 = scores.get("Q07", 50)
    q09 = scores.get("Q09", 50)
    if q06 <= 25 or q07 <= 30 or q09 <= 25:
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
    q11 = scores.get("Q11", 50)
    q12 = scores.get("Q12", 50)
    if q11 <= 30 or q12 <= 25:
        findings.append({
            "type": "bottleneck",
            "severity": "high",
            "title_zh": "商业模式可复制性低",
            "title_en": "Low Business Model Replicability",
            "description_zh": "企业缺乏标准化流程和SOP，复制到新市场的成功率低。需要先建立可复制的运营体系。",
            "description_en": "Lack of standardized processes and SOPs. Low replication success rate to new markets.",
            "module": 2,
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
            "module": 4,
        })

    if q21 <= 25:
        findings.append({
            "type": "gap",
            "severity": "medium",
            "title_zh": "股权结构不清晰",
            "title_en": "Unclear Equity Structure",
            "description_zh": "股权结构尚未清晰化，这是进入资本路径的前提条件。建议尽快梳理。",
            "description_en": "Equity structure not yet clarified — a prerequisite for capital pathway.",
            "module": 4,
        })

    # Strong potential signals
    overall_bm = modules.get("2", {}).get("score", 0)
    overall_growth = modules.get("3", {}).get("score", 0)
    if overall_bm >= 70 and overall_growth >= 65:
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
