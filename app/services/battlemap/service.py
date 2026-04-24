"""
BattleMap service — CRUD + per-section analysis + classify + report orchestration.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.battlemap import BattleMap, BattleMapStatus
from app.models.diagnostic import Diagnostic
from app.services.battlemap.classifier import classify
from app.services.battlemap.section_analysis import (
    SECTION_QUESTIONS,
    generate_battlemap_section_analysis,
)
from app.services.battlemap.variants import variant_meta


# Section order — must match the frontend's BM_SECTIONS ordering.
SECTION_ORDER = ["a", "b", "c", "d", "e", "f", "g", "h"]


async def get_battle_map(db: AsyncSession, battle_map_id: uuid.UUID) -> BattleMap | None:
    result = await db.execute(select(BattleMap).where(BattleMap.id == battle_map_id))
    return result.scalar_one_or_none()


async def get_by_diagnostic(db: AsyncSession, diagnostic_id: uuid.UUID) -> BattleMap | None:
    result = await db.execute(
        select(BattleMap).where(BattleMap.diagnostic_id == diagnostic_id)
    )
    return result.scalar_one_or_none()


async def list_by_user(db: AsyncSession, user_id: uuid.UUID) -> list[BattleMap]:
    result = await db.execute(
        select(BattleMap)
        .where(BattleMap.user_id == user_id)
        .order_by(BattleMap.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all(db: AsyncSession) -> list[BattleMap]:
    """List all battle maps (advisor dashboard)."""
    result = await db.execute(
        select(BattleMap).order_by(BattleMap.created_at.desc())
    )
    return list(result.scalars().all())


async def create_battle_map(
    db: AsyncSession,
    user_id: uuid.UUID,
    diagnostic: Diagnostic,
) -> BattleMap:
    """Create (or return) a draft BattleMap attached to an existing diagnostic.

    Ownership always follows the diagnostic's owner — one battle map per
    diagnostic, same user_id as the diagnostic. The `user_id` argument is
    accepted for signature compatibility but ignored when it diverges from
    `diagnostic.user_id` (which prevents orphan rows if an admin or a
    stale-session user POSTs the endpoint).
    """
    existing = await get_by_diagnostic(db, diagnostic.id)
    if existing:
        # Heal orphan rows: if a previous test / admin run attached this battle
        # map to a different user, retarget it to the diagnostic's real owner
        # so /battlemaps/mine for that owner actually returns it.
        if existing.user_id != diagnostic.user_id:
            existing.user_id = diagnostic.user_id
            await db.flush()
        return existing

    battle_map = BattleMap(
        user_id=diagnostic.user_id,
        company_id=diagnostic.company_id,
        diagnostic_id=diagnostic.id,
        status=BattleMapStatus.draft,
        answers={},
        other_answers={},
        source_scores=diagnostic.module_scores,
    )
    db.add(battle_map)
    await db.flush()
    return battle_map


async def save_draft(
    db: AsyncSession,
    battle_map_id: uuid.UUID,
    answers: dict,
    other_answers: dict | None = None,
) -> BattleMap:
    battle_map = await get_battle_map(db, battle_map_id)
    if not battle_map:
        raise ValueError("BattleMap not found")
    battle_map.answers = answers
    if other_answers is not None:
        battle_map.other_answers = other_answers
    battle_map.status = BattleMapStatus.draft
    await db.flush()
    return battle_map


async def submit_section(
    db: AsyncSession,
    battle_map_id: uuid.UUID,
    section_key: str,
    answers: dict,
    other_answers: dict | None = None,
) -> BattleMap:
    """
    Save one section's answers, generate AI analysis for that section, and
    auto-classify when all 8 sections are submitted. Mirrors Phase 1's
    per-section flow so the customer sees immediate feedback.
    """
    if section_key not in SECTION_ORDER:
        raise ValueError(f"Invalid section: {section_key}")

    battle_map = await get_battle_map(db, battle_map_id)
    if not battle_map:
        raise ValueError("BattleMap not found")

    # Enforce ordering: can't submit a section until the previous one is done
    # (re-submitting an already-submitted section is allowed).
    analyses = battle_map.section_analyses or {}
    meta = analyses.get("_meta", {"sections_submitted": []})
    sections_submitted = meta.get("sections_submitted", [])

    idx = SECTION_ORDER.index(section_key)
    if section_key not in sections_submitted and idx > 0:
        prev = SECTION_ORDER[idx - 1]
        if prev not in sections_submitted:
            raise ValueError(f"Section {prev.upper()} must be submitted first")

    # Merge answers (preserve earlier sections' answers).
    existing_answers = battle_map.answers or {}
    existing_answers.update(answers or {})
    battle_map.answers = existing_answers

    if other_answers is not None:
        existing_other = battle_map.other_answers or {}
        existing_other.update(other_answers)
        battle_map.other_answers = existing_other

    # Pull stage context from the linked diagnostic so the AI analysis is
    # stage-aware (e.g. don't give IPO tactics to a survival-stage company).
    diag_result = await db.execute(
        select(Diagnostic).where(Diagnostic.id == battle_map.diagnostic_id)
    )
    diagnostic = diag_result.scalar_one_or_none()
    source_scores = battle_map.source_scores or (diagnostic.module_scores if diagnostic else None)

    # Generate AI analysis for this section. Non-blocking on failure — the
    # section is still marked submitted so the user can move on.
    try:
        analysis = await generate_battlemap_section_analysis(
            answers=battle_map.answers,
            other_answers=battle_map.other_answers,
            section_key=section_key,
            current_stage=battle_map.current_stage,
            target_stage=battle_map.target_stage,
            source_scores=source_scores,
        )
        analyses[section_key] = analysis
    except Exception:
        analyses.setdefault(section_key, {"analysis_zh": "", "analysis_en": ""})

    # Track submission.
    if section_key not in sections_submitted:
        sections_submitted.append(section_key)
    meta["sections_submitted"] = sections_submitted
    meta.setdefault("section_submitted_at", {})[section_key] = (
        datetime.now(timezone.utc).isoformat()
    )
    analyses["_meta"] = meta
    battle_map.section_analyses = analyses

    if not battle_map.submitted_at:
        battle_map.submitted_at = datetime.now(timezone.utc)
    battle_map.status = BattleMapStatus.submitted

    # Auto-classify when all 8 sections are in.
    all_done = all(s in sections_submitted for s in SECTION_ORDER)
    if all_done and battle_map.variant is None and diagnostic is not None:
        try:
            result = classify(diagnostic, battle_map.answers)
            battle_map.variant = result.variant
            battle_map.current_stage = result.current_stage
            battle_map.target_stage = result.target_stage
            battle_map.source_scores = diagnostic.module_scores

            vm = variant_meta(result.variant)
            battle_map.top_priorities = [
                {
                    "rank": i + 1,
                    "title_zh": m["title_zh"],
                    "title_en": m["title_en"],
                    "action_zh": m["action_zh"],
                    "action_en": m["action_en"],
                }
                for i, m in enumerate(vm["modules"][:3])
            ]
            battle_map.do_not_do = vm["do_not_do"]
            battle_map.battle_modules = vm["modules"]
            battle_map.timeline = vm["timeline_template"]
            battle_map.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            battle_map.error_message = f"Auto-classification failed: {str(exc)[:400]}"

    flag_modified(battle_map, "section_analyses")
    flag_modified(battle_map, "answers")
    if other_answers is not None:
        flag_modified(battle_map, "other_answers")

    await db.flush()
    return battle_map


async def submit_and_classify(
    db: AsyncSession,
    battle_map_id: uuid.UUID,
) -> BattleMap:
    """Finalize answers, run classifier, store variant + stages + skeleton."""
    battle_map = await get_battle_map(db, battle_map_id)
    if not battle_map:
        raise ValueError("BattleMap not found")
    if not battle_map.answers:
        raise ValueError("No answers to classify")

    # Fetch linked diagnostic for its Phase 1 module scores.
    diag_result = await db.execute(
        select(Diagnostic).where(Diagnostic.id == battle_map.diagnostic_id)
    )
    diagnostic = diag_result.scalar_one_or_none()
    if not diagnostic:
        raise ValueError("Linked diagnostic not found")

    battle_map.status = BattleMapStatus.classifying
    battle_map.submitted_at = datetime.now(timezone.utc)
    battle_map.progress_message = "Classifying variant..."
    await db.flush()

    try:
        result = classify(diagnostic, battle_map.answers)
        battle_map.variant = result.variant
        battle_map.current_stage = result.current_stage
        battle_map.target_stage = result.target_stage
        # Snapshot scores so later re-scoring of the diagnostic doesn't silently
        # change what this battle map was built on.
        battle_map.source_scores = diagnostic.module_scores

        meta = variant_meta(result.variant)
        # Pre-populate structural fields from the variant registry — the AI
        # report generator will elaborate, but these are the canonical values
        # surfaced on the dashboard before the full report finishes.
        battle_map.top_priorities = [
            {"rank": i + 1, "title_zh": m["title_zh"], "title_en": m["title_en"],
             "action_zh": m["action_zh"], "action_en": m["action_en"]}
            for i, m in enumerate(meta["modules"][:3])
        ]
        battle_map.do_not_do = meta["do_not_do"]
        battle_map.battle_modules = meta["modules"]
        battle_map.timeline = meta["timeline_template"]
        battle_map.status = BattleMapStatus.submitted
        battle_map.progress_message = None
        await db.flush()
    except Exception as exc:
        battle_map.status = BattleMapStatus.failed
        battle_map.error_message = f"Classification failed: {str(exc)[:500]}"
        battle_map.progress_message = None
        await db.flush()
        raise

    return battle_map
