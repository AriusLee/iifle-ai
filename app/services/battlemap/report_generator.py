"""
Phase 1.5 — Battle Map report generator.

Produces a 10-chapter bilingual report. The variant (replication / financing /
capitalization) must have been picked by the classifier before calling here.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.battlemap import BattleMap, BattleMapVariant
from app.models.company import Company
from app.models.diagnostic import Diagnostic
from app.models.report import Report, ReportLanguage, ReportSection, ReportStatus, ReportType
from app.services.ai.provider import get_ai_client
from app.services.battlemap.variants import variant_meta

logger = logging.getLogger(__name__)


# Keep concurrency conservative — the Groq free tier hits rate limits fast
# on longer prompts, and the battle map prompts are heavier than diagnostic.
_REPORT_PARALLELISM = 4


# 10-chapter skeleton. Keys match the client's 报告框架 sheet.
BATTLEMAP_SECTIONS = [
    {"key": "advanced_verdict", "title_cn": "进阶总判断页", "title_en": "Advanced Verdict", "sort_order": 1},
    {"key": "next_stage_goal", "title_cn": "下一阶段目标页", "title_en": "Next Stage Goal", "sort_order": 2},
    {"key": "priority_structures", "title_cn": "三大结构优先级页", "title_en": "Top 3 Structure Priorities", "sort_order": 3},
    {"key": "business_model_upgrade", "title_cn": "商业模式升级页", "title_en": "Business Model Upgrade", "sort_order": 4},
    {"key": "org_kpi_upgrade", "title_cn": "组织与 KPI 升级页", "title_en": "Org & KPI Upgrade", "sort_order": 5},
    {"key": "profit_finance_readiness", "title_cn": "利润质量与财务准备页", "title_en": "Profit Quality & Financial Readiness", "sort_order": 6},
    {"key": "equity_governance", "title_cn": "股权与治理升级页", "title_en": "Equity & Governance Upgrade", "sort_order": 7},
    {"key": "valuation_financing_path", "title_cn": "估值与融资路径页", "title_en": "Valuation & Financing Path", "sort_order": 8},
    {"key": "timeline_battle_plan", "title_cn": "90天 / 180天 / 12个月作战图", "title_en": "90 / 180 / 365-Day Battle Plan", "sort_order": 9},
    {"key": "next_service_path", "title_cn": "升级承接建议页", "title_en": "Recommended Next Service", "sort_order": 10},
]


def _build_context(battle_map: BattleMap, diagnostic: Diagnostic, company: Company) -> str:
    """Build the shared AI context string — passed to every section prompt."""
    answers = battle_map.answers or {}
    source_scores = battle_map.source_scores or diagnostic.module_scores or {}
    meta = variant_meta(battle_map.variant) if battle_map.variant else {}

    ctx = f"""## Company
- Name: {company.legal_name}
- Industry: {company.primary_industry or '(not specified)'}
- Country: {company.country or 'Malaysia'}

## Phase 1 Diagnostic Summary (source of truth for scores)
- Overall Score: {diagnostic.overall_score}/100
- Overall Rating: {diagnostic.overall_rating}
- Enterprise Stage: {diagnostic.enterprise_stage}
- Capital Readiness: {diagnostic.capital_readiness}

## Six-Structure Scores (from Phase 1)
"""
    for mod_num in range(1, 7):
        mod = source_scores.get(str(mod_num)) or source_scores.get(mod_num)
        if isinstance(mod, dict):
            ctx += f"- Module {mod_num} ({mod.get('name_zh', '')}/{mod.get('name_en', '')}): {mod.get('score', 'N/A')}/100 — {mod.get('rating', 'N/A')}\n"

    ctx += f"""
## Classified Battle Map Variant
- Key: {battle_map.variant.value if battle_map.variant else '(unclassified)'}
- Name (zh): {meta.get('name_zh', '')}
- Name (en): {meta.get('name_en', '')}
- Audience (zh): {meta.get('audience_zh', '')}
- Core task (zh): {meta.get('core_task_zh', '')}
- Current stage → Target stage: {battle_map.current_stage} → {battle_map.target_stage}

