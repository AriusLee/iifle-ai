"""
Per-section AI analysis for Phase 1.5 battle map.

Mirrors the Phase 1 section_analysis pattern — each of the 8 sections has its
own analytical lens, and the output is [ZH]/[EN] structured so the customer
portal can render it inline immediately after the section is submitted.

The LENS is *intent-aware*: for battle map we care about "what to do next",
not "where are you" (that was Phase 1's job). So each lens pushes toward
actionable, ranked advice grounded in the variant the company is heading
toward.
"""

from __future__ import annotations

import logging

from app.services.ai.provider import get_ai_client

logger = logging.getLogger(__name__)


SECTION_NAMES = {
    "a": ("目标与紧迫度", "Goals & Urgency"),
    "b": ("商业模式是否真的跑通", "Is the Business Model Really Proven"),
    "c": ("复制与扩张证据", "Replication & Expansion Evidence"),
    "d": ("利润质量与财务准备", "Profit Quality & Financial Readiness"),
    "e": ("组织与管理层承接", "Organization & Management"),
    "f": ("股权与治理复杂度", "Equity & Governance Complexity"),
    "g": ("估值逻辑与资本叙事", "Valuation Logic & Capital Narrative"),
    "h": ("推进意愿与资源匹配", "Willingness & Resource Match"),
}


# Plain-language labels so the AI can reference "revenue concentration" rather
# than echoing "Q06". Keys match Phase 1.5 Q01-Q35.
QUESTION_TEXT: dict[str, tuple[str, str]] = {
    "Q01": ("12 个月目标", "12-month goal"),
    "Q02": ("当前最困扰的问题", "Current biggest pain"),
    "Q03": ("优先解决项（开放）", "Top priority (open)"),
    "Q04": ("12–24 个月想推进的资本动作", "Capital action in 12–24 months"),
    "Q05": ("过去 12 个月核心收入来源", "Core revenue source over last 12m"),
    "Q06": ("前三大客户 / 产品 / 门店集中度", "Top-3 concentration"),
    "Q07": ("盈利模式", "Profit model"),
    "Q08": ("最赚钱业务单元可复制成熟度", "Replicability of best unit"),
    "Q09": ("异地 / 二店 / 二团队复制验证", "Offsite / 2nd unit validation"),
    "Q10": ("成交流程 SOP 成熟度", "Sales-process SOP maturity"),
    "Q11": ("交付可否脱离创始人", "Delivery independence from founder"),
    "Q12": ("创始人离场 1 个月最易出问题的环节", "What breaks first if founder is gone 1 month"),
    "Q13": ("盈利稳定度", "Profit stability"),
    "Q14": ("利润来源主营 vs 一次性", "Profit source: core vs one-off"),
    "Q15": ("财务报表 / 审计成熟度", "Financial reporting / audit maturity"),
    "Q16": ("未来 12 个月资金用途清晰度", "Clarity on next-12m capital use"),
    "Q17": ("能独立带结果的管理层数量", "# of independent leaders"),
    "Q18": ("最依赖创始人亲自处理的事情", "What founder still personally owns"),
    "Q19": ("中层承接成熟度", "Middle-management maturity"),
    "Q20": ("最缺的核心能力岗位", "Most-needed role"),
    "Q21": ("股权结构清晰度", "Equity clarity"),
    "Q22": ("股权复杂情况", "Equity complications"),
    "Q23": ("公司 / 个人账务边界", "Company / personal boundary"),
    "Q24": ("治理机制成熟度", "Governance maturity"),
    "Q25": ("投资人会关注什么（开放）", "Why would investors care (open)"),
    "Q26": ("最大增长故事方向", "Biggest growth story"),
    "Q27": ("市场空间定位", "Market scope"),
    "Q28": ("估值逻辑表达能力", "Ability to articulate valuation"),
    "Q29": ("未来 90 天推进意愿", "90-day push willingness"),
    "Q30": ("核心管理层是否愿意一起参与", "Whether mgmt will participate"),
    "Q31": ("为资本化调整股权 / 组织 / 财务意愿", "Willingness to adjust for capital action"),
    "Q32": ("最适合的下一步服务", "Best next-step service"),
    "Q33": ("最大结构性障碍（开放）", "Biggest structural obstacle (open)"),
    "Q34": ("最值得放大的增长点（开放）", "Highest-value growth lever (open)"),
    "Q35": ("最想本报告帮看清的事（开放）", "What customer wants to clarify (open)"),
}


