import uuid
from datetime import date, datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    legal_name: Mapped[str] = mapped_column(String(500), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_incorporation: Mapped[date | None] = mapped_column(nullable=True)
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    primary_industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sub_industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="Malaysia")
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brief_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enterprise_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="company")
    intake_stages: Mapped[list["IntakeStage"]] = relationship(back_populates="company")
    documents: Mapped[list["Document"]] = relationship(back_populates="company")
    research: Mapped[list["CompanyResearch"]] = relationship(back_populates="company")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="company")
    reports: Mapped[list["Report"]] = relationship(back_populates="company")
    conversations: Mapped[list["ChatConversation"]] = relationship(back_populates="company")
