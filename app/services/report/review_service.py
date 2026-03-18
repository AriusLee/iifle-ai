"""
ReviewService — simple review workflow for approving/rejecting reports
and editing individual report sections.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.report import Report, ReportSection, ReportStatus

logger = logging.getLogger(__name__)


class ReviewService:
    """Manages the report review lifecycle: approve, reject, edit sections."""

    async def approve_report(
        self,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> Report:
        """Approve a report, transitioning it to 'approved' status."""
        report = await self._get_report_or_raise(report_id, db)

        if report.status not in (ReportStatus.draft, ReportStatus.review, ReportStatus.revision):
            raise ValueError(
                f"Cannot approve report in '{report.status.value}' status. "
                f"Report must be in draft, review, or revision status."
            )

        report.status = ReportStatus.approved
        report.approved_by = user_id
        report.approved_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info("Report %s approved by user %s", report_id, user_id)
        return report

    async def reject_report(
        self,
        report_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None,
        db: AsyncSession,
    ) -> Report:
        """Reject a report, transitioning it to 'revision' status."""
        report = await self._get_report_or_raise(report_id, db)

        if report.status not in (ReportStatus.draft, ReportStatus.review):
            raise ValueError(
                f"Cannot reject report in '{report.status.value}' status. "
                f"Report must be in draft or review status."
            )

        report.status = ReportStatus.revision
        # Clear any previous approval
        report.approved_by = None
        report.approved_at = None
        await db.flush()

        logger.info(
            "Report %s rejected by user %s. Reason: %s",
            report_id,
            user_id,
            reason or "No reason given",
        )
        return report

    async def get_report_with_sections(
        self,
        report_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Retrieve a report with all its sections."""
        result = await db.execute(
            select(Report)
            .options(selectinload(Report.sections))
            .where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            raise ValueError(f"Report {report_id} not found.")

        sections = sorted(report.sections, key=lambda s: s.sort_order)

        return {
            "id": report.id,
            "assessment_id": report.assessment_id,
            "company_id": report.company_id,
            "report_type": report.report_type.value,
            "title": report.title,
            "status": report.status.value,
            "language": report.language.value,
            "version": report.version,
            "approved_by": report.approved_by,
            "approved_at": report.approved_at,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
            "sections": [
                {
                    "id": s.id,
                    "section_key": s.section_key,
                    "section_title": s.section_title,
                    "content_en": s.content_en,
                    "content_cn": s.content_cn,
                    "content_data": s.content_data,
                    "sort_order": s.sort_order,
                    "is_ai_generated": s.is_ai_generated,
                    "last_edited_by": s.last_edited_by,
                    "last_edited_at": s.last_edited_at,
                }
                for s in sections
            ],
        }

    async def update_section(
        self,
        section_id: uuid.UUID,
        content_en: str,
        content_cn: str | None,
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> ReportSection:
        """Update a report section's content (advisor manual edit)."""
        result = await db.execute(
            select(ReportSection).where(ReportSection.id == section_id)
        )
        section = result.scalar_one_or_none()

        if not section:
            raise ValueError(f"Report section {section_id} not found.")

        section.content_en = content_en
        if content_cn is not None:
            section.content_cn = content_cn
        section.is_ai_generated = False
        section.last_edited_by = user_id
        section.last_edited_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info("Section %s updated by user %s", section_id, user_id)
        return section

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_report_or_raise(
        report_id: uuid.UUID,
        db: AsyncSession,
    ) -> Report:
        """Fetch a report or raise ValueError if not found."""
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise ValueError(f"Report {report_id} not found.")
        return report
