"""
PDF Extraction Service (Pattern C) — two-pass pipeline for audited financial reports.

Pass 1: PyMuPDF digital text extraction (fast, cheap)
Pass 2: Claude Vision for scanned PDFs and complex tables (AI fallback)

Output: Structured data mapped to Stage 2 schema fields.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try to import pymupdf (optional dependency)
try:
    import pymupdf  # PyMuPDF >= 1.24
except ImportError:
    try:
        import fitz as pymupdf  # type: ignore[no-redef]
    except ImportError:
        pymupdf = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Text extraction (Pass 1)
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a digital PDF using PyMuPDF."""
    if pymupdf is None:
        raise RuntimeError("PyMuPDF (pymupdf) is not installed. Install with: pip install pymupdf")

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    pages_text: list[str] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages_text.append(f"--- Page {page_num + 1} ---\n{text}")
    doc.close()
    return "\n\n".join(pages_text)


def extract_tables_from_pdf(file_bytes: bytes) -> list[dict[str, Any]]:
    """Extract tables from a PDF using PyMuPDF's table detection."""
    if pymupdf is None:
        return []

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    tables: list[dict[str, Any]] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        try:
            page_tables = page.find_tables()
            for idx, table in enumerate(page_tables):
                data = table.extract()
                if data and len(data) > 1:  # header + at least one row
                    tables.append({
                        "page": page_num + 1,
                        "table_index": idx,
                        "headers": data[0],
                        "rows": data[1:],
                    })
        except Exception:
            # Table detection not available in all PyMuPDF versions
            pass
    doc.close()
    return tables


def is_scanned_pdf(file_bytes: bytes) -> bool:
    """Check if a PDF is scanned (image-based) vs digital (text-based)."""
    if pymupdf is None:
        return True  # Assume scanned if we can't check

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    total_pages = len(doc)
    text_pages = 0
    for page_num in range(min(total_pages, 5)):  # Check first 5 pages
        page = doc[page_num]
        text = page.get_text("text").strip()
        if len(text) > 50:
            text_pages += 1
    doc.close()
    return text_pages < (min(total_pages, 5) / 2)


# ---------------------------------------------------------------------------
# AI extraction (Pass 2)
# ---------------------------------------------------------------------------

def pdf_pages_to_images(file_bytes: bytes, max_pages: int = 20) -> list[str]:
    """Convert PDF pages to base64-encoded PNG images for Claude Vision."""
    if pymupdf is None:
        raise RuntimeError("PyMuPDF is required for image conversion")

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    images: list[str] = []
    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        # Render at 150 DPI for good quality without being too large
        mat = pymupdf.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("ascii")
        images.append(b64)
    doc.close()
    return images


EXTRACTION_PROMPT = """\
You are a financial document extraction specialist. Extract structured financial data
from this audited financial report into the following categories. Return a JSON object.

## Categories to Extract

### income_statement (for each year found)
- fiscal_year, total_revenue, cost_of_goods_sold, gross_profit
- staff_costs, rental_expenses, depreciation_amortization
- marketing_expenses, administrative_expenses, other_operating_expenses
- total_operating_expenses, ebitda, ebit
- interest_income, interest_expense, profit_before_tax, tax_expense, profit_after_tax

### balance_sheet (for each year found)
- fiscal_year, cash_and_equivalents, trade_receivables, other_receivables
- inventory, total_current_assets
- property_plant_equipment, right_of_use_assets, intangible_assets
- goodwill, total_non_current_assets, total_assets
- trade_payables, other_payables, short_term_borrowings
- total_current_liabilities, long_term_borrowings, total_non_current_liabilities
- total_liabilities, paid_up_capital, retained_earnings, total_equity

### cash_flow (for each year found)
- fiscal_year, net_operating_cash_flow, capex
- net_investing_cash_flow, net_financing_cash_flow
- net_change_in_cash, opening_cash, closing_cash

### audit_info
- auditor_name, auditor_firm, accounting_standard, audit_opinion
- fiscal_year_end

## Important Rules
- All monetary values should be in RM (millions) unless stated otherwise
- Extract ALL years available (typically 2-3 years of comparative data)
- If a value cannot be determined, use null
- Provide the JSON response only, no explanation text
"""


