"""
Report generator for Unicorn Diagnostic — creates a structured report
from questionnaire answers and scores using AI narratives.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.diagnostic import Diagnostic
from app.models.report import Report, ReportSection, ReportLanguage, ReportStatus, ReportType
from app.services.ai.provider import get_ai_client
from app.services.diagnostic.listing_requirements import (
    pick_tiers_for_stage,
    render_markdown_comparison,
    to_dict as listing_pair_to_dict,
)

logger = logging.getLogger(__name__)

# Maximum number of report sections to generate in parallel via the AI
# provider. Higher values give faster end-to-end report generation but
# risk hitting per-minute rate limits on the AI provider. 5 is a safe
# default for DeepSeek / Groq paid tiers; lower it if you see 429s.
_REPORT_PARALLELISM = 5

# Report sections for the Unicorn Diagnostic (8-section template)
DIAGNOSTIC_SECTIONS = [
    {
        "key": "enterprise_profile",
        "title_en": "Enterprise Profile & Stage Assessment",
        "title_cn": "企业画像与阶段判断",
        "sort_order": 1,
    },
    {
        "key": "key_highlights",
        "title_en": "Key Questionnaire Highlights",
        "title_cn": "关键勾选摘要",
        "sort_order": 2,
    },
    {
        "key": "six_scores",
        "title_en": "Six Structure Scores",
        "title_cn": "六大结构评分",
        "sort_order": 3,
    },
    {
        "key": "ai_assessment",
        "title_en": "AI Overall Assessment",
        "title_cn": "AI总判断",
        "sort_order": 4,
    },
    {
        "key": "unicorn_pathway",
        "title_en": "Unicorn Pathway",
        "title_cn": "独角兽路径图",
        "sort_order": 5,
    },
    {
        "key": "action_plan_90d",
        "title_en": "90-Day Action Plan",
        "title_cn": "90天行动建议",
        "sort_order": 6,
    },
    {
        "key": "upgrade_assessment",
        "title_en": "Upgrade Assessment",
        "title_cn": "升级判断",
        "sort_order": 7,
    },
    {
        "key": "listing_requirements",
        "title_en": "Listing Requirements — Bursa SC vs US SEC",
        "title_cn": "上市要求对比 — 马来西亚 SC 与 美国 SEC",
        "sort_order": 8,
    },
    {
        "key": "next_steps",
        "title_en": "Recommended Next Steps",
        "title_cn": "建议承接方向",
        "sort_order": 9,
    },
]


def _build_context(diagnostic: Diagnostic, company: Company) -> str:
    """Build the context string for AI report generation."""
    answers = diagnostic.answers or {}
    scores = diagnostic.module_scores or {}
    findings = diagnostic.key_findings or []

    context = f"""
## Company: {company.legal_name}
Industry: {company.primary_industry or answers.get('Q03', 'Not specified')}
Country: {company.country}

## Overall Diagnostic Results
- Overall Score: {diagnostic.overall_score}/100
- Overall Rating: {diagnostic.overall_rating}
- Enterprise Stage: {diagnostic.enterprise_stage}
- Capital Readiness: {diagnostic.capital_readiness}

## Module Scores
"""
    for mod_num in range(1, 7):
        mod = scores.get(str(mod_num), {})
        if mod:
            context += f"- Module {mod_num} ({mod.get('name_zh', '')}/{mod.get('name_en', '')}): {mod.get('score', 'N/A')}/100 — {mod.get('rating', 'N/A')}\n"

    context += "\n## Questionnaire Answers\n"
    for q_num in range(1, 28):
        qid = f"Q{q_num:02d}"
        answer = answers.get(qid)
        if answer:
            context += f"- {qid}: {answer}\n"

    if findings:
        context += "\n## Key Findings\n"
        for f in findings:
            context += f"- [{f.get('type', '')}] {f.get('title_zh', '')} / {f.get('title_en', '')}: {f.get('description_zh', '')}\n"

    report_focus = answers.get("Q27", [])
    if report_focus:
        context += f"\n## Customer's Report Focus (Q27): {', '.join(report_focus) if isinstance(report_focus, list) else report_focus}\n"

    return context


def _get_section_prompt(section_key: str) -> str:
    """Get the AI prompt for a specific report section."""
    prompts = {
        "enterprise_profile": """Write a company portrait and stage assessment. Structure:

