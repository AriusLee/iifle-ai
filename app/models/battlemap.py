"""
Phase 1.5 — 战略作战图 (Strategic Battle Map) model.

Branching follow-up to the Phase 1 Unicorn Diagnostic. One Diagnostic can have
at most one BattleMap; classifier picks one of three report variants based on
Phase 1 module scores + intent signals.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BattleMapStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    classifying = "classifying"
    generating = "generating"
    completed = "completed"
    failed = "failed"


class BattleMapVariant(str, enum.Enum):
    replication = "replication"      # 复制扩张作战图
    financing = "financing"          # 融资准备作战图
    capitalization = "capitalization"  # 资本化推进图


class BattleMap(Base):
    __tablename__ = "battle_maps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Phase 1 diagnostic this battle map is built on top of — we pull
    # six-structure scores and enterprise_stage from here.
    diagnostic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("diagnostics.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[BattleMapStatus] = mapped_column(
        Enum(BattleMapStatus), default=BattleMapStatus.draft, nullable=False
    )

    # 35 answers keyed by Qxx. Single-select stores the zh option string;
    # open-text stores the raw user text; multi-select stores a list.
    answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    other_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # Classifier output ---------------------------------------------------
    variant: Mapped[BattleMapVariant | None] = mapped_column(
        Enum(BattleMapVariant), nullable=True
    )
    current_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Freeform one-sentence consultant verdict.
    headline_verdict_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline_verdict_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"rank": 1, "title_zh": "...", "title_en": "...", "reason_zh": "..."}]
    top_priorities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{"title_zh": "暂不建议直接启动融资", "reason_zh": "..."}]
    do_not_do: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Four signature battle modules (A/B/C/D) for the picked variant.
    # [{"code": "A", "title_zh": "模式标准化", "action_zh": "..."}]
    battle_modules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # 90/180/365-day timeline:
    # {"90d": ["...", "..."], "180d": [...], "12m": [...]}
    timeline: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Snapshot of diagnostic module_scores at the moment of classification —
    # reading from the diagnostic later would drift if it's re-scored.
    source_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Per-section AI analysis generated on each section submit. Shape:
    # {"a": {"analysis_zh": "...", "analysis_en": "..."}, "b": {...}, ...}
    # Also stores meta like sections_submitted under "_meta".
    section_analyses: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    progress_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship()
    user: Mapped["User"] = relationship()
    diagnostic: Mapped["Diagnostic"] = relationship()
    report: Mapped["Report | None"] = relationship(foreign_keys=[report_id])