class PDFExtractionService:
    """Two-pass PDF extraction service for financial documents."""

    def __init__(self, ai_client=None):
        self._client = ai_client

    async def extract(
        self,
        file_bytes: bytes,
        filename: str = "",
        force_ai: bool = False,
    ) -> dict[str, Any]:
        """Extract financial data from a PDF using two-pass pipeline.

        Pass 1: PyMuPDF text extraction (fast)
        Pass 2: Claude Vision if scanned or tables are complex

        Returns a dict with keys: income_statement, balance_sheet, cash_flow, audit_info,
        extraction_method, confidence
        """
        result: dict[str, Any] = {
            "extraction_method": None,
            "confidence": "low",
            "income_statement": [],
            "balance_sheet": [],
            "cash_flow": [],
            "audit_info": {},
            "raw_text": None,
        }

        # Pass 1: Try digital text extraction
        if not force_ai:
            try:
                scanned = is_scanned_pdf(file_bytes)
                if not scanned:
                    text = extract_text_from_pdf(file_bytes)
                    tables = extract_tables_from_pdf(file_bytes)

                    if len(text) > 200:
                        result["raw_text"] = text[:50000]  # Cap at 50K chars
                        result["extraction_method"] = "pymupdf_text"

                        # Try to parse with AI using extracted text
                        if self._client:
                            ai_result = await self._extract_with_text(text, tables)
                            result.update(ai_result)
                            result["confidence"] = "medium"
                            return result
            except Exception as exc:
                logger.warning("Pass 1 (text) extraction failed for %s: %s", filename, exc)

        # Pass 2: AI Vision fallback
        if self._client:
            try:
                ai_result = await self._extract_with_vision(file_bytes)
                result.update(ai_result)
                result["extraction_method"] = "ai_vision"
                result["confidence"] = "medium"
            except Exception as exc:
                logger.warning("Pass 2 (vision) extraction failed for %s: %s", filename, exc)
                result["confidence"] = "failed"

        return result

    async def _extract_with_text(
        self,
        text: str,
        tables: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Use Claude to parse extracted text into structured data."""
        # Format tables for the prompt
        table_text = ""
        for tbl in tables[:10]:
            table_text += f"\n[Table on page {tbl['page']}]\n"
            if tbl["headers"]:
                table_text += " | ".join(str(h) for h in tbl["headers"]) + "\n"
            for row in tbl["rows"][:30]:
                table_text += " | ".join(str(c) for c in row) + "\n"

        prompt = f"""{EXTRACTION_PROMPT}

## Document Text
{text[:30000]}

## Detected Tables
{table_text[:15000]}
"""
        result = await self._client.generate_json(
            prompt=prompt,
            system="You are a financial document parser. Return valid JSON only.",
        )
        return _normalize_extraction(result)

    async def _extract_with_vision(self, file_bytes: bytes) -> dict[str, Any]:
        """Use Claude Vision to extract from scanned/image PDF."""
        images = pdf_pages_to_images(file_bytes, max_pages=15)

        if not images:
            return {}

        # Build message with images
        content: list[dict[str, Any]] = []
        for i, img_b64 in enumerate(images):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                },
            })

        content.append({
            "type": "text",
            "text": EXTRACTION_PROMPT,
        })

        result = await self._client.generate_json_with_images(
            content=content,
            system="You are a financial document parser. Return valid JSON only.",
        )
        return _normalize_extraction(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_extraction(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize AI extraction output to consistent format."""
    result: dict[str, Any] = {
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow": [],
        "audit_info": {},
    }

    # Income statements
    inc = raw.get("income_statement", [])
    if isinstance(inc, dict):
        inc = [inc]
    result["income_statement"] = [_clean_numbers(item) for item in inc if isinstance(item, dict)]

    # Balance sheets
    bs = raw.get("balance_sheet", [])
    if isinstance(bs, dict):
        bs = [bs]
    result["balance_sheet"] = [_clean_numbers(item) for item in bs if isinstance(item, dict)]

    # Cash flows
    cf = raw.get("cash_flow", [])
    if isinstance(cf, dict):
        cf = [cf]
    result["cash_flow"] = [_clean_numbers(item) for item in cf if isinstance(item, dict)]

    # Audit info
    audit = raw.get("audit_info", {})
    if isinstance(audit, dict):
        result["audit_info"] = audit

    return result


def _clean_numbers(d: dict[str, Any]) -> dict[str, Any]:
    """Clean number fields: handle strings with commas, brackets for negatives."""
    cleaned = {}
    for k, v in d.items():
        if isinstance(v, str):
            v = v.strip()
            # Handle (1,234) = -1234
            if v.startswith("(") and v.endswith(")"):
                v = "-" + v[1:-1]
            v = v.replace(",", "").replace(" ", "")
            try:
                cleaned[k] = float(v)
            except ValueError:
                cleaned[k] = v
        else:
            cleaned[k] = v
    return cleaned


def map_extraction_to_stage2(extracted: dict[str, Any]) -> dict[str, Any]:
    """Map extracted financial data to Stage 2 schema structure.

    Returns a dict that can be used to pre-populate Stage 2 intake form.
    """
    stage2: dict[str, Any] = {}

    # Map audit info
    audit_raw = extracted.get("audit_info", {})
    if audit_raw:
        stage2["audit"] = {
            "audit_info": {
                "auditor_name": audit_raw.get("auditor_name"),
                "auditor_firm": audit_raw.get("auditor_firm"),
                "accounting_standard": audit_raw.get("accounting_standard", "unknown"),
                "audit_opinion": audit_raw.get("audit_opinion", "unknown"),
                "has_audited_accounts": True,
                "years_audited": len(extracted.get("income_statement", [])),
            },
        }

    # Map income statements
    inc_years = extracted.get("income_statement", [])
    if inc_years:
        sorted_years = sorted(inc_years, key=lambda x: x.get("fiscal_year", 0))
        inc_map = {}
        for i, yr in enumerate(sorted_years[-3:]):
            key = ["year_t2", "year_t1", "year_t0"][max(0, 3 - len(sorted_years) + i)]
            inc_map[key] = yr
        stage2["income_statement"] = inc_map

    # Map balance sheets
    bs_years = extracted.get("balance_sheet", [])
    if bs_years:
        sorted_years = sorted(bs_years, key=lambda x: x.get("fiscal_year", 0))
        bs_map = {}
        for i, yr in enumerate(sorted_years[-3:]):
            key = ["year_t2", "year_t1", "year_t0"][max(0, 3 - len(sorted_years) + i)]
            bs_map[key] = yr
        stage2["balance_sheet"] = bs_map

    # Map cash flows
    cf_years = extracted.get("cash_flow", [])
    if cf_years:
        sorted_years = sorted(cf_years, key=lambda x: x.get("fiscal_year", 0))
        cf_map = {}
        for i, yr in enumerate(sorted_years[-3:]):
            key = ["year_t2", "year_t1", "year_t0"][max(0, 3 - len(sorted_years) + i)]
            cf_map[key] = yr
        stage2["cash_flow"] = cf_map

    return stage2
