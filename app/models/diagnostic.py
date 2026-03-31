import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DiagnosticStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    scoring = "scoring"
    completed = "completed"
    failed = "failed"


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[DiagnosticStatus] = mapped_column(
        Enum(DiagnosticStatus), default=DiagnosticStatus.draft
    )

    # Answers: {"Q01": "3-5年", "Q02": "5-10年", ..., "Q27": ["看清企业卡在哪", "看清能不能复制扩张"]}
    answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    # Free-text for "Other" options: {"Q03": "物流行业"}
    other_answers: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # Scores (populated after scoring)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    overall_rating: Mapped[str | None] = mapped_column(String(50), nullable=True)
    enterprise_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capital_readiness: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Per-module scores stored as JSONB for simplicity
    # {"module_1": {"name": "基因结构", "score": 72, "rating": "Medium", "questions": ["Q07","Q08","Q09"]}, ...}
    module_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # AI-generated insights/flags
    key_findings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Report reference
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_message: Mapped[str | None] = mapped_column(String(200), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship()
    user: Mapped["User"] = relationship()
    report: Mapped["Report | None"] = relationship(foreign_keys=[report_id])