# Section → list of question ids it contains.
SECTION_QUESTIONS: dict[str, list[str]] = {
    "a": ["Q01", "Q02", "Q03", "Q04"],
    "b": ["Q05", "Q06", "Q07", "Q08"],
    "c": ["Q09", "Q10", "Q11", "Q12"],
    "d": ["Q13", "Q14", "Q15", "Q16"],
    "e": ["Q17", "Q18", "Q19", "Q20"],
    "f": ["Q21", "Q22", "Q23", "Q24"],
    "g": ["Q25", "Q26", "Q27", "Q28"],
    "h": ["Q29", "Q30", "Q31", "Q32", "Q33", "Q34", "Q35"],
}


# Per-section analytical lens. Battle-map sections are about "what to fix next"
# and are stage-aware via the Phase 1 snapshot scores.
SECTION_LENS = {
    "a": (
        "判断企业对下一阶段的判断是否清醒：12 个月目标是否现实、当前困扰是否"
        "被正确识别、资本动作意图是否与实际能力匹配。重点抓出「目标-能力-时间」"
        "三者之间的错位。"
    ),
    "b": (
        "判断商业模式是否真的跑通——不是「有没有收入」，而是「收入是否来自"
        "可重复、可预测、不依赖少数客户的结构」。重点看集中度、盈利模式、"
        "最赚钱单元的复制成熟度。"
    ),
    "c": (
        "判断复制扩张的证据质量。重点看：异地 / 第二团队 / 第二店是否有"
        "真实验证；SOP 是否成体系；交付能否脱离创始人；创始人短期缺席"
        "最先出问题的是哪一块。区分「能想象复制」和「已验证复制」。"
    ),
    "d": (
        "判断利润是否可被外部投资人理解和信任。重点看：盈利是主营业务还是"
        "项目堆出来的；财务规范到哪一级；若今天有资金进来，用途是否清晰。"
        "结论应该是「这份利润拿出来见投资人会怎样」。"
    ),
    "e": (
        "判断组织是否能承接扩张。重点看：真正能独立带结果的管理层有几位、"
        "创始人还在亲自做什么、中层是否已经成形、最缺的能力岗位会不会"
        "拖慢下一阶段扩张。"
    ),
    "f": (
        "判断在启动资本动作之前，股权与治理是否已经可以承接外部资本。"
        "重点看：股权是否清晰、是否存在代持 / 口头承诺 / 公私混用等硬伤、"
        "治理机制是否已经规范到可被外部尽调。"
    ),
    "g": (
        "判断企业能否把增长翻译成投资人语言。重点看：增长故事方向是否清楚、"
        "市场空间判断是否扎实、是否具备较完整的估值逻辑表达。输出应该"
        "帮助老板意识到叙事的缺口，而不只是夸他。"
    ),
    "h": (
        "判断推进意愿是否足够支撑下一阶段。重点看：创始人是否愿意把"
        "90 天拿出来做结构升级；是否愿意让管理层一起参与；是否愿意为资本动作"
        "调整股权 / 组织 / 财务；下一步服务选得对不对。"
    ),
}


SYSTEM_PROMPT = (
    "你是 IIFLE 的资深资本结构顾问，风格直接、专业、有洞察力，聚焦「下一步怎么打」。"
    "You are IIFLE's senior capital-structure consultant — direct, professional, insightful, "
    "focused on 'what to do next'. "
    "严格按照要求的 [ZH]/[EN] 格式输出，不要任何额外解释或寒暄。"
    "Output strictly in the [ZH]/[EN] format requested. No preamble, no closing remarks."
)


def _build_section_context(
    answers: dict,
    other_answers: dict | None,
    section_key: str,
    current_stage: str | None,
    target_stage: str | None,
    source_scores: dict | None,
) -> str:
    name_zh, name_en = SECTION_NAMES.get(section_key, ("", ""))
    qids = SECTION_QUESTIONS.get(section_key, [])
    lens = SECTION_LENS.get(section_key, "")
    other_answers = other_answers or {}

    ctx = f"## Section: {name_zh} / {name_en}\n\n"
    ctx += f"### Analytical Lens\n{lens}\n\n"

    if current_stage or target_stage:
        ctx += "### Stage (from Phase 1 diagnostic)\n"
        if current_stage:
            ctx += f"- Current: {current_stage}\n"
        if target_stage:
            ctx += f"- Target: {target_stage}\n"
        ctx += "\n"

    if source_scores:
        ctx += "### Phase 1 Six-Structure Scores\n"
        for i in range(1, 7):
            mod = source_scores.get(str(i))
            if isinstance(mod, dict):
                ctx += f"- Module {i} ({mod.get('name_zh', '')}): {mod.get('score', 'N/A')}/100\n"
        ctx += "\n"

    ctx += "### Answers\n"
    for qid in qids:
        val = answers.get(qid)
        if val is None or val == "":
            continue
        label_zh, label_en = QUESTION_TEXT.get(qid, (qid, qid))
        if isinstance(val, list):
            val_str = " / ".join(str(v) for v in val)
        else:
            val_str = str(val)
        ctx += f"- {label_zh} / {label_en}: {val_str}\n"
        extra = other_answers.get(qid)
        if extra:
            ctx += f"  (补充 / note: {extra})\n"

    return ctx


