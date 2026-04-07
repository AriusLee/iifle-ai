"""
Generate AI analysis for a scored section based on actual answers.
Called during per-section submit to provide immediate, specific feedback.

Each section uses a module-specific analytical lens — the framing for
"Founder Dependency" is fundamentally different from "Capital Readiness".
Output is stage-aware: advice for a 概念萌芽期 company is different from
advice for a 资本进阶期 company.
"""

import logging
from app.services.ai.provider import get_ai_client
from app.services.diagnostic.scoring import SECTION_QUESTIONS

logger = logging.getLogger(__name__)

SECTION_NAMES = {
    "a": ("企业基础画像", "Enterprise Profile"),
    "b": ("基因结构（创始人依赖度）", "Gene Structure (Founder Dependency)"),
    "c": ("商业模式结构（可复制性）", "Business Model & Repeatability"),
    "d": ("估值结构（成长故事）", "Valuation & Growth Story"),
    "e": ("融资结构（资本就绪度）", "Financing Readiness"),
    "f": ("退出与上市路径", "Exit & IPO Pathway"),
}

SECTION_MODULE_MAP = {
    "b": 1, "c": 2, "d": 3, "e": 4, "f": 5,
}

# Plain-language label for each question (ZH / EN). Used so the AI knows
# what each answer represents — without this, the model has to guess
# what "Q07" means and produces vague text.
QUESTION_TEXT: dict[str, tuple[str, str]] = {
    "Q01": ("成立时间", "Years established"),
    "Q02": ("创始人行业经验", "Founder industry experience"),
    "Q03": ("行业类别", "Industry"),
    "Q04": ("年营收区间", "Annual revenue range"),
    "Q05": ("利润状态", "Profit status"),
    "Q06": ("团队规模", "Team size"),
    "Q07": ("经营状态", "Business state"),
    "Q08": ("当前最大目标", "Current biggest goal"),
    "Q09": ("增长最依赖什么", "What growth most depends on"),
    "Q10": ("最大驱动力", "Main driving force"),
    "Q11": ("企业定位清晰度", "Positioning clarity"),
    "Q12": ("离开创始人能否运转", "Can run without founder"),
    "Q13": ("管理层成熟度", "Management layer maturity"),
    "Q14": ("收入来源结构", "Revenue source mix"),
    "Q15": ("可复制成功率", "Replication success rate"),
    "Q16": ("成交标准化程度", "Sales standardization"),
    "Q17": ("交付独立性", "Delivery independence"),
    "Q18": ("客户复购/转介绍", "Customer retention & referrals"),
    "Q19": ("客户来源结构", "Customer acquisition channels"),
    "Q20": ("已验证的增长信号", "Validated growth signals"),
    "Q21": ("增长方式", "Growth method"),
    "Q22": ("市场机会规模", "Market opportunity scale"),
    "Q23": ("资金优先投入方向", "Capital priority allocation"),
    "Q24": ("增长核心逻辑", "Core growth logic"),
    "Q25": ("企业类型定位", "Enterprise type"),
    "Q26": ("股权结构清晰度", "Equity structure clarity"),
    "Q27": ("股东类型", "Shareholder composition"),
    "Q28": ("财务规范化程度", "Financial standardization"),
    "Q29": ("资本动作意向", "Capital action intent"),
    "Q30": ("融资时间预期", "Fundraising timeline"),
    "Q31": ("资本准备状态", "Capital preparation state"),
    "Q32": ("融资最大障碍", "Biggest fundraising obstacle"),
    "Q33": ("退出方向", "Exit direction"),
    "Q34": ("上市准备状态", "IPO readiness"),
    "Q35": ("报告期望焦点", "Report focus areas"),
}