1. **Industry & positioning** — what industry, what sub-segment, what's the company's core offering
2. **Current stage → Target stage** — where they are now and where they want to go. Be specific (e.g., "初创验证期 → 规模扩张期")
3. **One-sentence verdict** — capture the key tension in ONE sentence. Reference the 云桥企服 example style: "已跑出基础营收但仍属老板驱动成交" — be specific to THIS company, not generic.
4. **Key characteristics** — 3-4 defining traits of this company (positive and negative). What makes them who they are right now?

Be specific, not generic. This should read like a consultant who has deeply understood the company, not a template fill-in.
300-400 words in Chinese, 100-150 in English.""",

        "key_highlights": """Pick the ~11 most revealing answers from the questionnaire data. These should be the answers that MOST define the company's current position and contradictions.

Format as a bullet list. Each bullet:
**问题要点：回答 → 含义**

Example format:
- **团队规模：5人以下** → 仍处于创始人单兵作战阶段，尚未建立可复制的组织能力
- **客户获取方式：纯靠老板人脉** → 增长天花板明显，无法规模化

Focus on answers that reveal:
- Contradictions (claims big ambition but small team)
- Bottlenecks (single point of failure areas)
- Strengths (proven traction, real revenue)
- Stage indicators (what actually defines where they are)

Do NOT list all 35 answers — only the ~11 most diagnostic ones. Do NOT reference question numbers (Q01, Q07, etc.).
300-400 words in Chinese, 100-150 in English.""",

        "six_scores": """Present the 6 module scores clearly and concisely. This section should be SHORT — the scores are already in the data, your job is to present them with meaning.

For each of the 6 modules, present:
- **Module name**: Score/100 — Rating
- One-line assessment of what this score means FOR THIS SPECIFIC COMPANY

After all 6, add:
- **Highlight the HIGHEST scoring module** — what does this strength mean strategically?
- **Highlight the LOWEST scoring module** — what risk does this create?

Keep this section concise. Do not over-explain — the detailed analysis belongs in other sections.
200-300 words in Chinese, 80-120 in English.""",

        "ai_assessment": """Provide the AI overall assessment with THREE clear subsections:

### 三大核心亮点 (3 Key Highlights)
- What does this company do WELL? Be specific — reference real data points, scores, and business indicators.
- Each highlight should be 2-3 sentences: what it is, why it matters, how it compares to peers.

### 三大关键卡点 (3 Key Bottlenecks)
- What's HOLDING THEM BACK? Be brutally honest.
- Each bottleneck should explain: the problem, its root cause, and what happens if it's not fixed.
- Reference specific contradictions in the data.

### 当前不建议动作 (3 Not-Recommended Actions)
- What should they AVOID doing right now, and WHY?
- These should be common mistakes companies at this stage make.
- Example: "不建议现阶段启动融资 — 商业模式尚未验证，估值将被严重压低"

Be direct and opinionated. Write like a senior consultant giving tough-love advice.
400-500 words in Chinese, 150-200 in English.""",

        "unicorn_pathway": """Design a THREE-PHASE unicorn growth pathway. Adapt the phases to the company's current stage:

**For early-stage companies:**
- Phase 1: 夯实基础 (Fix the Base) — fix founder dependency, build SOPs, stabilize revenue model
- Phase 2: 可复制化 (Make Replicable) — prove the model works without the founder, expand to new segments
- Phase 3: 进入资本通道 (Enter Capital Path) — prepare for fundraising, build investor narrative

