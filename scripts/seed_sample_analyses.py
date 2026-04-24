"""
Generate per-section AI analyses for the 3 seeded sample battle maps.

Runs after `seed_sample_companies.py` (which sets answers + classifies but
skips AI calls to keep the primary seed fast). Fans out 8 sections per
battle map in parallel, so ~24 AI calls complete in roughly one provider
round-trip time per company (~10–20s total depending on provider / load).

Re-running is safe — it overwrites existing analyses for the three sample
battle maps by matching company.legal_name.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session_factory
from app.models.battlemap import BattleMap
from app.models.company import Company
from app.models.diagnostic import Diagnostic
from app.services.battlemap.section_analysis import (
    SECTION_QUESTIONS,
    generate_battlemap_section_analysis,
)


SAMPLE_COMPANY_NAMES = [
    "云桥企服（模拟）",
    "味坊连锁（模拟）",
    "领航云科（模拟）",
]


async def analyze_one_section(
    battle_map: BattleMap,
    diagnostic: Diagnostic,
    section_key: str,
) -> tuple[str, dict]:
    """Run the AI analysis for a single section. Returns (section_key, analysis)."""
    analysis = await generate_battlemap_section_analysis(
        answers=battle_map.answers or {},
        other_answers=battle_map.other_answers or {},
        section_key=section_key,
        current_stage=battle_map.current_stage,
        target_stage=battle_map.target_stage,
        source_scores=battle_map.source_scores or diagnostic.module_scores,
    )
    return section_key, analysis


async def seed_analyses_for_company(company_name: str) -> dict:
    async with async_session_factory() as db:
        # Find the company's battle map.
        r = await db.execute(select(Company).where(Company.legal_name == company_name))
        company = r.scalar_one_or_none()
        if not company:
            return {"company": company_name, "error": "company not found"}

        r = await db.execute(
            select(BattleMap).where(BattleMap.company_id == company.id)
        )
        bm = r.scalar_one_or_none()
        if not bm:
            return {"company": company_name, "error": "battle map not found"}

        r = await db.execute(
            select(Diagnostic).where(Diagnostic.id == bm.diagnostic_id)
        )
        diagnostic = r.scalar_one_or_none()
        if not diagnostic:
            return {"company": company_name, "error": "diagnostic not found"}

        # Fan out all 8 sections in parallel.
        tasks = [
            analyze_one_section(bm, diagnostic, key)
            for key in SECTION_QUESTIONS.keys()
        ]
        t0 = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = asyncio.get_event_loop().time() - t0

        analyses = bm.section_analyses or {}
        meta = analyses.get("_meta", {})
        failed: list[str] = []
        for res in results:
            if isinstance(res, Exception):
                # We don't know which section failed from a gather exception —
                # the individual `generate_battlemap_section_analysis` already
                # swallows failures and returns empty strings, so this only
                # fires on genuinely unexpected errors.
                failed.append("unknown")
                continue
            key, analysis = res
            analyses[key] = analysis
            if not (analysis.get("analysis_zh") or analysis.get("analysis_en")):
                failed.append(key)
        analyses["_meta"] = meta
        bm.section_analyses = analyses

        flag_modified(bm, "section_analyses")
        await db.commit()

        return {
            "company": company_name,
            "elapsed_s": round(elapsed, 1),
            "sections_ok": 8 - len(failed),
            "failed": failed,
        }


async def main():
    print("Generating per-section AI analyses for 3 sample battle maps...")
    print("(8 sections per company × 3 companies = 24 AI calls, all parallelized)\n")

    tasks = [seed_analyses_for_company(name) for name in SAMPLE_COMPANY_NAMES]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    print(f"  {'Company':<22} {'Sections':<10} {'Time':<8} {'Failed'}")
    print(f"  {'-'*22} {'-'*10} {'-'*8} {'-'*6}")
    for r in results:
        if isinstance(r, Exception):
            print(f"  EXCEPTION: {r}")
            continue
        if r.get("error"):
            print(f"  {r['company']:<22} ERROR: {r['error']}")
            continue
        failed_str = ",".join(r["failed"]) if r["failed"] else "—"
        print(f"  {r['company']:<22} {r['sections_ok']}/8{'':<6} {r['elapsed_s']}s{'':<3} {failed_str}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
