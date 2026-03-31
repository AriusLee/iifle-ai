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

logger = logging.getLogger(__name__)

# Report sections for the Unicorn Diagnostic
DIAGNOSTIC_SECTIONS = [
    {
        "key": "executive_summary",
        "title_en": "Executive Summary",
        "title_cn": "总体诊断概述",
        "sort_order": 1,
    },
    {
        "key": "enterprise_stage",
        "title_en": "Enterprise Stage Assessment",
        "title_cn": "企业阶段判定",
        "sort_order": 2,
    },
    {
        "key": "gene_structure",
        "title_en": "Gene Structure Diagnosis",
        "title_cn": "基因结构诊断",
        "sort_order": 3,
    },
    {
        "key": "business_model",
        "title_en": "Business Model Diagnosis",
        "title_cn": "商业模式诊断",
        "sort_order": 4,
    },
    {
        "key": "growth_valuation",
        "title_en": "Growth & Valuation Potential",
        "title_cn": "增长与估值潜力",
        "sort_order": 5,
    },
    {
        "key": "financing_readiness",
        "title_en": "Financing & Capital Readiness",
        "title_cn": "融资与资本准备度",
        "sort_order": 6,
    },
    {
        "key": "exit_listing",
        "title_en": "Exit & Listing Direction",
        "title_cn": "退出与上市方向",
        "sort_order": 7,
    },
    {
        "key": "growth_pathway",
        "title_en": "Growth Pathway Recommendations",
        "title_cn": "做大做强路径建议",
        "sort_order": 8,
    },
    {
        "key": "action_items",
        "title_en": "Key Bottlenecks & Action Items",
        "title_cn": "主要卡点与行动建议",
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
        "executive_summary": """Write an executive summary. Structure:

1. **One-paragraph verdict** — what kind of company is this, what stage, and what's the core tension/contradiction in their position
2. **Top 3 strengths** — be specific, reference scores and what they mean in industry context
3. **Top 3 bottlenecks** — be brutally honest, explain WHY each is a problem
4. **One-line conclusion** — the single most important thing this company should do next

DO NOT list question numbers. Synthesize as if you personally assessed this company.
Use industry benchmarks from the web research to contextualize scores.
500-700 words in Chinese, 200-300 in English.""",

        "enterprise_stage": """Analyze the enterprise's current development stage. Cover:

1. **Stage classification and WHY** — what specific indicators place them here? Are there contradictions? (e.g., a 5-year-old company with no stable revenue is unusual — explain why this might be)
2. **Contradiction analysis** — identify conflicting signals in the data (e.g., high capital readiness but low business maturity)
3. **Peer comparison** — reference real companies in similar industries/stages from the web research. How does this company compare?
4. **Stage advancement criteria** — list 3-4 SPECIFIC conditions to reach the next stage (with numbers, e.g., "achieve MRR of RM XX" not "improve revenue")

400-500 words in Chinese, 150-200 in English.""",

        "gene_structure": """Analyze the enterprise DNA / gene structure. This is about whether the foundation is worth scaling.

1. **Founder dependency deep-dive** — what exactly breaks if the founder leaves? Decision-making? Client relationships? Product direction? Be specific about the risk.
2. **Organizational maturity** — compare to industry benchmarks. At this company's age, what level of organizational independence should they have? Reference real companies that successfully transitioned.
3. **Brand positioning gap** — how clear is their market position? In their industry, what does good positioning look like? Name competitors with strong positioning as benchmarks.
4. **Concrete recommendations** — 3 specific actions with timelines (e.g., "Hire a COO within 60 days", "Document top 5 business processes into SOPs by end of Q2")

400-500 words in Chinese, 150-200 in English.""",

        "business_model": """Analyze the business model structure — can this business scale beyond the founder?

1. **Revenue model assessment** — what type of revenue model do they have? How does it compare to industry best practices? What's the typical revenue profile for successful companies in this sector? Use web research data.
2. **Replicability score deep-dive** — if they tried to replicate to a new city/market, what would fail? Be specific about which processes are missing SOPs.
3. **Customer economics** — analyze retention vs acquisition. What does the customer journey look like? What's the industry benchmark for retention in their sector?
4. **Channel risk** — how dependent are they on specific acquisition channels? What happens if that channel's economics change?
5. **Recommendations** — specific, measurable actions (e.g., "Build a 3-stage sales playbook", "Achieve 85% customer retention rate within 6 months")

500-600 words in Chinese, 200-250 in English.""",

        "growth_valuation": """Analyze growth trajectory and valuation potential.

1. **Growth strategy critique** — is their chosen growth path (from answers) the RIGHT one for their industry? What do successful peers do? Reference specific companies from web research.
2. **TAM/SAM/SOM analysis** — use web research data to estimate market sizes. What's the realistic addressable market? Is their current market focus (local/regional/global) appropriate?
3. **Valuation logic** — what valuation methodology applies? (PS ratio, ARR multiple, etc.) What are typical multiples for their industry in SEA? Give a rough valuation range based on current and projected metrics.
4. **Growth unlock conditions** — what specific changes would move them from linear to exponential growth? Be concrete.

400-500 words in Chinese, 150-200 in English.""",

        "financing_readiness": """Analyze financing and capital readiness.

1. **Readiness vs reality** — if their financing readiness score is high but business maturity is low, explain this mismatch and its implications. Should they raise now or wait?
2. **Equity structure review** — is the structure investor-friendly? Common issues to check: founder control %, ESOP pool, investor protections.
3. **Audit & financial infrastructure** — how does their financial maturity compare to peers at this stage? What do investors actually look for?
4. **Fundraising strategy** — specific recommendation on timing, round type, target amount, and use of funds. Reference typical round sizes for their stage/industry in Malaysia/SEA.
5. **Risk warning** — what could go wrong if they raise too early? Be honest.

400-500 words in Chinese, 150-200 in English.""",

        "exit_listing": """Analyze exit strategy and listing readiness.

1. **Exit path analysis** — evaluate the feasibility of their stated preference. If there are contradictions (e.g., "no exit" but "want IPO"), address them directly.
2. **Listing requirements checklist** — for Bursa Malaysia (ACE Market or Main Market), list specific requirements and mark which are met ✅ and which are not ❌. Include: audit history, revenue/profit thresholds, public shareholding %, independent directors, sponsor requirements.
3. **Timeline estimation** — realistic year-by-year roadmap to listing readiness
4. **Alternative paths** — if IPO is too far, what are realistic alternatives? (M&A, strategic sale, secondary sale)

300-400 words in Chinese, 150-200 in English.""",

        "growth_pathway": """This is the MOST IMPORTANT section. Provide a comprehensive "做大做强" growth roadmap.

Structure as THREE PHASES with SPECIFIC deliverables:

**Phase 1: Foundation (0-6 months)**
- List 4-5 specific actions with measurable targets
- Focus on fixing the biggest bottleneck identified in the diagnostic
- Include team, process, and product actions

**Phase 2: Validation & Scale (6-18 months)**
- List 4-5 specific actions
- Focus on proving replicability and achieving revenue milestones
- Include market expansion and fundraising timing

**Phase 3: Capital Acceleration (18-36 months)**
- List 3-4 specific actions
- Focus on fundraising, market expansion, and IPO preparation

For each action, provide: WHAT to do, WHY it matters, and a MEASURABLE target.
Use industry benchmarks and real company examples to justify recommendations.

600-800 words in Chinese, 250-300 in English.""",

        "action_items": """Provide a prioritized action plan. Structure:

**URGENT — 30天内 (30 days)**
- 3 specific actions, each with: what, who is responsible, measurable outcome
- These should address the #1 bottleneck identified

**IMPORTANT — 90天内 (90 days)**
- 4 specific actions with measurable outcomes
- Focus on team building and process standardization

**STRATEGIC — 6个月内 (6 months)**
- 3 specific actions with measurable outcomes
- Focus on market positioning and capital preparation

Each action item must be SPECIFIC and MEASURABLE. Bad: "improve operations". Good: "Complete SOP documentation for 5 core processes, train 2 new team members to execute independently, achieve 80% process compliance rate."

400-500 words in Chinese, 200-250 in English.""",
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

    for section_def in DIAGNOSTIC_SECTIONS:
        section_prompt = _get_section_prompt(section_def["key"])

        try:
            section_context = {
                "section": section_def["title_en"],
                "section_zh": section_def["title_cn"],
                "instructions": section_prompt,
                "diagnostic_data": context,
            }

            response = await ai_client._chat(
                system_prompt,
                f"Section: {section_def['title_cn']} / {section_def['title_en']}\n\n"
                f"{section_prompt}\n\n"
                f"Context:\n{context}",
                0.4,
            )

            # Parse bilingual response
            content_cn, content_en = _parse_bilingual(response)

            section = ReportSection(
                report_id=report.id,
                section_key=section_def["key"],
                section_title=f"{section_def['title_cn']} / {section_def['title_en']}",
                content_cn=content_cn,
                content_en=content_en,
                content_data={
                    "module_scores": diagnostic.module_scores,
                    "overall_score": float(diagnostic.overall_score) if diagnostic.overall_score else None,
                },
                sort_order=section_def["sort_order"],
                is_ai_generated=True,
            )
            db.add(section)

        except Exception as exc:
            logger.error(f"Failed to generate section {section_def['key']}: {exc}")
            section = ReportSection(
                report_id=report.id,
                section_key=section_def["key"],
                section_title=f"{section_def['title_cn']} / {section_def['title_en']}",
                content_cn=f"[生成失败] {str(exc)[:200]}",
                content_en=f"[Generation failed] {str(exc)[:200]}",
                sort_order=section_def["sort_order"],
                is_ai_generated=False,
            )
            db.add(section)

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