**For mid-stage companies:**
- Phase 1: 巩固单位经济 (Solidify Unit Economics) — prove profitability per unit, optimize margins
- Phase 2: 搭建资本叙事 (Build Capital Narrative) — create a compelling story, benchmark against listed peers
- Phase 3: 启动融资 (Launch Financing) — execute fundraising, target specific investor types

**For advanced companies:**
- Phase 1: 上市前体检 (Pre-IPO Health Check) — audit readiness, governance, compliance
- Phase 2: 升级叙事 (Upgrade Narrative) — position for IPO valuation, international benchmarking
- Phase 3: 进入Pre-IPO (Enter Pre-IPO) — engage sponsors, roadshow preparation

Each phase must include: phase name, objective, and 2-3 SPECIFIC actions.
400-500 words in Chinese, 150-200 in English.""",

        "action_plan_90d": """Provide a focused 90-day action plan with THREE time horizons. Each action MUST be specific and tied to a bottleneck identified in the assessment.

**本周 (This Week):**
- 1-2 immediate actions the founder can start TODAY
- These should address the single most urgent issue
- Example: "梳理现有客户清单，标注哪些客户是老板独立维护、哪些已有团队跟进"

**本月 (This Month):**
- 2-3 actions to complete within 30 days
- Focus on quick wins that build momentum
- Each must have a measurable deliverable

**90天内 (Within 90 Days):**
- 2-3 actions for the quarter
- Focus on structural changes (team, process, systems)
- Each must have a clear success metric

IMPORTANT: Every action must be SPECIFIC and ACTIONABLE. Bad: "优化运营". Good: "完成5个核心业务流程的SOP文档化，并培训至少2名员工独立执行".
300-400 words in Chinese, 100-150 in English.""",

        "upgrade_assessment": """Provide FOUR upgrade verdicts. Each verdict must have a rating AND a one-line explanation.

### 高估值潜力 (High Valuation Potential)
Rating: **低 / 初显 / 强** (Low / Emerging / Strong)
One-line explanation of why.

### 融资准备度 (Financing Readiness)
Rating: **尚未准备 / 可启动准备 / 可进入实操** (Not Ready / Can Start Prep / Ready for Action)
One-line explanation of why.

### BP准备度 (Business Plan Readiness)
Rating: **需先补基础 / 可进入BP阶段 / 已进入进阶阶段** (Supplement Basics First / Can Enter BP Stage / Advanced Stage)
One-line explanation of why.

### 上市成熟度 (Listing Maturity)
Rating: **尚远 / 中期方向 / 接近Pre-IPO** (Far Away / Mid-term Direction / Pre-IPO Period)
One-line explanation of why.

Be honest in your ratings — most early-stage companies will be "Low" or "Not Ready" in most categories. Do not inflate ratings to be polite.
200-300 words in Chinese, 80-120 in English.""",

        "listing_requirements": """Write a SHORT narrative commentary (NOT the table — the table will be appended automatically) introducing the side-by-side listing requirements comparison.

Structure your commentary in 3 short paragraphs:

1. **为什么对比这两个市场 (Why these two markets)** — 1 short paragraph explaining why we benchmark against Bursa Malaysia (SC) and US NASDAQ (SEC) for THIS company. Reference the company's stage, ambition, and any signal from their answers about geographic / capital ambitions.

2. **对该企业的现实意义 (What this means for them)** — 1 short paragraph that grounds the comparison in the company's actual situation. Reference their REAL revenue, profit status, team size, and equity structure. Be specific about which thresholds they are far from, close to, or already meet. Do NOT invent numbers.

3. **下一步重点 (Where to focus next)** — 1 short paragraph naming the 2-3 highest-leverage gaps to close if they want to credibly approach EITHER market in the next 24-36 months.