## Phase 1.5 Questionnaire Answers
"""
    for qnum in range(1, 36):
        qid = f"Q{qnum:02d}"
        ans = answers.get(qid)
        if ans:
            ctx += f"- {qid}: {ans}\n"

    # Highlight open-text signals — the 5 richest inputs.
    high_signal = {"Q03", "Q25", "Q33", "Q34", "Q35"}
    open_answers = {k: v for k, v in answers.items() if k in high_signal and v}
    if open_answers:
        ctx += "\n## High-Signal Open Answers (use these directly in narrative)\n"
        for k, v in open_answers.items():
            ctx += f"- {k}: {v}\n"

    # Signature modules give the AI concrete scaffolding for chapters 4-8.
    if meta.get("modules"):
        ctx += "\n## Variant Signature Modules (A/B/C/D)\n"
        for m in meta["modules"]:
            ctx += f"- {m['code']}｜{m['title_zh']} / {m['title_en']}: {m['action_zh']}\n"

    # Shared do-not-do list. The AI should build on these but personalize.
    if meta.get("do_not_do"):
        ctx += "\n## Variant-Level Do-Not-Do (adapt, don't parrot)\n"
        for d in meta["do_not_do"]:
            ctx += f"- {d['title_zh']} — {d['reason_zh']}\n"

    # Timeline template — AI will enrich with company-specific detail.
    tt = meta.get("timeline_template") or {}
    if tt:
        ctx += "\n## Variant Timeline Template (use as skeleton, add company-specific detail)\n"
        for label, items in tt.items():
            ctx += f"- {label}: {' | '.join(items)}\n"

    return ctx


def _section_prompt(section_key: str, variant: BattleMapVariant) -> str:
    """Return the per-section prompt. Variant influences tone and focus."""
    base = {
        "advanced_verdict": """Write the Advanced Verdict page. Structure:

1. **一句话核心判断** — one decisive sentence naming this company's key tension at this stage. Reference the worked example style (e.g. "企业需求真实、赛道稳定，但目前仍是\"靠老板推动\"的服务公司").
2. **三大升级重点** — rank 1/2/3 the structures that MUST be upgraded first. One sentence each explaining *why this one, now*.
3. **三大当前不建议动作** — three "don't do this now" calls with one-sentence reasons each. Use the variant's do-not-do list as skeleton but personalize to what this company actually seems about to do wrong.

Be opinionated. This is the page the founder will read first. 300-400 words Chinese, 100-150 English.""",

        "next_stage_goal": """Write the Next Stage Goal page — makes it unambiguously clear that the next move is NOT "do everything" but "level up to one specific layer":

1. **当前阶段 → 目标阶段** — state explicitly (use the stages from context).
2. **升级的本质** — one paragraph explaining what "leveling up" actually means for THIS company (not generic). What changes in how they run the business.
3. **3 个判断标准** — three tests they can apply in 6 months to know they made it. Must be measurable.

200-300 words Chinese, 80-120 English.""",

        "priority_structures": """Write the Top 3 Structure Priorities page. Pick from:
基因结构 / 商业模式结构 / 估值结构 / 融资结构 / 退出结构 / 上市结构 / 组织结构 / 治理结构.

Rank top 3 specifically for this company. For each:
- **优先级 N：结构名称**
- **当前状态**：one sentence with concrete detail from the context.
- **升级动作**：2-3 concrete actions. Measurable.
- **做到什么样算够**：one-sentence exit criterion.

Do not rank 4+ structures — three is the point. 300-400 words Chinese, 120-160 English.""",

        "business_model_upgrade": """Write the Business Model Upgrade page — judge replication, expansion, and second-curve potential.

1. **模式类型诊断** — which of these is this company actually? one-time transaction / repeat purchase / subscription / project / platform / mixed. Cite the answer that reveals it.
2. **复制难点** — what specifically makes replication hard (founder dependency, SOP gaps, concentration, supply chain)? 2-3 points.
3. **增长杠杆** — what lever actually moves the needle next (not generic "grow revenue"). Concrete.
4. **第二增长曲线** — does one exist / should they look for one now / or is this premature?

Opinionated and specific. 300-400 words Chinese, 120-160 English.""",

        "org_kpi_upgrade": """Write the Org & KPI Upgrade page — founder dependency and middle-management takeover.

1. **创始人依赖诊断** — list 2-3 things only the founder does today (from context).
2. **关键岗位缺口** — name 1-2 specific roles to hire next (not "ops person" — "供应链 / 采购总监" style).
3. **中层承接节奏** — 90-day / 180-day / 12-month plan for building an independent leadership layer.
4. **3 个关键经营 KPI** — pick 3 KPIs that should run weekly/monthly from now on. Must be measurable.
5. **创始人放手清单** — 2-3 things the founder must stop doing personally.

250-350 words Chinese, 100-150 English.""",

        "profit_finance_readiness": """Write the Profit Quality & Financial Readiness page.

