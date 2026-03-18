import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, BigInteger, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentCategory(str, enum.Enum):
    audited_report = "audited_report"
    management_accounts = "management_accounts"
    tax_return = "tax_return"
    company_profile = "company_profile"
    org_chart = "org_chart"
    business_plan = "business_plan"
    group_structure = "group_structure"
    board_resolution = "board_resolution"
    shareholder_agreement = "shareholder_agreement"
    constitution = "constitution"
    icc_report = "icc_report"
    risk_register = "risk_register"
    esg_report = "esg_report"
    governance_manual = "governance_manual"
    material_contract = "material_contract"
    license = "license"
    property_valuation = "property_valuation"
    tax_clearance = "tax_clearance"
    transfer_pricing = "transfer_pricing"
    esos_plan = "esos_plan"
    term_sheet = "term_sheet"
    other = "other"


class DocumentStage(str, enum.Enum):
    stage_1 = "1"
    stage_2 = "2"
    stage_3 = "3"


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[DocumentCategory] = mapped_column(Enum(DocumentCategory), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    stage: Mapped[DocumentStage | None] = mapped_column(Enum(DocumentStage), nullable=True)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(Enum(ExtractionStatus), default=ExtractionStatus.pending)
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="documents")
    uploader: Mapped["User"] = relationship(foreign_keys=[uploaded_by])