# Per-module analytical lens — tells the AI what to LOOK FOR in each module.
# Without this, every section gets the same generic "strength + weakness" treatment.
SECTION_LENS = {
    "a": (
        "判断企业目前所处的成长阶段，识别基础画像中的关键张力："
        "比如团队规模与营收是否匹配、创始人经验与行业难度是否匹配、"
        "目标雄心与当前阶段是否一致。重点是给企业一个清晰的「现状坐标」。"
    ),
    "b": (
        "诊断企业对创始人的依赖程度，判断这是一家「老板就是公司」的生意，"
        "还是一家已经具备团队、系统、组织能力的「企业」。"
        "重点看：增长靠人还是靠系统、定位清不清、离开创始人能不能运转、有没有真正的管理层。"
    ),
    "c": (
        "诊断商业模式的可复制性和可规模化程度。"
        "重点看：收入是单次还是重复、销售能不能标准化、交付能不能独立运作、"
        "客户会不会自然回流、增长是靠老板人脉还是靠系统化获客。"
        "核心问题是：「这门生意能不能从一个店复制到一百个店？」"
    ),
    "d": (
        "评估企业的估值故事质量。投资人和资本市场看的不是今天赚多少钱，"
        "而是未来能长成多大、能不能形成品牌或平台效应。"
        "重点看：增长方式是开店还是平台化、市场天花板有多高、"
        "增长逻辑是规模还是网络效应、企业类型属于经营/业务/成长/资本/平台型哪一种。"
    ),
    "e": (
        "评估企业的资本就绪度——能不能「接得住」投资人的钱。"
        "重点看：股权清不清晰、财务规不规范、有没有BP和路演材料、"
        "时间预期合不合理、最大障碍是什么。"
        "结论应该是：「如果今天投资人来看你，你能不能签字？」"
    ),
    "f": (
        "判断企业对终局的思考深度。"
        "重点看：创始人有没有想过退出方式、上市准备到了哪一步、"
        "选择的退出路径（长期经营/股权交易/并购/上市）是否符合企业类型。"
        "区分「想上市」和「能上市」——前者是愿望，后者需要扎实的前置工作。"
    ),
}

# Stage-specific tone guidance
STAGE_TONE = {
    "概念萌芽期": "企业极早期，核心建议是「先验证、再谈结构」。不要给融资或上市建议。",
    "初创探索期": "企业刚起步，核心建议是「先稳住模式、建立SOP」。融资建议应保守。",
    "模式验证期": "企业正在验证可复制性，建议聚焦「打磨标准化、降低创始人依赖」。",
    "规模扩张期": "企业已验证模式，可以建议「建立组织能力、规范财务、考虑融资」。",
    "资本进阶期": "企业已具备资本化条件，建议直接、专业，可以涉及具体融资动作和上市路径。",
}


def _build_section_context(
    answers: dict,
    section_key: str,
    score_result: dict,
    enterprise_stage: str | None,
) -> str:
    """Build the context block for a section's AI analysis."""
    name_zh, name_en = SECTION_NAMES.get(section_key, ("", ""))
    qids = SECTION_QUESTIONS.get(section_key, [])
    lens = SECTION_LENS.get(section_key, "")

    ctx = f"## Section: {name_zh} / {name_en}\n\n"
    ctx += f"### Analytical Lens\n{lens}\n\n"

    if enterprise_stage:
        tone = STAGE_TONE.get(enterprise_stage, "")
        ctx += f"### Enterprise Stage\n{enterprise_stage}\n"
        if tone:
            ctx += f"Tone guidance: {tone}\n"
        ctx += "\n"

    # Answers with plain-language labels (not raw Q-codes)
    ctx += "### Answers\n"
    for qid in qids:
        val = answers.get(qid)
        if not val:
            continue
        label_zh, label_en = QUESTION_TEXT.get(qid, (qid, qid))
        if isinstance(val, list):
            val_str = " / ".join(str(v) for v in val)
        else:
            val_str = str(val)
        ctx += f"- {label_zh} / {label_en}: {val_str}\n"

    # Scoring context
    if section_key == "a":
        ctx += f"\n### Stage Result\n"
        ctx += f"- Stage: {score_result.get('enterprise_stage', 'N/A')}\n"
        ctx += f"- Stage Score: {score_result.get('stage_score', 'N/A')}/100\n"
    else:
        mod_num = SECTION_MODULE_MAP.get(section_key)
        if mod_num:
            mod = score_result.get("module_scores", {}).get(str(mod_num), {})
            ctx += f"\n### Module Score\n"
            ctx += f"- Score: {mod.get('score', 'N/A')}/100\n"
            ctx += f"- Rating: {mod.get('rating', 'N/A')}\n"

    findings = score_result.get("key_findings", [])
    if findings:
        ctx += "\n### Detected Findings\n"
        for f in findings:
            ctx += f"- [{f.get('type')}] {f.get('title_zh', '')} — {f.get('description_zh', '')}\n"

    return ctx