CRITICAL:
- Do NOT generate a table — a deterministic comparison table will be appended automatically.
- Do NOT invent specific listing rule numbers — refer to thresholds in general terms (e.g. "the profit threshold", "the public float requirement"). The accurate numbers live in the appended table.
- Reference the company's actual data points from the questionnaire context.
- Tone: senior consultant, direct, no boilerplate.
- 200-300 words in Chinese, 80-120 in English.""",

        "next_steps": """Recommend what IIFLE should offer this company as next steps. Adapt to the company's stage:

**For early-stage companies, recommend:**
- 商业模式梳理 (Business Model Structuring) — why they need it
- SOP搭建 (SOP Development) — which processes to prioritize
- 基础财务/股权整理 (Basic Finance & Equity Cleanup) — what needs fixing

**For mid-stage companies, recommend:**
- BP梳理 (Business Plan Development) — what story to tell
- 资本故事设计 (Capital Narrative Design) — how to position for investors
- 对接匹配资本 (Capital Matching) — what type of investors to target

**For advanced companies, recommend:**
- 上市前体检 (Pre-IPO Health Check) — what gaps to close
- 资本故事重塑 (Capital Narrative Reshaping) — how to upgrade the story
- 顾问团队搭建 (Advisory Team Building) — what expertise to bring in

For each recommendation, explain: WHY this company needs it, WHAT it involves, and WHAT outcome to expect.
End with a clear call-to-action for the company to engage with IIFLE.
200-300 words in Chinese, 80-120 in English.""",
    }
    return prompts.get(section_key, "Provide analysis for this section based on the diagnostic data.")


async def generate_diagnostic_report(
    db: AsyncSession,
    diagnostic: Diagnostic,
    company: Company,
) -> Report:
    """Generate a full diagnostic report using AI narratives."""
    # Create report record
    report = Report(
        company_id=company.id,
        assessment_id=None,
        report_type=ReportType.diagnostic,
        title=f"独角兽成长诊断报告 — {company.legal_name}",
        status=ReportStatus.generating,
        language=ReportLanguage.bilingual,
    )
    db.add(report)
    await db.flush()

    # Link report to diagnostic
    diagnostic.report_id = report.id
    await db.flush()

    context = _build_context(diagnostic, company)

    # Enrich context with web research if Tavily is configured
    from app.services.ai.web_search import get_web_search
    web_search = get_web_search()
    if web_search:
        try:
            industry = company.primary_industry or diagnostic.answers.get("Q03", "")
            country = company.country or "Malaysia"

            # Run multiple targeted searches
            searches = [
                web_search.search(f"{industry} industry market size growth rate {country} 2025 2026", max_results=3),
                web_search.search(f"{industry} top companies competitors {country} Southeast Asia", max_results=3),
                web_search.search(f"{company.legal_name} company profile", max_results=2),
                web_search.search(f"Bursa Malaysia ACE Market listing requirements 2025", max_results=2),
                web_search.search(f"SaaS startup fundraising Series A {country} Southeast Asia benchmark", max_results=2),
            ]

            import asyncio
            results = await asyncio.gather(*searches, return_exceptions=True)

            all_content = []
            all_sources = []
            labels = ["Industry Market Data", "Competitors & Landscape", "Company Profile", "Listing Requirements", "Fundraising Benchmarks"]
            for label, res in zip(labels, results):
                if isinstance(res, Exception):
                    continue
                for r in res:
                    if r.get("content"):
                        all_content.append(f"### {label}: {r['title']}\n{r['content']}")
                        all_sources.append({"title": r["title"], "url": r["url"]})

            if all_content:
                context += "\n\n## Web Research (Real-time Data — USE THIS in your analysis)\n"
                context += "\n\n".join(all_content)
                context += "\n\nSources:\n"
                for s in all_sources:
                    context += f"- {s['title']}: {s['url']}\n"

            logger.info("Enriched report context with %d web results from %d searches", len(all_content), len(searches))
        except Exception as exc:
            logger.warning("Web research for report failed (non-blocking): %s", exc)

    ai_client = get_ai_client()

    system_prompt = """You are a senior capital structure consultant at IIFLE, a Malaysian capital advisory firm. You are writing a professional enterprise diagnostic report for a business owner.

