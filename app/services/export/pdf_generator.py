"""
PDF report generator using WeasyPrint.

Produces a branded, professionally-styled PDF with:
  - Full-bleed cover page featuring the IIFLE logo + metadata
  - Running page header (logo + report type) on all content pages
  - Running page footer (page number, confidentiality)
  - Gold accent (#b8893e) that matches the IIFLE logo
  - Proper typography for bilingual (zh/en) content
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from pathlib import Path

import weasyprint
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.battlemap import BattleMap
from app.models.company import Company
from app.models.report import Report, ReportSection
from app.services.battlemap.variants import variant_meta

logger = logging.getLogger(__name__)


# Human-readable titles per report_type. Fallback to the report's own title
# if a type isn't listed.
REPORT_TYPE_LABELS = {
    "module_1": ("Gene Structure Assessment", "基因结构评估"),
    "module_2": ("Business Model Assessment", "商业模式评估"),
    "module_3": ("Valuation Assessment", "估值结构评估"),
    "module_4": ("Financing Strategy Report", "融资策略报告"),
    "module_5": ("Exit Mechanism Report", "退出机制报告"),
    "module_6": ("Listing Standards Report", "上市标准报告"),
    "master": ("Master Report", "综合报告"),
    "diagnostic": ("Unicorn Growth Diagnostic Report", "独角兽成长诊断报告"),
    "battle_map": ("Professional Battle Map Report", "专业作战图报告"),
}


# Resolve the repo-level logo (repo-root/iifle-logo.png) once and embed as
# a data URL. WeasyPrint can render file:// paths too, but a data URL is
# portable across dev/prod containers regardless of working directory.
_LOGO_PATH = Path(__file__).resolve().parents[4] / "iifle-logo.png"


def _logo_data_url() -> str:
    try:
        data = _LOGO_PATH.read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    except Exception as exc:
        logger.warning("Could not embed IIFLE logo (%s): %s", _LOGO_PATH, exc)
        return ""


_LOGO_DATA_URL = _logo_data_url()


# Brand accent — tuned to match the gold in iifle-logo.png.
BRAND_GOLD = "#b8893e"
BRAND_GOLD_DARK = "#8f6a2c"
BRAND_GOLD_SOFT = "#f4ead8"
INK = "#111827"
INK_SOFT = "#475569"
INK_MUTED = "#94a3b8"
RULE = "#e5e7eb"


def _render_html(
    report: Report,
    sections: list[ReportSection],
    company: Company | None,
    language: str = "en",
    branch_label: str | None = None,
) -> str:
    """Render report data into styled HTML for PDF conversion.

    `branch_label` is the localized variant name for battle map reports (e.g.
    "复制扩张作战图" / "Replication & Expansion Battle Map"). Displayed as a
    subtitle under the main report title when provided.
    """

    is_cn = language == "cn"
    company_name = company.legal_name if company else ("公司" if is_cn else "Company")

    type_en, type_zh = REPORT_TYPE_LABELS.get(
        report.report_type.value, (report.title or "Assessment Report", report.title or "评估报告")
    )
    type_label = type_zh if is_cn else type_en
    # The top-of-cover title is always the canonical report type label. We no
    # longer use report.title (which embedded the company name) — "Prepared for
    # {company}" already shows that below.
    report_title = type_label

    generated_date = (
        report.created_at.strftime("%d %B %Y")
        if report.created_at
        else datetime.now().strftime("%d %B %Y")
    )
    status_label = report.status.value.title() if report.status else "Draft"
    version_label = f"v{report.version}"

    # Build sections HTML from markdown
    import markdown as md

    sections_html = ""
    for section in sorted(sections, key=lambda s: s.sort_order):
        content = section.content_cn if is_cn and section.content_cn else section.content_en
        if not content and section.content_cn:
            content = section.content_cn  # fallback
        if not content:
            continue

        content_html = md.markdown(content, extensions=["tables", "sane_lists"])

        title = section.section_title or ""
        # Section titles are often "中文 / English" — display the preferred half.
        if " / " in title:
            parts = title.split(" / ", 1)
            title = parts[0] if is_cn else parts[1]

        sections_html += f"""
        <section class="report-section">
            <header class="section-head">
                <span class="section-index">{section.sort_order:02d}</span>
                <h2>{_escape(title)}</h2>
            </header>
            <div class="section-body">
                {content_html}
            </div>
        </section>
        """

    # Copy labels for cover metadata
    labels = {
        "prepared_for": ("Prepared for", "报告对象"),
        "report_type": ("Report Type", "报告类型"),
        "date": ("Date", "生成日期"),
        "version": ("Version", "版本"),
        "status": ("Status", "状态"),
        "confidential": (
            "CONFIDENTIAL — Prepared exclusively for authorized personnel. Unauthorized distribution is prohibited.",
            "机密文件 — 仅供授权人员使用，禁止擅自转发或披露。",
        ),
    }
    def L(key: str) -> str:
        en, zh = labels[key]
        return zh if is_cn else en

    # Footer tagline
    footer_tagline = (
        "IIFLE · International Institute of Financing & Listing for Entrepreneurs"
    )

    logo_img = (
        f'<img src="{_LOGO_DATA_URL}" alt="IIFLE" />'
        if _LOGO_DATA_URL
        else '<div class="logo-fallback">IIFLE</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <title>{_escape(report_title)} — {_escape(company_name)}</title>
    <style>
        /* ───────────────── Page setup ───────────────── */

        /* Cover page: no running header/footer. */
        @page cover {{
            size: A4;
            margin: 0;
            @top-left {{ content: normal; }}
            @top-right {{ content: normal; }}
            @bottom-left {{ content: normal; }}
            @bottom-right {{ content: normal; }}
            @bottom-center {{ content: normal; }}
        }}

        /* Content pages: running header + footer with logo, type, page nums. */
        @page {{
            size: A4;
            margin: 3.2cm 2.2cm 2.6cm 2.2cm;

            /* Use @top-center (which spans the full top margin width when
             * @top-left/@top-right are empty) so our flex header with
             * justify-content: space-between can actually stretch edge-to-edge. */
            @top-center {{
                content: element(pageHeader);
                width: 100%;
            }}
            @bottom-left {{
                content: "{_escape(L('confidential').split(' — ')[0])}";
                font-family: "Inter", "Noto Sans SC", sans-serif;
                font-size: 8px;
                color: {INK_MUTED};
                letter-spacing: 1.5px;
                border-top: 0.5pt solid {RULE};
                padding: 6pt 0 4pt 0;
                vertical-align: middle;
            }}
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-family: "Inter", "Noto Sans SC", sans-serif;
                font-size: 8.5px;
                color: {INK_SOFT};
                font-weight: 600;
                white-space: nowrap;
                border-top: 0.5pt solid {RULE};
                padding: 6pt 0 4pt 0;
                vertical-align: middle;
            }}
        }}

        /* ───────────────── Typography reset ───────────────── */

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        html, body {{
            font-family: "Inter", "Helvetica Neue", -apple-system,
                         "Noto Sans SC", "Source Han Sans SC", sans-serif;
            font-size: 10.5pt;
            line-height: 1.65;
            color: {INK};
            -webkit-font-smoothing: antialiased;
        }}

        /* ───────────────── Running page header ───────────────── */

        .page-header {{
            position: running(pageHeader);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 8pt;
            border-bottom: 0.5pt solid {RULE};
            width: 100%;
            /* One-line header — never wrap the type label or company name
             * when there's plenty of horizontal space on an A4 page. */
            white-space: nowrap;
            line-height: 1;
        }}
        .page-header .brand {{
            display: flex;
            align-items: center;
            gap: 8pt;
            flex-shrink: 0;
        }}
        .page-header .brand img {{
            height: 12pt;
            width: auto;
        }}
        .page-header .brand .sep {{
            width: 1pt;
            height: 9pt;
            background: {RULE};
        }}
        .page-header .brand .label {{
            font-size: 8pt;
            color: {INK_SOFT};
            letter-spacing: 0.5pt;
            text-transform: uppercase;
            font-weight: 600;
            white-space: nowrap;
        }}
        .page-header .company {{
            font-size: 8pt;
            color: {INK_MUTED};
            letter-spacing: 0.3pt;
            white-space: nowrap;
            flex-shrink: 0;
        }}

        /* ───────────────── Cover page ───────────────── */
        /* Layout: subtle gold corner decorations + centered composition with
         * a serif title, branch subtitle in brand gold, "Prepared for" block
         * anchored by an ornamental divider, and a bordered confidentiality
         * stamp at the bottom. No heavy color bands. */

        .cover {{
            page: cover;
            page-break-after: always;
            width: 100%;
            height: 297mm;
            position: relative;
            color: {INK};
            padding: 20mm 22mm 16mm 22mm;
            display: flex;
            flex-direction: column;
        }}

        /* Thin gold L-brackets anchoring each corner. These are drawn using
         * `::before` / `::after` on the `.cover` and a sibling `.cover-frame`
         * because WeasyPrint supports multiple pseudo-elements per node. */
        .cover .corner {{
            position: absolute;
            width: 12mm;
            height: 12mm;
            border-color: {BRAND_GOLD};
            border-style: solid;
            border-width: 0;
        }}
        .cover .corner-tl {{ top: 10mm; left: 10mm; border-top-width: 1pt; border-left-width: 1pt; }}
        .cover .corner-tr {{ top: 10mm; right: 10mm; border-top-width: 1pt; border-right-width: 1pt; }}
        .cover .corner-bl {{ bottom: 10mm; left: 10mm; border-bottom-width: 1pt; border-left-width: 1pt; }}
        .cover .corner-br {{ bottom: 10mm; right: 10mm; border-bottom-width: 1pt; border-right-width: 1pt; }}

        .cover-inner {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            padding: 6mm 10mm 8mm 10mm;
        }}

        .cover .cover-logo {{
            margin-top: 4mm;
            margin-bottom: 4mm;
        }}
        .cover .cover-logo img {{
            height: 24mm;
            width: auto;
        }}
        .cover .cover-logo .logo-fallback {{
            font-size: 32pt;
            font-weight: 800;
            letter-spacing: 6pt;
            color: {BRAND_GOLD_DARK};
        }}

        .cover .logo-rule {{
            width: 40pt;
            height: 1pt;
            background: {BRAND_GOLD};
            margin: 4pt 0 6mm 0;
        }}

        .cover .eyebrow-top {{
            font-size: 9pt;
            color: {BRAND_GOLD_DARK};
            letter-spacing: 6pt;
            text-transform: uppercase;
            font-weight: 700;
            margin-top: 4mm;
        }}

        .cover h1 {{
            font-family: "Georgia", "Times New Roman", "Noto Serif SC", serif;
            font-size: 36pt;
            line-height: 1.15;
            font-weight: 700;
            color: {INK};
            margin-top: 8mm;
            margin-bottom: 10pt;
            letter-spacing: 0.3pt;
            max-width: 140mm;
        }}

        .cover .branch {{
            font-family: "Georgia", "Times New Roman", "Noto Serif SC", serif;
            font-size: 18pt;
            font-style: italic;
            font-weight: 400;
            color: {BRAND_GOLD_DARK};
            margin-top: 2pt;
            margin-bottom: 10mm;
            letter-spacing: 0.3pt;
        }}

        /* Ornamental divider — three small diamonds in a row. */
        .cover .ornament {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8pt;
            margin: 4mm 0 6mm 0;
        }}
        .cover .ornament .rule-l,
        .cover .ornament .rule-r {{
            width: 36pt;
            height: 0.6pt;
            background: {BRAND_GOLD};
        }}
        .cover .ornament .diamond {{
            width: 5pt;
            height: 5pt;
            background: {BRAND_GOLD};
            transform: rotate(45deg);
            display: inline-block;
        }}

        .cover .prepared-for {{
            font-size: 8pt;
            color: {INK_MUTED};
            letter-spacing: 3pt;
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 6pt;
        }}

        .cover .company-name {{
            font-family: "Georgia", "Times New Roman", "Noto Serif SC", serif;
            font-size: 24pt;
            font-weight: 700;
            color: {INK};
            margin-bottom: 8mm;
        }}

        /* Meta strip: centered single row, elegant small-caps labels inline
         * with their values. Entire row is nowrap so long labels like
         * "专业作战图报告" stay on one line instead of breaking character-
         * by-character. */
        .cover .meta-strip {{
            margin-top: auto;
            padding: 10pt 0;
            border-top: 0.5pt solid {BRAND_GOLD};
            border-bottom: 0.5pt solid {BRAND_GOLD};
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 22pt;
            line-height: 1;
            white-space: nowrap;
        }}
        .cover .meta-strip .item {{
            display: flex;
            align-items: baseline;
            gap: 6pt;
            white-space: nowrap;
        }}
        .cover .meta-strip .k {{
            font-size: 7.5pt;
            color: {BRAND_GOLD_DARK};
            letter-spacing: 1.5pt;
            text-transform: uppercase;
            font-weight: 700;
            white-space: nowrap;
        }}
        .cover .meta-strip .v {{
            font-size: 10pt;
            color: {INK};
            font-weight: 600;
            white-space: nowrap;
        }}
        .cover .meta-strip .sep {{
            width: 4pt;
            height: 4pt;
            background: {BRAND_GOLD};
            transform: rotate(45deg);
            display: inline-block;
            flex-shrink: 0;
        }}

        .cover .confidential-stamp {{
            margin-top: 8mm;
            padding: 10pt 14pt;
            border: 0.5pt solid {BRAND_GOLD};
            border-radius: 2pt;
            font-size: 8pt;
            color: {INK_SOFT};
            letter-spacing: 0.5pt;
            line-height: 1.5;
            max-width: 120mm;
            text-align: center;
        }}
        .cover .confidential-stamp .stamp-label {{
            display: inline-block;
            font-size: 7.5pt;
            font-weight: 700;
            letter-spacing: 3pt;
            color: {BRAND_GOLD_DARK};
            text-transform: uppercase;
            margin-bottom: 4pt;
        }}

        .cover .footer-tagline {{
            margin-top: 6mm;
            font-size: 7.5pt;
            color: {INK_MUTED};
            letter-spacing: 1.2pt;
            text-align: center;
        }}

        /* ───────────────── Content sections ───────────────── */

        .report-section {{
            margin-bottom: 14pt;
            /* allow natural breaking — many AI sections are too long to avoid */
            page-break-inside: auto;
        }}
        /* Generous top margin between sections — the section heading needs
         * breathing room from the prior section's body for rhythm. */
        .report-section + .report-section {{
            margin-top: 30pt;
            page-break-before: auto;
        }}

        .section-head {{
            display: flex;
            align-items: baseline;
            gap: 10pt;
            /* Line-height 1 so the gold rule sits right under the glyph
             * baseline — otherwise the inherited 1.65 line-height adds ~10pt
             * of invisible space between the text and the rule. */
            line-height: 1;
            padding-bottom: 2pt;
            margin-bottom: 6pt;
            border-bottom: 1.5pt solid {BRAND_GOLD};
        }}
        .section-head .section-index {{
            font-size: 10pt;
            font-weight: 700;
            color: {BRAND_GOLD};
            letter-spacing: 1pt;
            font-family: "Inter", monospace;
            line-height: 1;
        }}
        .section-head h2 {{
            font-size: 16pt;
            font-weight: 700;
            color: {INK};
            letter-spacing: -0.2pt;
            flex: 1;
            line-height: 1;
        }}

        .section-body h3 {{
            font-size: 11.5pt;
            font-weight: 700;
            color: {INK};
            margin: 16pt 0 6pt 0;
            padding-left: 8pt;
            border-left: 3pt solid {BRAND_GOLD};
        }}

        .section-body h4 {{
            font-size: 10.5pt;
            font-weight: 700;
            color: {INK};
            margin: 12pt 0 4pt 0;
        }}

        /* The first element inside a section-body should sit tight against
         * the section heading's gold rule — the h3/p's own margin-top would
         * otherwise double the gap on top of section-head's margin. */
        .section-body > *:first-child {{
            margin-top: 0;
        }}

        .section-body p {{
            margin-bottom: 8pt;
            text-align: justify;
            text-justify: inter-ideograph;
        }}

        .section-body ul,
        .section-body ol {{
            margin: 6pt 0 10pt 16pt;
        }}
        .section-body li {{
            margin-bottom: 4pt;
        }}
        .section-body ul > li::marker {{ color: {BRAND_GOLD}; }}
        .section-body ol > li::marker {{ color: {BRAND_GOLD}; font-weight: 700; }}

        .section-body strong {{
            color: {BRAND_GOLD_DARK};
            font-weight: 700;
        }}

        .section-body em {{ font-style: italic; color: {INK_SOFT}; }}

        .section-body blockquote {{
            border-left: 3pt solid {BRAND_GOLD};
            padding: 8pt 14pt;
            margin: 10pt 0;
            background: {BRAND_GOLD_SOFT};
            color: {INK};
            font-style: italic;
        }}

        .section-body code {{
            font-family: "SF Mono", "Menlo", monospace;
            font-size: 9pt;
            background: #f5f5f4;
            padding: 1pt 4pt;
            border-radius: 2pt;
        }}

        .section-body pre {{
            background: #1f2937;
            color: #f9fafb;
            padding: 10pt;
            border-radius: 3pt;
            font-size: 9pt;
            overflow-x: auto;
            margin: 10pt 0;
        }}

        .section-body table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12pt 0;
            font-size: 9.5pt;
            page-break-inside: avoid;
        }}
        .section-body th {{
            background: {BRAND_GOLD_SOFT};
            border-bottom: 1.5pt solid {BRAND_GOLD};
            padding: 8pt 10pt;
            text-align: left;
            font-weight: 700;
            color: {BRAND_GOLD_DARK};
            letter-spacing: 0.3pt;
            text-transform: uppercase;
            font-size: 8.5pt;
        }}
        .section-body td {{
            border-bottom: 0.5pt solid {RULE};
            padding: 7pt 10pt;
            vertical-align: top;
        }}
        .section-body tr:last-child td {{ border-bottom: none; }}

        .section-body hr {{
            border: none;
            border-top: 0.5pt solid {RULE};
            margin: 16pt 0;
        }}
    </style>
</head>
<body>
    <!-- Running header — placed once, displayed on every non-cover page. -->
    <div class="page-header">
        <div class="brand">
            {logo_img if _LOGO_DATA_URL else '<span class="logo-fallback">IIFLE</span>'}
            <span class="sep"></span>
            <span class="label">{_escape(type_label)}</span>
        </div>
        <div class="company">{_escape(company_name)}</div>
    </div>

    <!-- ─────────────── COVER PAGE ─────────────── -->
    <div class="cover">
        <div class="corner corner-tl"></div>
        <div class="corner corner-tr"></div>
        <div class="corner corner-bl"></div>
        <div class="corner corner-br"></div>

        <div class="cover-inner">
            <div class="cover-logo">{logo_img}</div>
            <div class="logo-rule"></div>

            <div class="eyebrow-top">{'报 告' if is_cn else 'REPORT'}</div>
            <h1>{_escape(report_title)}</h1>
            {f'<div class="branch">{_escape(branch_label)}</div>' if branch_label else ''}

            <div class="ornament">
                <span class="rule-l"></span>
                <span class="diamond"></span>
                <span class="diamond"></span>
                <span class="diamond"></span>
                <span class="rule-r"></span>
            </div>

            <div class="prepared-for">{_escape(L('prepared_for'))}</div>
            <div class="company-name">{_escape(company_name)}</div>

            <div class="meta-strip">
                <div class="item">
                    <span class="k">{_escape(L('date'))}</span>
                    <span class="v">{_escape(generated_date)}</span>
                </div>
                <span class="sep"></span>
                <div class="item">
                    <span class="k">{_escape(L('report_type'))}</span>
                    <span class="v">{_escape(type_label)}</span>
                </div>
            </div>

            <div class="confidential-stamp">
                <div class="stamp-label">{'机 密' if is_cn else 'Confidential'}</div>
                <div>{_escape(L('confidential').split(' — ', 1)[1] if ' — ' in L('confidential') else L('confidential'))}</div>
            </div>

            <div class="footer-tagline">{_escape(footer_tagline)}</div>
        </div>
    </div>

    <!-- ─────────────── CONTENT ─────────────── -->
    {sections_html}
</body>
</html>"""


def _escape(text: str) -> str:
    """Escape HTML special characters. Safe for text nodes and attribute values."""
    if not text:
        return ""
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

    result = await db.execute(
        select(Report)
        .options(selectinload(Report.sections))
        .where(Report.id == report_id, Report.company_id == company_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise ValueError(f"Report {report_id} not found")

    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()

    # For battle map reports, resolve the variant's localized branch name
    # ("复制扩张作战图" / "Replication & Expansion Battle Map") so the cover
    # can render it as a subtitle below the main title.
    branch_label: str | None = None
    if report.report_type.value == "battle_map":
        bm_result = await db.execute(
            select(BattleMap).where(BattleMap.report_id == report_id)
        )
        bm = bm_result.scalar_one_or_none()
        if bm and bm.variant is not None:
            meta = variant_meta(bm.variant)
            branch_label = meta["name_zh"] if language == "cn" else meta["name_en"]

    html_content = _render_html(report, list(report.sections), company, language, branch_label)

    pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()

    logger.info("PDF generated for report %s (%d bytes)", report_id, len(pdf_bytes))
    return pdf_bytes
