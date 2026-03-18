import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IntakeStageNumber(str, enum.Enum):
    stage_1 = "1"
    stage_2 = "2"
    stage_3 = "3"


class IntakeStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"
    validated = "validated"


class IntakeStage(Base):
    __tablename__ = "intake_stages"
    __table_args__ = (UniqueConstraint("company_id", "stage", name="uq_intake_company_stage"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    stage: Mapped[IntakeStageNumber] = mapped_column(Enum(IntakeStageNumber), nullable=False)
    status: Mapped[IntakeStatus] = mapped_column(Enum(IntakeStatus), default=IntakeStatus.not_started)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    completed_sections: Mapped[list] = mapped_column(JSONB, default=list)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    validated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    company: Mapped["Company"] = relationship(back_populates="intake_stages")
    submitter: Mapped["User | None"] = relationship(foreign_keys=[submitted_by])
    validator: Mapped["User | None"] = relationship(foreign_keys=[validated_by])