You are generating ONE SECTION of an 8-section diagnostic report:
1. 企业画像与阶段判断 — Enterprise Profile & Stage Assessment
2. 关键勾选摘要 — Key Questionnaire Highlights
3. 六大结构评分 — Six Structure Scores
4. AI总判断 — AI Overall Assessment
5. 独角兽路径图 — Unicorn Pathway
6. 90天行动建议 — 90-Day Action Plan
7. 升级判断 — Upgrade Assessment
8. 建议承接方向 — Recommended Next Steps

Write like the sample diagnostic reports: direct, specific, consultant-style. Each section has a clear purpose — stay focused on that section's role. Do NOT repeat content across sections.

CRITICAL RULES — follow these exactly:

1. NEVER reference question numbers (Q01, Q07, etc.) or say "根据问卷". The reader should not know this came from a questionnaire. Synthesize the data as if you conducted an in-depth assessment.

2. USE REAL INDUSTRY DATA from the web research provided. Cite specific market sizes, growth rates, competitor names, and regulatory requirements. If web research is provided, you MUST reference it.

3. IDENTIFY CONTRADICTIONS in the data. If a company claims to be "platform-level" but has no stable revenue, call that out directly. Be honest, not flattering.

4. PROVIDE SPECIFIC NUMBERS AND BENCHMARKS. Instead of "improve revenue", say "target MRR of RM 50K within 6 months". Instead of "build a team", say "hire CTO, COO, and Sales Head within 90 days".

5. NAME REAL COMPANIES as peer benchmarks where possible — competitors, successful examples in the same industry/market, or comparable companies that have gone through similar stages.

6. For LISTING analysis, reference SPECIFIC requirements (e.g., Bursa Malaysia ACE Market minimum requirements, SC Malaysia guidelines).

7. Write like a CONSULTANT, not an academic. Be direct, opinionated, and actionable. Use bold for key points. Use short paragraphs.

8. Chinese (简体中文) is the PRIMARY language — write 70% of content in Chinese, richer and more detailed. English is supplementary — concise summary of the same points.

FORMAT:
## 中文
[Detailed Chinese analysis — this is the main content]

