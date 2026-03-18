"""
Due Diligence Research Service — auto-triggers on company creation.
Uses Claude web search to gather company, industry, and peer data.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.research import CompanyResearch
from app.services.ai.provider import get_ai_client

logger = logging.getLogger(__name__)


class ResearchService:
    """Orchestrates due diligence research for a company."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = get_ai_client()

    async def run_full_research(self, company_id: uuid.UUID) -> CompanyResearch:
        """Run full DD research for a company. Creates/updates CompanyResearch record."""

        # Get company info
        result = await self._db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise ValueError(f"Company {company_id} not found")

        # Check for existing recent research (skip if < 7 days old)
        existing = await self._db.execute(
            select(CompanyResearch)
            .where(CompanyResearch.company_id == company_id)
            .order_by(CompanyResearch.created_at.desc())
            .limit(1)
        )
        recent = existing.scalar_one_or_none()
        if recent and recent.status == "completed" and recent.research_date:
            age = datetime.now(timezone.utc) - recent.research_date.replace(tzinfo=timezone.utc)
            if age < timedelta(days=7):
                logger.info("Skipping research for %s — recent results exist", company.legal_name)
                return recent

        # Create research record
        research = CompanyResearch(
            id=uuid.uuid4(),
            company_id=company_id,
            research_type="full",
            status="in_progress",
            company_data={},
            industry_data={},
            peer_data={},
            sources=[],
        )
        self._db.add(research)
        await self._db.flush()

        company_context = {
            "name": company.legal_name,
            "industry": company.primary_industry or "Unknown",
            "sub_industry": company.sub_industry or "",
            "country": company.country or "Malaysia",
            "description": company.brief_description or "",
            "website": company.website or "",
        }

        try:
            # Run three research queries in sequence (to stay within rate limits)
            company_data = await self._research_company(company_context)
            industry_data = await self._research_industry(company_context)
            peer_data = await self._research_peers(company_context)

            research.company_data = company_data
            research.industry_data = industry_data
            research.peer_data = peer_data
            research.sources = (
                company_data.get("sources", [])
                + industry_data.get("sources", [])
                + peer_data.get("sources", [])
            )
            research.status = "completed"
            research.research_date = datetime.now(timezone.utc)
            research.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        except Exception as exc:
            logger.exception("Research failed for company %s: %s", company.legal_name, exc)
            research.status = "failed"
            research.company_data = {"error": str(exc)}

        await self._db.flush()
        return research

    async def _research_company(self, ctx: dict) -> dict:
        """Research the company itself: news, reputation, key people."""
        try:
            result = await self._client.research_web(
                query=f"{ctx['name']} company news financials reputation {ctx['country']}",
                company_context=ctx,
            )
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as exc:
            logger.warning("Company research failed: %s", exc)
            return {"error": str(exc), "sources": []}

    async def _research_industry(self, ctx: dict) -> dict:
        """Research the industry: TAM, trends, PESTEL, regulations."""
        try:
            result = await self._client.research_web(
                query=f"{ctx['industry']} industry market size trends {ctx['country']} 2025 2026",
                company_context=ctx,
            )
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as exc:
            logger.warning("Industry research failed: %s", exc)
            return {"error": str(exc), "sources": []}

    async def _research_peers(self, ctx: dict) -> dict:
        """Research comparable companies and competitors."""
        try:
            result = await self._client.research_web(
                query=f"{ctx['industry']} top companies competitors {ctx['country']} listed comparable {ctx.get('sub_industry', '')}",
                company_context=ctx,
            )
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as exc:
            logger.warning("Peer research failed: %s", exc)
            return {"error": str(exc), "sources": []}