1. **盈利质量判断** — is profit from recurring core business or one-off? how stable?
2. **财务规范差距** — how far is the company from external-investor-grade financials? name specific gaps (无审计 / 科目不清 / 公私混用 / …).
3. **资金用途清晰度** — if they had RM 5M tomorrow, would they know where to deploy? Grade their clarity.
4. **报表成熟度分层** — rate them on a 1-5 scale (no books → internal → basic statements → standardized → audited).
5. **补齐顺序** — what to fix first, second, third.

250-350 words Chinese, 100-150 English.""",

        "equity_governance": """Write the Equity & Governance Upgrade page.

1. **股权复杂点** — identify any complications (nominee holding / verbal promises / family co-ownership / unaligned external shareholders / none). If none, say so clearly.
2. **治理补项** — concrete governance mechanisms to add (例会 / 授权矩阵 / 预算审批 / 审计委员会 / …).
3. **公司-个人边界** — judge current state; name 1-2 specific things to clean up.
4. **结构重整建议** — one-paragraph plan if any pre-capital-action restructuring is needed.

200-300 words Chinese, 80-120 English.""",

        "valuation_financing_path": """Write the Valuation & Financing Path page.

1. **高估值潜力** — Low / Emerging / Strong, and one reason rooted in the company's actual answers.
2. **融资准备度** — Not Ready / Can Start Prep / Ready for Action, with reason.
3. **BP 准备度** — Supplement Basics First / Can Enter BP Stage / Advanced Stage, with reason.
4. **匹配的资本类型** — name specific investor types this company should target (天使 / 战略 / PE / 产业资本 / …). Be specific.
5. **估值故事的缺失拼图** — what must the capital narrative include that it can't today?

250-350 words Chinese, 100-150 English.""",

        "timeline_battle_plan": """Write the 90-day / 180-day / 12-month battle plan. Use the variant's timeline template as skeleton, BUT:

- Add company-specific detail in each line. Don't parrot the generic template.
- Every action must have: **动作 / 负责人角色 / 产出物**.
- Avoid vague verbs ("优化", "提升") unless followed by a measurable target.

Structure:
**未来90天**
- [具体动作]（负责人：角色）→ 产出物：…
- …

**未来180天**
- …

**未来12个月**
- …

End with **验收标准** — 3 objective tests to confirm the 12-month target is hit.

400-500 words Chinese, 150-200 English.""",

        "next_service_path": """Write the Recommended Next Service page — the monetization hook.

1. **当前最适合的下一步服务** — pick ONE from: 继续学习课程 / 会员长期陪跑 / 一对一顾问深拆 / 融资准备 / BP 路演材料 / 资本化 / 上市前规划. Justify using the specific gaps found in earlier chapters (reference structure priorities + timeline).
2. **辅助路径** — 1-2 supporting services that extend the main recommendation.
3. **为什么不是其他选项** — one-paragraph negative case for why the obvious alternatives are premature OR overkill.
4. **下一次复核时点** — when should the company re-take this diagnostic (3mo / 6mo / 12mo)?

Direct sales tone but grounded in the report's findings. 200-300 words Chinese, 80-120 English.""",
    }
    return base.get(section_key, "Provide analysis for this section based on the context.")