## English
[Concise English summary of the same analysis]"""

    # Generate all sections in parallel. Each section is independent (same
    # `context`, no cross-references), so we can fan out the AI calls and only
    # serialize the DB inserts at the end. A semaphore caps concurrency to
    # avoid hammering the AI provider's rate limit.
    import asyncio

    sem = asyncio.Semaphore(_REPORT_PARALLELISM)

    async def _generate_one(section_def: dict) -> dict:
        """Generate one section's content under the semaphore. Returns a result
        dict — never raises (errors are captured into the dict)."""
        async with sem:
            section_prompt = _get_section_prompt(section_def["key"])
            listing_pair = None
            section_user_prompt = (
                f"Section: {section_def['title_cn']} / {section_def['title_en']}\n\n"
                f"{section_prompt}\n\n"
                f"Context:\n{context}"
            )

            if section_def["key"] == "listing_requirements":
                listing_pair = pick_tiers_for_stage(diagnostic.enterprise_stage)
                section_user_prompt += (
                    "\n\n## Selected Tier Pair (auto-picked from enterprise stage)\n"
                    f"- Malaysia (SC): {listing_pair.my.board_zh} / {listing_pair.my.board_en}\n"
                    f"- United States (SEC): {listing_pair.us.board_zh} / {listing_pair.us.board_en}\n"
                    f"- Rationale (zh): {listing_pair.rationale_zh}\n"
                    f"- Rationale (en): {listing_pair.rationale_en}\n"
                    "\nIMPORTANT: Use the tier names above in your commentary, but do NOT reproduce the criteria — they will be appended as a table automatically.\n"
                )

            try:
                response = await ai_client._chat(
                    system_prompt,
                    section_user_prompt,
                    0.4,
                )
                content_cn, content_en = _parse_bilingual(response)

                if listing_pair is not None:
                    table_cn = render_markdown_comparison(listing_pair, language="cn")
                    table_en = render_markdown_comparison(listing_pair, language="en")
                    content_cn = (content_cn or "").rstrip() + "\n\n### 上市要求对比表\n\n" + table_cn + "\n\n*以上为公开披露的上市规则参考摘要，实际申报需以交易所最新规定及保荐机构意见为准。*"
                    content_en = (content_en or "").rstrip() + "\n\n### Listing Requirements Comparison\n\n" + table_en + "\n\n*Reference summary of publicly disclosed listing rules. Actual eligibility requires the latest exchange rules and sponsor advisory.*"

                return {
                    "section_def": section_def,
                    "content_cn": content_cn,
                    "content_en": content_en,
                    "listing_pair": listing_pair,
                    "ok": True,
                }
            except Exception as exc:
                logger.error(f"Failed to generate section {section_def['key']}: {exc}")
                return {
                    "section_def": section_def,
                    "error": str(exc),
                    "ok": False,
                }

    import time
    t0 = time.monotonic()

    # Fan out all section AI calls. Insert each ReportSection row + flush as
    # soon as its task completes — that way the polling reports list endpoint
    # sees progress in real time (sections_done count climbs as the AI works).
    pending = [asyncio.create_task(_generate_one(sd)) for sd in DIAGNOSTIC_SECTIONS]
    completed_count = 0

    for fut in asyncio.as_completed(pending):
        result = await fut
        section_def = result["section_def"]

        if result["ok"]:
            section_content_data: dict = {
                "module_scores": diagnostic.module_scores,
                "overall_score": float(diagnostic.overall_score) if diagnostic.overall_score else None,
            }
            if result["listing_pair"] is not None:
                section_content_data["listing_pair"] = listing_pair_to_dict(result["listing_pair"])

            section = ReportSection(
                report_id=report.id,
                section_key=section_def["key"],
                section_title=f"{section_def['title_cn']} / {section_def['title_en']}",
                content_cn=result["content_cn"],
                content_en=result["content_en"],
                content_data=section_content_data,
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
                sort_order=section_def["sort_order"],
                is_ai_generated=False,
            )
        db.add(section)
        # Flush so the new row is visible to the next poll. Status stays
        # `generating` until all sections are inserted, so the frontend keeps
        # polling and the user sees the progress count climb.
        await db.flush()
        completed_count += 1
        logger.info(
            "Report %s — section %s done (%d/%d, %.1fs elapsed)",
            report.id,
            section_def["key"],
            completed_count,
            len(DIAGNOSTIC_SECTIONS),
            time.monotonic() - t0,
        )

    logger.info(
        "Generated %d sections in %.1fs (concurrency=%d)",
        completed_count,
        time.monotonic() - t0,
        _REPORT_PARALLELISM,
    )

    report.status = ReportStatus.draft
    await db.flush()

    return report


def _parse_bilingual(response: str) -> tuple[str, str]:
    """Parse a bilingual AI response into (Chinese, English) content."""
    content_cn = response
    content_en = ""

    if "## English" in response:
        parts = response.split("## English", 1)
        cn_part = parts[0]
        en_part = parts[1] if len(parts) > 1 else ""

        # Clean up Chinese part
        content_cn = cn_part.replace("## 中文", "").strip()
        content_en = en_part.strip()
    elif "## 中文" in response:
        content_cn = response.replace("## 中文", "").strip()

    return content_cn, content_en
