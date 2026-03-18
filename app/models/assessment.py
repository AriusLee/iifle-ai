import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssessmentStatus(str, enum.Enum):
    pending = "pending"
    scoring = "scoring"
    draft = "draft"
    review = "review"
    approved = "approved"
    archived = "archived"
    failed = "failed"


class CapitalReadiness(str, enum.Enum):
    red = "red"
    amber = "amber"
    green = "green"


class FlagSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    trigger_stage: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[AssessmentStatus] = mapped_column(Enum(AssessmentStatus), default=AssessmentStatus.pending)
    overall_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    overall_rating: Mapped[str | None] = mapped_column(String(50), nullable=True)
    enterprise_stage_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capital_readiness: Mapped[CapitalReadiness | None] = mapped_column(Enum(CapitalReadiness), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company: Mapped["Company"] = relationship(back_populates="assessments")
    module_scores: Mapped[list["ModuleScore"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")
    auto_flags: Mapped[list["AutoFlag"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="assessment")


class ModuleScore(Base):
    __tablename__ = "module_scores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    module_number: Mapped[int] = mapped_column(Integer, nullable=False)
    module_name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    rating: Mapped[str | None] = mapped_column(String(50), nullable=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assessment: Mapped["Assessment"] = relationship(back_populates="module_scores")
    dimension_scores: Mapped[list["DimensionScore"]] = relationship(
        back_populates="module_score", cascade="all, delete-orphan"
    )


class DimensionScore(Base):
    __tablename__ = "dimension_scores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_score_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module_scores.id", ondelete="CASCADE"), nullable=False
    )
    dimension_number: Mapped[int] = mapped_column(Integer, nullable=False)
    dimension_name: Mapped[str] = mapped_column(String(200), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    scoring_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    calculation_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_data_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    module_score: Mapped["ModuleScore"] = relationship(back_populates="dimension_scores")


class AutoFlag(Base):
    __tablename__ = "auto_flags"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    flag_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[FlagSeverity] = mapped_column(Enum(FlagSeverity), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(default=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assessment: Mapped["Assessment"] = relationship(back_populates="auto_flags")
    company: Mapped["Company"] = relationship()
    resolver: Mapped["User | None"] = relationship(foreign_keys=[resolved_by])
