"""
Battle Map classifier — picks one of three report variants based on Phase 1
six-structure scores plus intent signals from the Phase 1.5 questionnaire.

Decision is score-first (stable, non-AI) with intent override on the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.battlemap import BattleMapVariant
from app.models.diagnostic import Diagnostic


# Score thresholds on Gene (基因) and Financing (融资) structures. These two
# best separate the three archetypes in the client's worked examples
# (云桥 64/34, 味坊 78/60, 领航 88/79).
GENE_THRESHOLD_MID = 70
GENE_THRESHOLD_HIGH = 85
FINANCING_THRESHOLD_MID = 50
FINANCING_THRESHOLD_HIGH = 75


# Stage strings are kept human-readable — they surface directly in the report.
STAGE_LABELS = {
    "survival": "生存经营期",
    "stable_profit": "稳定盈利期",
    "replication": "复制扩张期",
    "capital_ready": "资本准备期",
    "pre_ipo": "上市预备期",
}


VARIANT_STAGES: dict[BattleMapVariant, tuple[str, str]] = {
    BattleMapVariant.replication: (STAGE_LABELS["survival"], STAGE_LABELS["stable_profit"]),
    BattleMapVariant.financing: (STAGE_LABELS["stable_profit"], STAGE_LABELS["replication"]),
    BattleMapVariant.capitalization: (STAGE_LABELS["capital_ready"], STAGE_LABELS["pre_ipo"]),
}


@dataclass
class ClassificationResult:
    variant: BattleMapVariant
    current_stage: str
    target_stage: str
    gene_score: float
    financing_score: float
    reason: str
    intent_override: bool


def _module_score(scores: dict | None, module_num: int) -> float:
    """Pull a module score out of the diagnostic module_scores JSONB."""
    if not scores:
        return 0.0
    mod = scores.get(str(module_num)) or scores.get(module_num)
    if not mod:
        return 0.0
    val = mod.get("score") if isinstance(mod, dict) else mod
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def classify(
    diagnostic: Diagnostic,
    answers: dict | None,
) -> ClassificationResult:
    """
    Pick a battle map variant.

    Score buckets (gene / financing):
      - <70 / <50              → Replication
      - 70–85 / 50–75          → Financing
      - ≥85 / ≥75              → Capitalization

    Intent overrides (Q04 capital_action, Q32 next_step_service) can push one
    tier up or down when the scores land on a boundary — e.g. a company with
    mid scores but "上市规划" intent stays in Financing rather than jumping to
    Capitalization unless scores also support it.
    """
    answers = answers or {}
    scores = diagnostic.module_scores or {}
    gene = _module_score(scores, 1)       # 基因结构
    financing = _module_score(scores, 4)  # 融资结构

    # Score-first decision
    if gene >= GENE_THRESHOLD_HIGH and financing >= FINANCING_THRESHOLD_HIGH:
        variant = BattleMapVariant.capitalization
        reason = f"Gene {gene:.0f} ≥ {GENE_THRESHOLD_HIGH} and Financing {financing:.0f} ≥ {FINANCING_THRESHOLD_HIGH}"
    elif gene >= GENE_THRESHOLD_MID and financing >= FINANCING_THRESHOLD_MID:
        variant = BattleMapVariant.financing
        reason = f"Gene {gene:.0f} in [{GENE_THRESHOLD_MID},{GENE_THRESHOLD_HIGH}) and Financing {financing:.0f} ≥ {FINANCING_THRESHOLD_MID}"
    else:
        variant = BattleMapVariant.replication
        reason = f"Gene {gene:.0f} < {GENE_THRESHOLD_MID} or Financing {financing:.0f} < {FINANCING_THRESHOLD_MID}"

    # Intent override — only applied when answers meaningfully contradict
    # the score-based bucket AND the company self-reports the more
    # conservative or more ambitious next step.
    intent_override = False
    q04 = (answers.get("Q04") or "").strip()
    q32 = (answers.get("Q32") or "").strip()

    capitalization_intent = {"上市规划", "并购 / 被并购准备"}
    capitalization_service = {"资本化 / 上市前规划"}
    financing_intent = {"融资准备", "正式融资", "商业计划书 / BP"}
    financing_service = {"融资准备", "BP / 路演材料整理"}
    conservative_intent = {"暂不考虑资本动作", "先做内部结构升级"}

    # Upgrade path: scored Financing but strong capitalization intent + near-
    # threshold scores — only bump up if they are actually close.
    if variant == BattleMapVariant.financing and (
        q04 in capitalization_intent or q32 in capitalization_service
    ):
        if gene >= GENE_THRESHOLD_HIGH - 3 and financing >= FINANCING_THRESHOLD_HIGH - 5:
            variant = BattleMapVariant.capitalization
            reason += "; intent override → capitalization (near threshold + capital-action intent)"
            intent_override = True

    # Downgrade path: scored Capitalization but owner wants to stay internal.
    elif variant == BattleMapVariant.capitalization and q04 in conservative_intent:
        variant = BattleMapVariant.financing
        reason += "; intent override → financing (owner prefers internal upgrade first)"
        intent_override = True

    # Upgrade: scored Replication but intent is financing and financials are
    # just under the mid threshold.
    elif variant == BattleMapVariant.replication and (
        q04 in financing_intent or q32 in financing_service
    ):
        if gene >= GENE_THRESHOLD_MID - 3 and financing >= FINANCING_THRESHOLD_MID - 5:
            variant = BattleMapVariant.financing
            reason += "; intent override → financing (near threshold + financing intent)"
            intent_override = True

    current_stage, target_stage = VARIANT_STAGES[variant]

    return ClassificationResult(
        variant=variant,
        current_stage=current_stage,
        target_stage=target_stage,
        gene_score=gene,
        financing_score=financing,
        reason=reason,
        intent_override=intent_override,
    )
