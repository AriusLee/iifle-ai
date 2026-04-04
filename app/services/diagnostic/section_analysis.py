"""
Generate brief AI analysis for a scored section based on actual answers.
Called during per-section submit to provide immediate, specific feedback.
"""

import logging
from app.services.ai.provider import get_ai_client
from app.services.diagnostic.scoring import SECTION_QUESTIONS

logger = logging.getLogger(__name__)

SECTION_NAMES = {
    "a": ("企业基础画像", "Enterprise Profile"),
    "b": ("基因结构", "Gene Structure"),
    "c": ("商业模式结构", "Business Model"),
    "d": ("估值结构", "Valuation"),
    "e": ("融资结构", "Financing"),
    "f": ("退出与上市", "Exit & Listing"),
}

SECTION_MODULE_MAP = {
    "b": 1, "c": 2, "d": 3, "e": 4, "f": 5,
}


def _build_section_context(answers: dict, section_key: str, score_result: dict) -> str:
    """Build context for a single section's AI analysis."""
    name_zh, name_en = SECTION_NAMES.get(section_key, ("", ""))
    qids = SECTION_QUESTIONS.get(section_key, [])

    ctx = f"## Section: {name_zh} / {name_en}\n\n"
    ctx += "### Answers:\n"
    for qid in qids:
        val = answers.get(qid)
        if val:
            ctx += f"- {qid}: {val}\n"

    if section_key == "a":
        ctx += f"\n### Stage Classification:\n"
        ctx += f"- Enterprise Stage: {score_result.get('enterprise_stage', 'N/A')}\n"
        ctx += f"- Stage Score: {score_result.get('stage_score', 'N/A')}/100\n"
    else:
        mod_num = SECTION_MODULE_MAP.get(section_key)
        if mod_num:
            mod = score_result.get("module_scores", {}).get(str(mod_num), {})
            ctx += f"\n### Module Score:\n"
            ctx += f"- Score: {mod.get('score', 'N/A')}/100\n"
            ctx += f"- Rating: {mod.get('rating', 'N/A')}\n"
            if mod.get("questions"):
                ctx += "- Per-question scores:\n"
                for qid, qd in mod["questions"].items():
                    ctx += f"  - {qid}: {qd.get('score', 'N/A')}/100 (answer: {qd.get('answer', '')})\n"

    findings = score_result.get("key_findings", [])
    if findings:
        ctx += "\n### Key Findings:\n"
        for f in findings:
            ctx += f"- [{f.get('type')}] {f.get('title_zh', '')} — {f.get('description_zh', '')}\n"

    return ctx


SYSTEM_PROMPT = (
    "You are a concise enterprise diagnostic consultant for IIFLE. "
    "Output exactly in the [ZH]/[EN] format requested. No other text or explanation."
)


async def generate_section_analysis(answers: dict, section_key: str, score_result: dict) -> dict:
    """
    Generate bilingual AI analysis for a scored section.

    Returns:
        {"analysis_zh": "...", "analysis_en": "..."}
    """
    context = _build_section_context(answers, section_key, score_result)

    prompt = f"""Based on the following diagnostic section data, write a specific analysis (3-5 sentences).

Requirements:
- Reference the company's ACTUAL answers and scores — be specific, not generic
- Identify the top strength and top weakness in this section
- Give 1-2 actionable next-step suggestions
- Professional but accessible tone

Output format (strictly follow):
[ZH]
(Chinese analysis, 3-5 sentences)
[EN]
(English analysis, 3-5 sentences)

{context}
"""

    try:
        client = get_ai_client()
        response = await client._chat(
            system=SYSTEM_PROMPT,
            user_content=prompt,
            temperature=0.3,
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