def _build_prompt(context: str) -> str:
    return f"""根据以下企业战略作战图问卷的分区回答，撰写一份针对该分区的简明分析。

【硬性要求 / Hard Requirements】
1. 必须引用企业的"实际回答内容"——例如"前三大客户集中度较高"、"目前只有 1 位可独立带结果的管理层"、"财务仅有内部账"。不要写空泛的话。
   You MUST reference the company's ACTUAL answers (e.g. "top-3 concentration high", "only 1 independent leader", "internal-only bookkeeping"). No generic platitudes.
2. 不要提及"问卷"、"评分"、"Q01/Q07"等技术词汇。读者不应该知道这是从问卷生成的。
   Do NOT mention "questionnaire", "Q01", "scoring", etc. The reader should not know this came from a form.
3. 必须遵守"分析视角"——这份作战图聚焦「下一步怎么打」，不是「你在哪里」。建议必须可执行，不要停留在诊断。
   You MUST respect the "Analytical Lens" — this battle map is about NEXT MOVES, not diagnosis. Advice must be actionable, not descriptive.
4. 必须考虑 Phase 1 的阶段定位——对 "生存经营期" 企业不要谈上市细节，对 "资本准备期" 企业不要再讲 SOP 基础。
   You MUST respect the stage context — no IPO tactics for survival-stage companies; no SOP basics for capital-ready companies.
5. 输出严格按照下方结构，使用中文标签【现状判断】【下一步重点】【常见陷阱】【行动建议】，英文使用 [State] [Next Focus] [Common Pitfall] [Action].

【输出格式 / Output Format】
[ZH]
【现状判断】
（1-2 句话。针对该分区给出一个具体的现状结论。必须引用至少 1 个真实数据点或选项。）

【下一步重点】
（1-2 句话。在这个分区里，下一阶段应该把精力聚焦在哪件事上？为什么是这件事？）

【常见陷阱】
（1-2 句话。和该分区相关、处于此阶段的企业最容易踩的 1 个坑。给出具体画面。）

【行动建议】
（2-3 条具体可执行建议，每条以 "•" 开头。每条都应该写清楚「做什么 / 产出物 / 时间窗」中的至少两项。）

[EN]
[State]
(1-2 sentences. Specific verdict grounded in at least 1 real answer.)

[Next Focus]
(1-2 sentences. Where should next-stage attention concentrate in this section, and why this and not something else?)

[Common Pitfall]
(1-2 sentences. The single most common trap companies at this stage fall into in this section. Paint a concrete picture.)

[Action]
(2-3 bullets starting with "•". Each must specify at least two of: what-to-do / deliverable / time window.)

{context}
"""


async def generate_battlemap_section_analysis(
    answers: dict,
    other_answers: dict | None,
    section_key: str,
    current_stage: str | None = None,
    target_stage: str | None = None,
    source_scores: dict | None = None,
) -> dict:
    """Generate bilingual structured analysis for a battle-map section."""
    context = _build_section_context(
        answers=answers,
        other_answers=other_answers,
        section_key=section_key,
        current_stage=current_stage,
        target_stage=target_stage,
        source_scores=source_scores,
    )
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
        logger.warning("Battle map section analysis failed (%s): %s", section_key, e)
        return {"analysis_zh": "", "analysis_en": ""}


def _parse_bilingual(response: str) -> tuple[str, str]:
    if "[ZH]" in response and "[EN]" in response:
        parts = response.split("[EN]")
        zh = parts[0].split("[ZH]")[-1].strip()
        en = parts[1].strip() if len(parts) > 1 else ""
        return zh, en
    return response.strip(), response.strip()