SYSTEM_PROMPT = (
    "你是 IIFLE 的资深企业诊断顾问，风格直接、专业、有洞察力。"
    "You are IIFLE's senior enterprise diagnostic consultant — direct, professional, insightful. "
    "严格按照要求的 [ZH]/[EN] 格式输出，不要任何额外解释或寒暄。"
    "Output strictly in the [ZH]/[EN] format requested. No preamble, no closing remarks."
)


def _build_prompt(context: str) -> str:
    return f"""根据以下企业诊断数据，撰写一份针对该模块的简明分析报告。

【硬性要求 / Hard Requirements】
1. 必须引用企业的"实际回答内容"——例如"团队仅5人以下"、"年营收100万–500万"、"客户主要靠创始人人脉"。不要写空泛的话。
   You MUST reference the company's ACTUAL answers (e.g. "team under 5 people", "revenue 1M–5M", "customers come mainly from founder's network"). No generic platitudes.
2. 不要提及"问卷"、"评分"、"Q01/Q07"等技术词汇。读者不应该知道这是从问卷生成的。
   Do NOT mention "questionnaire", "Q01", "scoring", etc. The reader should not know this came from a form.
3. 必须遵守"分析视角"和"阶段语调指引"——不要给一个早期企业谈融资细节。
   You MUST respect the "Analytical Lens" and "Stage Tone" — don't give fundraising tactics to a concept-stage company.
4. 输出严格按照下方结构，使用中文标签【现状判断】【核心优势】【关键短板】【行动建议】，英文使用 [State] [Strength] [Weakness] [Next Steps]。

【输出格式 / Output Format】
[ZH]
【现状判断】
（1-2句话，针对该模块给出一个具体的现状结论。引用至少1个真实数据点。）

【核心优势】
（1-2句话，指出该模块中表现最好的1个方面。说明它"为什么是优势"以及它能带来什么。）

【关键短板】
（1-2句话，指出该模块中最严重的1个问题。说明它"为什么是短板"以及如果不解决会发生什么。）

【行动建议】
（2-3条具体可执行的建议。每条以"•"开头。建议必须与上述短板对应，并符合企业当前阶段。）

[EN]
[State]
(1-2 sentences. Specific verdict on this module, referencing at least 1 real data point.)

[Strength]
(1-2 sentences. The single strongest aspect of this module — what it is and what it enables.)

[Weakness]
(1-2 sentences. The single biggest gap in this module — what it is and what happens if it's not fixed.)

[Next Steps]
(2-3 concrete actionable bullets, each starting with "•". Must address the weakness above and fit the company's current stage.)

{context}
"""


async def generate_section_analysis(
    answers: dict,
    section_key: str,
    score_result: dict,
    enterprise_stage: str | None = None,
) -> dict:
    """
    Generate bilingual structured analysis for a scored section.

    Returns:
        {"analysis_zh": "...", "analysis_en": "..."}
    """
    context = _build_section_context(answers, section_key, score_result, enterprise_stage)
    prompt = _build_prompt(context)

    try:
        client = get_ai_client()
        response = await client._chat(
            system=SYSTEM_PROMPT,
            user_content=prompt,
            temperature=0.4,
        )
        zh, en = _parse_bilingual(response)
        return {"analysis_zh": zh, "analysis_en": en}

    except Exception as e:
        logger.warning(f"Section analysis generation failed: {e}")
        return {"analysis_zh": "", "analysis_en": ""}


def _parse_bilingual(response: str) -> tuple[str, str]:
    """Parse [ZH]/[EN] formatted response."""
    if "[ZH]" in response and "[EN]" in response:
        parts = response.split("[EN]")
        zh = parts[0].split("[ZH]")[-1].strip()
        en = parts[1].strip() if len(parts) > 1 else ""
        return zh, en
    return response.strip(), response.strip()
