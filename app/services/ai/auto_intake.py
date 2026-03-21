"""
Auto-Intake Service — extracts data from uploaded documents + web research
to automatically fill Stage 1 intake data (~80 fields).
"""

from __future__ import annotations

import json
import logging
import pathlib
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.document import Document
from app.models.research import CompanyResearch
from app.services.ai.provider import get_ai_client
from app.services.intake_service import save_draft

logger = logging.getLogger(__name__)

UPLOAD_DIR = pathlib.Path(__file__).resolve().parents[3] / "uploads"

# Maximum total chars of extracted text to include in the prompt context
MAX_DOCUMENT_CHARS = 50_000

# ──────────────────────────────────────────────────────────────────────
# Tool schema for structured Stage 1 output — mirrors stage_1.py exactly
# ──────────────────────────────────────────────────────────────────────

STAGE1_TOOL = {
    "name": "record_stage1",
    "description": (
        "Record the extracted Stage 1 intake data for the company. "
        "Fill in as many fields as possible from the provided documents and research. "
        "Use null for fields where data is not available."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "registration": {
                "type": "object",
                "description": "Section A: Registration Details",
                "properties": {
                    "legal_name": {"type": "string"},
                    "registration_number": {"type": "string"},
                    "date_of_incorporation": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "company_type": {"type": "string", "enum": ["sdn_bhd", "berhad", "llp", "sole_prop", "partnership"]},
                    "registered_address": {"type": "string"},
                    "operating_address": {"type": ["string", "null"]},
                    "website": {"type": ["string", "null"]},
                    "country_of_incorporation": {"type": "string", "enum": ["malaysia", "singapore", "others"]},
                    "other_jurisdictions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["legal_name", "registration_number", "date_of_incorporation", "company_type", "registered_address"],
            },
            "industry": {
                "type": "object",
                "description": "Section A: Industry Classification",
                "properties": {
                    "primary_industry": {"type": "string", "enum": ["fnb", "it", "manufacturing", "retail", "logistics", "property", "services", "others"]},
                    "sub_industry": {"type": "string"},
                    "msic_code": {"type": ["string", "null"]},
                    "brief_description": {"type": "string", "maxLength": 500},
                },
                "required": ["primary_industry", "sub_industry", "brief_description"],
            },
            "scale": {
                "type": "object",
                "description": "Section A: Company Scale",
                "properties": {
                    "total_employees": {"type": "integer", "minimum": 0},
                    "num_branches": {"type": ["integer", "null"]},
                    "operating_since": {"type": "integer", "minimum": 1800, "maximum": 2100},
                    "geographic_coverage": {"type": "array", "items": {"type": "string", "enum": ["local", "national", "regional", "international"]}},
                    "countries_of_operation": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["total_employees", "operating_since", "geographic_coverage"],
            },
            "founder": {
                "type": "object",
                "description": "Section B: Founder Profile",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer", "minimum": 18, "maximum": 120},
                    "nationality": {"type": "string"},
                    "highest_education": {"type": "string", "enum": ["secondary", "diploma", "degree", "masters", "phd", "professional", "emba"]},
                    "education_institution": {"type": ["string", "null"]},
                    "years_in_industry": {"type": "integer", "minimum": 0},
                    "years_business_experience": {"type": "integer", "minimum": 0},
                    "previous_companies_founded": {"type": "integer"},
                    "previous_exit_experience": {"type": "string", "enum": ["none", "sold", "listed", "both"]},
                    "emba_status": {"type": "string", "enum": ["none", "in_progress", "completed"]},
                    "emba_program": {"type": ["string", "null"]},
                },
                "required": ["name", "age", "nationality", "highest_education", "years_in_industry", "years_business_experience"],
            },
            "co_founders": {
                "type": "array",
                "description": "Section B: Co-founders",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "ownership_pct": {"type": "number", "minimum": 0, "maximum": 100},
                        "years_with_company": {"type": "integer", "minimum": 0},
                        "expertise": {"type": "string"},
                    },
                    "required": ["name", "role", "ownership_pct", "years_with_company", "expertise"],
                },
            },
            "management_team": {
                "type": "array",
                "description": "Section B: Key management team members",
                "items": {
                    "type": "object",
                    "properties": {
                        "position": {"type": "string"},
                        "name": {"type": ["string", "null"]},
                        "years_in_role": {"type": ["integer", "null"]},
                        "years_with_company": {"type": ["integer", "null"]},
                        "background": {"type": ["string", "null"]},
                    },
                    "required": ["position"],
                },
            },
            "succession": {
                "type": "object",
                "description": "Section B: Succession Planning",
                "properties": {
                    "has_succession_plan": {"type": "string", "enum": ["yes", "in_progress", "no"]},
                    "management_stable_3yr": {"type": "string", "enum": ["yes", "mostly", "no"]},
                    "key_person": {"type": "string"},
                    "key_person_contingency": {"type": "string", "maxLength": 300},
                },
                "required": ["has_succession_plan", "management_stable_3yr", "key_person", "key_person_contingency"],
            },
            "products": {
                "type": "array",
                "description": "Section C: Product/Service Offerings",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["product", "service", "subscription", "license"]},
                        "revenue_share_pct": {"type": "number", "minimum": 0, "maximum": 100},
                        "gross_margin_pct": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                        "growth_trend": {"type": "string", "enum": ["growing", "stable", "declining"]},
                    },
                    "required": ["name", "type", "revenue_share_pct", "growth_trend"],
                },
            },
            "product_competitiveness": {
                "type": "object",
                "description": "Section C: Product Competitiveness & IP",
                "properties": {
                    "differentiation": {"type": "string", "maxLength": 500},
                    "ip_type": {"type": "array", "items": {"type": "string", "enum": ["none", "patents", "trademarks", "trade_secrets", "proprietary_tech"]}},
                    "num_patents": {"type": ["integer", "null"]},
                    "rd_spending": {"type": ["number", "null"]},
                    "certifications": {"type": ["string", "null"]},
                },
                "required": ["differentiation", "ip_type"],
            },
            "customers": {
                "type": "object",
                "description": "Section C: Customer Profile",
                "properties": {
                    "customer_type": {"type": "string", "enum": ["b2b", "b2c", "b2g", "mixed"]},
                    "active_customers": {"type": "integer", "minimum": 0},
                    "top1_revenue_pct": {"type": "number", "minimum": 0, "maximum": 100},
                    "top5_revenue_pct": {"type": "number", "minimum": 0, "maximum": 100},
                    "top10_revenue_pct": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                    "avg_relationship_length": {"type": "string", "enum": ["lt_1yr", "1_3yr", "3_5yr", "5plus"]},
                    "retention_rate": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                    "long_term_contracts": {"type": "string", "enum": ["none", "some", "majority", "all"]},
                },
                "required": ["customer_type", "active_customers", "top1_revenue_pct", "top5_revenue_pct", "avg_relationship_length", "long_term_contracts"],
            },
            "supply_chain": {
                "type": "object",
                "description": "Section C: Supply Chain",
                "properties": {
                    "num_key_suppliers": {"type": "integer", "minimum": 0},
                    "single_supplier_dependency": {"type": "string", "enum": ["none", "low", "moderate", "high", "critical"]},
                    "supplier_agreements_documented": {"type": "string", "enum": ["all", "most", "some", "none"]},
                },
                "required": ["num_key_suppliers", "single_supplier_dependency", "supplier_agreements_documented"],
            },
            "revenue_model": {
                "type": "object",
                "description": "Section D: Revenue Model",
                "properties": {
                    "description": {"type": "string", "maxLength": 300},
                    "model_types": {"type": "array", "items": {"type": "string", "enum": ["product_sales", "service_fees", "subscription", "commission", "licensing", "franchise", "rental", "others"]}},
                    "recurring_revenue_pct": {"type": "number", "minimum": 0, "maximum": 100},
                    "is_seasonal": {"type": "string", "enum": ["not_seasonal", "mildly", "highly"]},
                    "peak_months": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 12}},
                },
                "required": ["description", "model_types", "recurring_revenue_pct", "is_seasonal"],
            },
            "scalability": {
                "type": "object",
                "description": "Section D: Scalability",
                "properties": {
                    "replicable": {"type": "string", "enum": ["easily", "with_effort", "difficult", "no"]},
                    "documented_sops": {"type": "string", "enum": ["comprehensive", "partial", "minimal", "none"]},
                    "central_facility": {"type": ["string", "null"], "enum": ["yes", "planned", "no", "na", None]},
                    "training_weeks": {"type": "integer", "minimum": 0},
                    "expansion_plan_3yr": {"type": "string", "maxLength": 300},
                },
                "required": ["replicable", "documented_sops", "training_weeks", "expansion_plan_3yr"],
            },
            "competitive_landscape": {
                "type": "object",
                "description": "Section D: Competitive Landscape",
                "properties": {
                    "top3_competitors": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
                    "estimated_market_share": {"type": "string", "enum": ["lt_1pct", "1_5pct", "5_10pct", "10_25pct", "25_50pct", "gt_50pct", "unknown"]},
                    "segment_leader": {"type": "boolean"},
                    "segment_leader_detail": {"type": ["string", "null"]},
                    "competitive_advantages": {"type": "array", "items": {"type": "string", "enum": ["price", "quality", "brand", "technology", "speed", "service", "location", "network", "others"]}},
                    "barriers_to_entry": {"type": "string", "enum": ["very_high", "high", "moderate", "low", "none"]},
                },
                "required": ["top3_competitors", "estimated_market_share", "segment_leader", "competitive_advantages", "barriers_to_entry"],
            },
            "financials": {
                "type": "object",
                "description": "Section E: 3-Year Financial Summary",
                "properties": {
                    "fy_end_month": {"type": "integer", "minimum": 1, "maximum": 12},
                    "year_t2": {
                        "type": "object",
                        "properties": {
                            "revenue": {"type": "number"},
                            "cogs": {"type": "number"},
                            "operating_expenses": {"type": "number"},
                            "pbt": {"type": "number"},
                            "pat": {"type": "number"},
                        },
                        "required": ["revenue", "cogs", "operating_expenses", "pbt", "pat"],
                    },
                    "year_t1": {
                        "type": "object",
                        "properties": {
                            "revenue": {"type": "number"},
                            "cogs": {"type": "number"},
                            "operating_expenses": {"type": "number"},
                            "pbt": {"type": "number"},
                            "pat": {"type": "number"},
                        },
                        "required": ["revenue", "cogs", "operating_expenses", "pbt", "pat"],
                    },
                    "year_t0": {
                        "type": "object",
                        "properties": {
                            "revenue": {"type": "number"},
                            "cogs": {"type": "number"},
                            "operating_expenses": {"type": "number"},
                            "pbt": {"type": "number"},
                            "pat": {"type": "number"},
                        },
                        "required": ["revenue", "cogs", "operating_expenses", "pbt", "pat"],
                    },
                },
                "required": ["fy_end_month", "year_t2", "year_t1", "year_t0"],
            },
            "balance_sheet": {
                "type": "object",
                "description": "Section E: Latest Balance Sheet",
                "properties": {
                    "cash": {"type": "number"},
                    "receivables": {"type": "number"},
                    "inventory": {"type": ["number", "null"]},
                    "current_assets": {"type": "number"},
                    "fixed_assets": {"type": "number"},
                    "total_assets": {"type": "number"},
                    "current_liabilities": {"type": "number"},
                    "bank_borrowings": {"type": "number"},
                    "total_liabilities": {"type": "number"},
                    "paid_up_capital": {"type": "number"},
                },
                "required": ["cash", "receivables", "current_assets", "fixed_assets", "total_assets", "current_liabilities", "bank_borrowings", "total_liabilities", "paid_up_capital"],
            },
            "cash_flow": {
                "type": "object",
                "description": "Section E: Cash Flow Basics",
                "properties": {
                    "cash_flow_positive": {"type": "string", "enum": ["yes_consistently", "sometimes", "no"]},
                    "monthly_opex": {"type": "number"},
                    "current_cash": {"type": "number"},
                    "customer_pay_days": {"type": "integer", "minimum": 0},
                    "supplier_pay_days": {"type": "integer", "minimum": 0},
                },
                "required": ["cash_flow_positive", "monthly_opex", "current_cash", "customer_pay_days", "supplier_pay_days"],
            },
            "audit_status": {
                "type": "object",
                "description": "Section E: Audit Status",
                "properties": {
                    "has_audited": {"type": "boolean"},
                    "years_audited": {"type": ["integer", "null"]},
                    "auditor_name": {"type": ["string", "null"]},
                    "aob_registered": {"type": ["string", "null"], "enum": ["yes", "no", "unknown", None]},
                    "accounting_standard": {"type": "string", "enum": ["mpers", "mfrs", "unknown"]},
                },
                "required": ["has_audited", "accounting_standard"],
            },
            "growth_plans": {
                "type": "object",
                "description": "Section F: Growth Plans",
                "properties": {
                    "revenue_target_yr1": {"type": "number"},
                    "revenue_target_yr3": {"type": "number"},
                    "revenue_target_yr5": {"type": ["number", "null"]},
                    "growth_strategy": {"type": "array", "items": {"type": "string", "enum": ["organic", "new_products", "new_markets", "acquisitions", "franchising", "online", "partnerships"]}},
                    "biggest_obstacle": {"type": "string", "maxLength": 300},
                },
                "required": ["revenue_target_yr1", "revenue_target_yr3", "growth_strategy", "biggest_obstacle"],
            },
            "capital_intentions": {
                "type": "object",
                "description": "Section F: Capital Intentions",
                "properties": {
                    "looking_to_raise": {"type": "string", "enum": ["yes_actively", "considering", "not_now", "no"]},
                    "raise_amount": {"type": ["number", "null"]},
                    "raise_purpose": {"type": "array", "items": {"type": "string", "enum": ["expansion", "working_capital", "rd", "ma", "debt_repayment", "ipo_prep", "others"]}},
                    "prior_funding": {"type": "array", "items": {"type": "string", "enum": ["never", "angel", "vc", "pe", "bank_loan", "government_grant", "others"]}},
                    "prior_amount": {"type": ["number", "null"]},
                },
                "required": ["looking_to_raise"],
            },
            "ipo_aspiration": {
                "type": "object",
                "description": "Section F: IPO Aspiration",
                "properties": {
                    "interest": {"type": "string", "enum": ["within_3yr", "within_5yr", "interested_unsure", "not_interested", "dont_know"]},
                    "preferred_markets": {"type": "array", "items": {"type": "string"}},
                    "engaged_advisors": {"type": ["string", "null"], "enum": ["yes", "in_discussions", "no", None]},
                    "biggest_barrier": {"type": ["string", "null"]},
                },
                "required": ["interest"],
            },
            "exit_preference": {
                "type": "object",
                "description": "Section F: Exit Preference",
                "properties": {
                    "long_term_goal": {"type": "string", "enum": ["keep_forever", "ipo", "sell", "next_generation", "dont_know"]},
                    "liquidity_timeline": {"type": ["string", "null"], "enum": ["1_2yr", "3_5yr", "5_10yr", "no_timeline", None]},
                },
                "required": ["long_term_goal"],
            },
            "org_maturity": {
                "type": "object",
                "description": "Section G: Organizational Maturity",
                "properties": {
                    "formal_org_chart": {"type": "string", "enum": ["yes", "partial", "no"]},
                    "num_departments": {"type": "integer", "minimum": 0},
                    "performance_reviews": {"type": "string", "enum": ["quarterly", "semi_annually", "annually", "rarely", "never"]},
                    "training_program": {"type": "string", "enum": ["systematic_733", "periodic", "adhoc", "none"]},
                    "turnover_rate": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
                    "hr_policies": {"type": "string", "enum": ["comprehensive", "basic", "none"]},
                },
                "required": ["formal_org_chart", "num_departments", "performance_reviews", "training_program", "hr_policies"],
            },
            "culture": {
                "type": "object",
                "description": "Section G: Culture & Values",
                "properties": {
                    "documented_vmv": {"type": "string", "enum": ["all_three", "some", "none"]},
                    "vision": {"type": ["string", "null"]},
                    "mission": {"type": ["string", "null"]},
                    "core_values": {"type": ["string", "null"]},
                },
                "required": ["documented_vmv"],
            },
        },
        "required": [],
    },
}