async def generate_battlemap_report(
    db: AsyncSession,
    battle_map: BattleMap,
    diagnostic: Diagnostic,
    company: Company,
) -> Report:
    """Generate the full 10-chapter battle map report."""
    if battle_map.variant is None:
        raise ValueError("BattleMap must be classified before report generation")

    meta = variant_meta(battle_map.variant)
    title_zh = f"{meta['name_zh']} — {company.legal_name}"

    report = Report(
        company_id=company.id,
        assessment_id=None,
        report_type=ReportType.battle_map,
        title=title_zh,
        status=ReportStatus.generating,
        language=ReportLanguage.bilingual,
    )
    db.add(report)
    await db.flush()

    battle_map.report_id = report.id
    await db.flush()

    context = _build_context(battle_map, diagnostic, company)
    ai_client = get_ai_client()

    system_prompt = f"""You are a senior capital structure consultant at IIFLE, a Malaysian capital advisory firm.

You are generating ONE CHAPTER of a 10-chapter Phase 1.5 Battle Map report. The overall report has already been classified as: **{meta['name_zh']} ({meta['name_en']})**.

The 10 chapters are:
1. 进阶总判断页 — Advanced Verdict
2. 下一阶段目标页 — Next Stage Goal
3. 三大结构优先级页 — Top 3 Structure Priorities
4. 商业模式升级页 — Business Model Upgrade
5. 组织与 KPI 升级页 — Org & KPI Upgrade
6. 利润质量与财务准备页 — Profit Quality & Financial Readiness
7. 股权与治理升级页 — Equity & Governance Upgrade
8. 估值与融资路径页 — Valuation & Financing Path
9. 90天 / 180天 / 12个月作战图 — Timeline Battle Plan
10. 升级承接建议页 — Recommended Next Service

Stay tightly on the assigned chapter. Do not repeat content from other chapters.

CRITICAL RULES:

1. NEVER reference question numbers (Q01, Q02, …) or say "根据问卷" / "according to the questionnaire". Synthesize as if you conducted the assessment yourself.

2. USE THE COMPANY'S SPECIFIC DATA — founder name, industry, concentration level, revenue band, management count, equity state. Do NOT produce generic advice that could apply to any company.

3. BE DIRECT AND OPINIONATED. Give verdicts, not summaries. When something is weak, name it.

4. PROVIDE CONCRETE NUMBERS AND ROLES. Not "grow the team" — "hire supply chain head within 90 days". Not "improve margin" — "raise recurring revenue share from ~30% to 45%+ in 6 months".

5. RESPECT THE VARIANT FRAME. This is **{meta['name_zh']}** — focus is: {meta['core_task_zh']}. Do NOT drift into advice that belongs in a different variant (e.g. don't push IPO prep in a Replication report).

6. Chinese (简体中文) is the PRIMARY language — write 70% of content in Chinese. English is a concise supplementary summary.

FORMAT:
## 中文
[Chinese analysis — main content]

## English
[Concise English summary of the same points]"""

    sem = asyncio.Semaphore(_REPORT_PARALLELISM)

    async def _generate_one(section_def: dict) -> dict:
        async with sem:
            user_prompt = (
                f"Chapter: {section_def['title_cn']} / {section_def['title_en']}\n\n"
                f"{_section_prompt(section_def['key'], battle_map.variant)}\n\n"
                f"Context:\n{context}"
            )
            try:
                response = await ai_client._chat(system_prompt, user_prompt, 0.4)
                content_cn, content_en = _parse_bilingual(response)
                return {
                    "section_def": section_def,
                    "content_cn": content_cn,
                    "content_en": content_en,
                    "ok": True,
                }
            except Exception as exc:
                logger.error(f"Battle map section {section_def['key']} failed: {exc}")
                return {"section_def": section_def, "error": str(exc), "ok": False}

    t0 = time.monotonic()
    pending = [asyncio.create_task(_generate_one(sd)) for sd in BATTLEMAP_SECTIONS]
    completed = 0

    for fut in asyncio.as_completed(pending):
        result = await fut
        section_def = result["section_def"]
        content_data = {
            "variant": battle_map.variant.value,
            "current_stage": battle_map.current_stage,
            "target_stage": battle_map.target_stage,
            "source_scores": battle_map.source_scores,
        }
        if result["ok"]:
            section = ReportSection(
                report_id=report.id,
                section_key=section_def["key"],
                section_title=f"{section_def['title_cn']} / {section_def['title_en']}",
                content_cn=result["content_cn"],
                content_en=result["content_en"],
                content_data=content_data,
                sort_order=section_def["sort_order"],
                is_ai_generated=True,
            )
        else:
            section = ReportSection(
                report_id=report.id,
                section_key=section_def["key"],
                section_title=f"{section_def['title_cn']} / {section_def['title_en']}",
                content_cn=f"[生成失败] {result['error'][:200]}",
                content_en=f"[Generation failed] {result['error'][:200]}",
                content_data=content_data,
                sort_order=section_def["sort_order"],
                is_ai_generated=False,
            )
        db.add(section)
        await db.flush()
        completed += 1
        logger.info(
            "BattleMap %s — chapter %s done (%d/%d, %.1fs)",
            report.id, section_def["key"], completed, len(BATTLEMAP_SECTIONS),
            time.monotonic() - t0,
        )

    report.status = ReportStatus.draft
    battle_map.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return report


def _parse_bilingual(response: str) -> tuple[str, str]:
    """Split bilingual AI response into (zh, en)."""
    content_cn = response
    content_en = ""
    if "## English" in response:
        parts = response.split("## English", 1)
        content_cn = parts[0].replace("## 中文", "").strip()
        content_en = parts[1].strip()
    elif "## 中文" in response:
        content_cn = response.replace("## 中文", "").strip()
    return content_cn, content_en
