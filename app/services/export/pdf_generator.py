"""
PDF report generator using WeasyPrint.
Renders report sections into a styled HTML document and converts to PDF.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime
from typing import Any

import weasyprint

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company
from app.models.report import Report, ReportSection

logger = logging.getLogger(__name__)


REPORT_TYPE_LABELS = {
    "module_1": "Gene Structure Assessment Report",
    "module_2": "Business Model Assessment Report",
    "module_3": "Valuation Assessment Report",
    "module_4": "Financing Strategy Report",
    "module_5": "Exit Mechanism Report",
    "module_6": "Listing Standards Report",
    "master": "Master Report",
}


def _render_html(
    report: Report,
    sections: list[ReportSection],
    company: Company | None,
    language: str = "en",
) -> str:
    """Render report data into styled HTML for PDF conversion."""

    company_name = company.legal_name if company else "Company"
    report_title = report.title or REPORT_TYPE_LABELS.get(report.report_type.value, "Assessment Report")
    generated_date = report.created_at.strftime("%d %B %Y") if report.created_at else datetime.now().strftime("%d %B %Y")
    status_label = report.status.value.title() if report.status else "Draft"

    # Build sections HTML
    import markdown as md

    sections_html = ""
    for section in sorted(sections, key=lambda s: s.sort_order):
        content = section.content_cn if language == "cn" and section.content_cn else section.content_en
        if not content:
            continue

        # Convert markdown to HTML
        content_html = md.markdown(content, extensions=["tables", "sane_lists"])

        sections_html += f"""
        <div class="section">
            <h2>{_escape(section.section_title)}</h2>
            {content_html}
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700&display=swap">
    <style>
        @page {{
            size: A4;
            margin: 2.5cm 2cm;
            @bottom-center {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9px;
                color: #94a3b8;
            }}
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 11px;
            line-height: 1.6;
            color: #1e293b;
        }}

        /* Cover Page */
        .cover {{
            page-break-after: always;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 80vh;
            text-align: center;
        }}

        .cover .logo {{
            font-size: 28px;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: 3px;
            margin-bottom: 8px;
        }}

        .cover .subtitle {{
            font-size: 11px;
            color: #64748b;
            margin-bottom: 60px;
            letter-spacing: 1px;
        }}

        .cover .report-title {{
            font-size: 24px;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 12px;
        }}

        .cover .company-name {{
            font-size: 18px;
            color: #3b82f6;
            margin-bottom: 40px;
        }}

        .cover .meta {{
            font-size: 10px;
            color: #94a3b8;
        }}

        .cover .meta span {{
            margin: 0 8px;
        }}

        .cover .divider {{
            width: 60px;
            height: 3px;
            background: #3b82f6;
            margin: 20px auto;
        }}

        .cover .confidential {{
            margin-top: 60px;
            font-size: 9px;
            color: #cbd5e1;
            border: 1px solid #e2e8f0;
            padding: 8px 16px;
            border-radius: 4px;
        }}

        /* Content */
        .section {{
            margin-bottom: 28px;
            page-break-inside: avoid;
        }}

        h2 {{
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 12px;
            padding-bottom: 6px;
            border-bottom: 2px solid #e2e8f0;
        }}

        h3 {{
            font-size: 13px;
            font-weight: 700;
            color: #1e293b;
            margin: 16px 0 8px 0;
        }}

        h4 {{
            font-size: 11px;
            font-weight: 700;
            color: #334155;
            margin: 12px 0 6px 0;
        }}

        p {{
            margin-bottom: 8px;
            text-align: justify;
        }}

        ul, ol {{
            margin: 8px 0 12px 20px;
            padding: 0;
        }}

        li {{
            margin-bottom: 4px;
        }}

        strong {{
            font-weight: 700;
        }}

        em {{
            font-style: italic;
        }}

        blockquote {{
            border-left: 3px solid #3b82f6;
            padding: 8px 12px;
            margin: 8px 0;
            background: #f8fafc;
            color: #475569;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
            font-size: 10px;
        }}

        th {{
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            padding: 6px 10px;
            text-align: left;
            font-weight: 700;
        }}

        td {{
            border: 1px solid #e2e8f0;
            padding: 6px 10px;
        }}

        hr {{
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 16px 0;
        }}

        /* Footer */
        .footer {{
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            font-size: 9px;
            color: #94a3b8;
            text-align: center;
        }}
    </style>
</head>
<body>
    <!-- Cover Page -->
    <div class="cover">
        <div class="logo">IIFLE</div>
        <div class="subtitle">AI CAPITAL STRUCTURE PLATFORM</div>
        <div class="divider"></div>
        <div class="report-title">{_escape(report_title)}</div>
        <div class="company-name">{_escape(company_name)}</div>
        <div class="meta">
            <span>{generated_date}</span> |
            <span>Status: {status_label}</span> |
            <span>Version {report.version}</span>
        </div>
        <div class="confidential">
            CONFIDENTIAL — This document is prepared exclusively for authorized personnel.
            Unauthorized distribution is prohibited.
        </div>
    </div>

    <!-- Report Content -->
    {sections_html}

    <!-- Footer -->
    <div class="footer">
        Generated by IIFLE AI Capital Structure Platform — {generated_date}<br>
        This report is confidential and intended for authorized personnel only.
    </div>
</body>
</html>"""


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


async def generate_pdf(
    report_id: uuid.UUID,
    company_id: uuid.UUID,
    db: AsyncSession,
    language: str = "en",
) -> bytes:
    """Generate a PDF for the given report. Returns PDF bytes."""

    # Load report with sections
    result = await db.execute(
        select(Report)
        .options(selectinload(Report.sections))
        .where(Report.id == report_id, Report.company_id == company_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise ValueError(f"Report {report_id} not found")

    # Load company
    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()

    # Render HTML
    html_content = _render_html(report, list(report.sections), company, language)

    # Convert to PDF
    pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()

    logger.info("PDF generated for report %s (%d bytes)", report_id, len(pdf_bytes))
    return pdf_bytes