class AutoIntakeService:
    """Automatically fills Stage 1 intake data from uploaded files + web research."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = get_ai_client()

    async def process_company(self, company_id: uuid.UUID) -> dict:
        """Main entry point: extract from files + research + fill Stage 1.

        Steps:
        1. Get company info
        2. Get all uploaded documents for this company
        3. Extract text from each document (read file content)
        4. Do web research about the company
        5. Send everything to Claude with the Stage 1 schema
        6. Claude returns structured JSON matching the Stage 1 schema
        7. Save to intake_stages table as 'in_progress' status (draft)

        Returns the filled Stage 1 data dict.
        """
        # 1. Get company
        result = await self._db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise ValueError(f"Company {company_id} not found")

        logger.info("Starting auto-intake for company %s (%s)", company.legal_name, company_id)

        # 2. Get all uploaded documents
        doc_result = await self._db.execute(
            select(Document).where(Document.company_id == company_id)
        )
        documents = list(doc_result.scalars().all())
        logger.info("Found %d documents for company %s", len(documents), company_id)

        # 3. Extract text from documents
        extracted_texts = await self._extract_document_texts(company_id, documents)
        combined_text = self._combine_texts(extracted_texts)
        logger.info("Extracted %d chars of text from %d documents", len(combined_text), len(extracted_texts))

        # 4. Get web research (if available)
        research_context = await self._get_research_context(company_id)

        # 5. Build context and ask Claude to fill Stage 1
        company_context = {
            "name": company.legal_name,
            "registration_number": company.registration_number or "",
            "date_of_incorporation": str(company.date_of_incorporation) if company.date_of_incorporation else "",
            "company_type": company.company_type or "",
            "industry": company.primary_industry or "",
            "sub_industry": company.sub_industry or "",
            "country": company.country or "Malaysia",
            "website": company.website or "",
            "description": company.brief_description or "",
        }

        stage1_data = await self._extract_stage1_from_context(
            company_context=company_context,
            document_text=combined_text,
            research_data=research_context,
        )

        # 6. Clean up nulls — remove None values from nested dicts so Pydantic is happy
        stage1_data = self._clean_output(stage1_data)

        # 7. Save as submitted (auto-intake skips review)
        from app.services.intake_service import submit_stage

        try:
            await submit_stage(
                db=self._db,
                company_id=company_id,
                stage="1",
                data=stage1_data,
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # system user
            )
        except Exception:
            # Validation may fail — fall back to save_draft
            await save_draft(
                db=self._db,
                company_id=company_id,
                stage="1",
                data=stage1_data,
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            )
            # Mark as submitted anyway so scoring can proceed
            from app.models.intake import IntakeStage
            await self._db.execute(
                update(IntakeStage)
                .where(IntakeStage.company_id == company_id, IntakeStage.stage == "1")
                .values(status="submitted")
            )

        await self._db.commit()
        logger.info("Auto-intake completed for company %s — submitted", company.legal_name)

        # 8. Auto-trigger scoring (Module 1 + 2)
        try:
            from app.services.scoring.engine import ScoringEngine
            engine = ScoringEngine(self._db)
            await engine.score_stage1(company_id, stage1_data, self._db)
            await self._db.commit()
            logger.info("Auto-scoring completed for company %s", company.legal_name)
        except Exception as exc:
            logger.exception("Auto-scoring failed for %s: %s", company.legal_name, exc)

        return stage1_data

    # ------------------------------------------------------------------
    # Document text extraction
    # ------------------------------------------------------------------

    async def _extract_document_texts(
        self, company_id: uuid.UUID, documents: list[Document]
    ) -> list[dict[str, str]]:
        """Extract text from each uploaded document."""
        results = []
        for doc in documents:
            local_path = UPLOAD_DIR / str(company_id) / doc.category.value / doc.filename
            if not local_path.exists():
                logger.warning("File not found on disk: %s", local_path)
                continue

            text = self._extract_text_from_file(local_path, doc.mime_type)
            if text and text.strip():
                results.append({
                    "filename": doc.original_filename,
                    "category": doc.category.value,
                    "text": text,
                })
        return results

    @staticmethod
    def _extract_text_from_file(path: pathlib.Path, mime_type: str) -> str:
        """Extract text from a single file based on its type."""
        suffix = path.suffix.lower()

        # PDF files — use PyMuPDF
        if suffix == ".pdf" or mime_type == "application/pdf":
            try:
                import pymupdf
                doc = pymupdf.open(str(path))
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                return text
            except ImportError:
                logger.warning("pymupdf not installed — skipping PDF: %s", path.name)
                return ""
            except Exception as exc:
                logger.warning("Failed to extract PDF text from %s: %s", path.name, exc)
                return ""

        # Text-based files
        if suffix in (".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"):
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.warning("Failed to read text file %s: %s", path.name, exc)
                return ""

        # DOCX files
        if suffix == ".docx":
            try:
                import docx
                doc = docx.Document(str(path))
                return "\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                logger.warning("python-docx not installed — skipping DOCX: %s", path.name)
                return ""
            except Exception as exc:
                logger.warning("Failed to read DOCX %s: %s", path.name, exc)
                return ""

        # XLSX files
        if suffix in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
                lines = []
                for ws in wb.worksheets:
                    lines.append(f"--- Sheet: {ws.title} ---")
                    for row in ws.iter_rows(values_only=True):
                        line = "\t".join(str(c) if c is not None else "" for c in row)
                        if line.strip():
                            lines.append(line)
                wb.close()
                return "\n".join(lines)
            except ImportError:
                logger.warning("openpyxl not installed — skipping XLSX: %s", path.name)
                return ""
            except Exception as exc:
                logger.warning("Failed to read XLSX %s: %s", path.name, exc)
                return ""

        # Fallback: try to read as text
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            logger.debug("Skipping unsupported file type: %s", path.name)
            return ""

    @staticmethod
    def _combine_texts(extracted: list[dict[str, str]]) -> str:
        """Combine extracted texts, capping at MAX_DOCUMENT_CHARS."""
        parts = []
        total = 0
        for item in extracted:
            header = f"\n\n===== Document: {item['filename']} (Category: {item['category']}) =====\n\n"
            text = item["text"]
            remaining = MAX_DOCUMENT_CHARS - total - len(header)
            if remaining <= 0:
                break
            if len(text) > remaining:
                text = text[:remaining] + "\n... [truncated]"
            parts.append(header + text)
            total += len(header) + len(text)
        return "".join(parts)

    # ------------------------------------------------------------------
    # Research context
    # ------------------------------------------------------------------

    async def _get_research_context(self, company_id: uuid.UUID) -> dict[str, Any]:
        """Get existing research data if available."""
        result = await self._db.execute(
            select(CompanyResearch)
            .where(
                CompanyResearch.company_id == company_id,
                CompanyResearch.status == "completed",
            )
            .order_by(CompanyResearch.created_at.desc())
            .limit(1)
        )
        research = result.scalar_one_or_none()
        if not research:
            return {}

        return {
            "company_research": research.company_data or {},
            "industry_research": research.industry_data or {},
            "peer_research": research.peer_data or {},
        }

    # ------------------------------------------------------------------
    # Claude extraction
    # ------------------------------------------------------------------

    async def _extract_stage1_from_context(
        self,
        company_context: dict[str, str],
        document_text: str,
        research_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Send all context to Claude and get structured Stage 1 data back."""

        system_prompt = (
            "You are a data extraction specialist for IIFLE, a Malaysian capital-market "
            "advisory platform. Your job is to extract structured company intake data from "
            "uploaded documents and research findings.\n\n"
            "RULES:\n"
            "- Extract as many fields as possible from the provided documents and research.\n"
            "- For fields where data is clearly stated in documents, use the exact values.\n"
            "- For fields that can be reasonably inferred, make your best estimate and note it.\n"
            "- For financial figures, use the values as stated. All monetary values should be in MYR (RM) unless clearly stated otherwise.\n"
            "- For enum fields, you MUST pick one of the valid enum values listed in the tool schema.\n"
            "- Omit sections entirely if there is zero data available for them — do not fabricate.\n"
            "- When data is partially available for a section, fill what you can and use reasonable defaults for required fields.\n"
            "- Dates must be in YYYY-MM-DD format.\n"
            "- Be conservative with estimates — it's better to omit than to fabricate."
        )

        # Build the user prompt with all context
        parts = [
            "# Company Auto-Intake: Extract Stage 1 Data\n\n",
            "## Company Basic Information\n",
            json.dumps(company_context, indent=2, default=str),
            "\n\n",
        ]

        if document_text:
            parts.append("## Uploaded Documents Content\n")
            parts.append(document_text)
            parts.append("\n\n")

        if research_data:
            parts.append("## Web Research Findings\n")
            parts.append(json.dumps(research_data, indent=2, default=str))
            parts.append("\n\n")

        parts.append(
            "## Task\n"
            "Extract ALL available Stage 1 intake data from the above documents and research.\n"
            "Fill in the following sections as completely as possible:\n\n"
            "- **Section A**: registration, industry, scale\n"
            "- **Section B**: founder, co_founders, management_team, succession\n"
            "- **Section C**: products, product_competitiveness, customers, supply_chain\n"
            "- **Section D**: revenue_model, scalability, competitive_landscape\n"
            "- **Section E**: financials (3yr), balance_sheet, cash_flow, audit_status\n"
            "- **Section F**: growth_plans, capital_intentions, ipo_aspiration, exit_preference\n"
            "- **Section G**: org_maturity, culture\n\n"
            "Call the record_stage1 tool with the extracted data. "
            "Only include sections where you have at least some data. "
            "Do NOT fabricate data — if a section has no supporting evidence, omit it entirely."
        )

        user_content = "".join(parts)

        from app.services.ai.groq_client import GroqClient

        if isinstance(self._client, GroqClient):
            # Groq: ask for JSON directly with EXACT key names
            json_prompt = system_prompt + (
                "\n\nYou MUST respond with ONLY a valid JSON object using these EXACT top-level keys:\n"
                '{\n'
                '  "registration": {"legal_name": "", "registration_number": "", "date_of_incorporation": "YYYY-MM-DD", "company_type": "sdn_bhd|berhad|llp|sole_prop|partnership", "registered_address": "", "operating_address": "", "website": "", "country_of_incorporation": "malaysia|singapore|others", "other_jurisdictions": []},\n'
                '  "industry": {"primary_industry": "fnb|it|manufacturing|retail|logistics|property|services|others", "sub_industry": "", "msic_code": "", "brief_description": ""},\n'
                '  "scale": {"total_employees": 0, "num_branches": 0, "operating_since": 2000, "geographic_coverage": ["local","national","regional","international"], "countries_of_operation": []},\n'
                '  "founder": {"name": "", "age": 0, "nationality": "", "highest_education": "secondary|diploma|degree|masters|phd|professional|emba", "education_institution": "", "years_in_industry": 0, "years_business_experience": 0, "previous_companies_founded": 0, "previous_exit_experience": "none|sold|listed|both", "emba_status": "none|in_progress|completed", "emba_program": ""},\n'
                '  "co_founders": [{"name": "", "role": "", "ownership_pct": 0, "years_with_company": 0, "expertise": ""}],\n'
                '  "management_team": [{"position": "", "name": "", "years_in_role": 0, "years_with_company": 0, "background": ""}],\n'
                '  "succession": {"has_succession_plan": "yes|in_progress|no", "management_stable_3yr": "yes|mostly|no", "key_person": "", "key_person_contingency": ""},\n'
                '  "products": [{"name": "", "type": "product|service|subscription|license", "revenue_share_pct": 0, "gross_margin_pct": 0, "growth_trend": "growing|stable|declining"}],\n'
                '  "product_competitiveness": {"differentiation": "", "ip_type": ["none","patents","trademarks","trade_secrets","proprietary_tech"], "num_patents": 0, "rd_spending": 0, "certifications": ""},\n'
                '  "customers": {"customer_type": "b2b|b2c|b2g|mixed", "active_customers": 0, "top1_revenue_pct": 0, "top5_revenue_pct": 0, "avg_relationship_length": "lt_1yr|1_3yr|3_5yr|5plus", "retention_rate": 0, "long_term_contracts": "none|some|majority|all"},\n'
                '  "supply_chain": {"num_key_suppliers": 0, "single_supplier_dependency": "none|low|moderate|high|critical", "supplier_agreements_documented": "all|most|some|none"},\n'
                '  "revenue_model": {"description": "", "model_types": ["product_sales","service_fees","subscription","commission","licensing","franchise","rental","others"], "recurring_revenue_pct": 0, "is_seasonal": "not_seasonal|mildly|highly", "peak_months": []},\n'
                '  "scalability": {"replicable": "easily|with_effort|difficult|no", "documented_sops": "comprehensive|partial|minimal|none", "central_facility": "yes|planned|no|na", "training_weeks": 0, "expansion_plan_3yr": ""},\n'
                '  "competitive_landscape": {"top3_competitors": [], "estimated_market_share": "lt_1pct|1_5pct|5_10pct|10_25pct|25_50pct|gt_50pct|unknown", "segment_leader": true, "segment_leader_detail": "", "competitive_advantages": ["price","quality","brand","technology","speed","service","location","network","others"], "barriers_to_entry": "very_high|high|moderate|low|none"},\n'
                '  "financials": {"fy_end_month": 6, "year_t2": {"revenue": 0, "cogs": 0, "operating_expenses": 0, "pbt": 0, "pat": 0}, "year_t1": {...}, "year_t0": {...}},\n'
                '  "balance_sheet": {"cash": 0, "receivables": 0, "inventory": 0, "current_assets": 0, "fixed_assets": 0, "total_assets": 0, "current_liabilities": 0, "bank_borrowings": 0, "total_liabilities": 0, "paid_up_capital": 0},\n'
                '  "cash_flow": {"cash_flow_positive": "yes_consistently|sometimes|no", "monthly_opex": 0, "current_cash": 0, "customer_pay_days": 0, "supplier_pay_days": 0},\n'
                '  "audit_status": {"has_audited": true, "years_audited": 0, "auditor_name": "", "aob_registered": "yes|no|unknown", "accounting_standard": "mpers|mfrs|unknown"},\n'
                '  "growth_plans": {"revenue_target_yr1": 0, "revenue_target_yr3": 0, "revenue_target_yr5": 0, "growth_strategy": [], "biggest_obstacle": ""},\n'
                '  "capital_intentions": {"looking_to_raise": "yes_actively|considering|not_now|no", "raise_amount": 0, "raise_purpose": [], "prior_funding": [], "prior_amount": 0},\n'
                '  "ipo_aspiration": {"interest": "within_3yr|within_5yr|interested_unsure|not_interested|dont_know", "preferred_markets": [], "engaged_advisors": "yes|in_discussions|no", "biggest_barrier": ""},\n'
                '  "exit_preference": {"long_term_goal": "keep_forever|ipo|sell|next_generation|dont_know", "liquidity_timeline": "1_2yr|3_5yr|5_10yr|no_timeline"},\n'
                '  "org_maturity": {"formal_org_chart": "yes|partial|no", "num_departments": 0, "performance_reviews": "quarterly|semi_annually|annually|rarely|never", "training_program": "systematic_733|periodic|adhoc|none", "turnover_rate": 0, "hr_policies": "comprehensive|basic|none"},\n'
                '  "culture": {"documented_vmv": "all_three|some|none", "vision": "", "mission": "", "core_values": ""}\n'
                '}\n\n'
                "Use EXACTLY these key names. For enum fields, pick one of the values shown after |. "
                "Omit sections where you have no data. No markdown — just the JSON."
            )
            result = await self._client.extract_structured_data(json_prompt, user_content, temperature=0.1)
            if result:
                return result
            raise RuntimeError("Groq did not return valid Stage 1 JSON")
        else:
            # Anthropic: use tool_use
            response = await self._client._call_with_retry(
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                tools=[STAGE1_TOOL],
                tool_choice={"type": "tool", "name": "record_stage1"},
                temperature=0.1,
                max_tokens=8192,
            )

            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and block.name == "record_stage1":
                    return dict(block.input)

            raise RuntimeError("Claude did not return record_stage1 tool call")

    # ------------------------------------------------------------------
    # Output cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_output(data: dict[str, Any]) -> dict[str, Any]:
        """Remove None values and empty structures to keep the output clean."""

        def _clean(obj: Any) -> Any:
            if isinstance(obj, dict):
                cleaned = {}
                for k, v in obj.items():
                    v = _clean(v)
                    if v is not None:
                        cleaned[k] = v
                return cleaned if cleaned else None
            elif isinstance(obj, list):
                cleaned = [_clean(item) for item in obj if _clean(item) is not None]
                return cleaned
            else:
                return obj

        result = _clean(data)
        return result if isinstance(result, dict) else {}
