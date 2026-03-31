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

    async def run_full_research(self, company_id: uuid.UUID, force: bool = False) -> CompanyResearch:
        """Run full DD research for a company. Creates/updates CompanyResearch record."""

        # Get company info
        result = await self._db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise ValueError(f"Company {company_id} not found")

        # Check for existing recent research (skip if < 7 days old, unless forced)
        existing = await self._db.execute(
            select(CompanyResearch)
            .where(CompanyResearch.company_id == company_id)
            .order_by(CompanyResearch.created_at.desc())
            .limit(1)
        )
        recent = existing.scalar_one_or_none()
        if not force and recent and recent.status == "completed" and recent.research_date:
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
            # Run four research queries
            company_data = await self._research_company(company_context)
            people_data = await self._research_people(company_context)
            industry_data = await self._research_industry(company_context)
            peer_data = await self._research_peers(company_context)

            # Merge people data into company_data
            if people_data:
                company_data["key_people"] = people_data.get("key_people", {})
                company_data["leadership"] = people_data.get("leadership", "")
                company_data["founders"] = people_data.get("founders", "")
                company_data["board"] = people_data.get("board", "")

            research.company_data = company_data
            research.industry_data = industry_data
            research.peer_data = peer_data
            research.sources = []  # Don't expose raw source URLs
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
        """Research the company: profile, news, reputation, products."""
        try:
            result = await self._client.research_web(
                query=f'"{ctx["name"]}" company profile products services news {ctx["country"]}',
                company_context=ctx,
            )
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as exc:
            logger.warning("Company research failed: %s", exc)
            return {"error": str(exc)}

    async def _research_people(self, ctx: dict) -> dict:
        """Research key people: founders, CEO, directors, shareholders."""
        from app.services.ai.web_search import get_web_search

        web_search = get_web_search()
        web_context = ""
        if web_search:
            try:
                results = await web_search.search(
                    f'"{ctx["name"]}" founder CEO director shareholders team {ctx["country"]}',
                    max_results=5,
                )
                web_context = "\n\n".join(
                    f"### {r['title']}\n{r['content']}" for r in results if r.get("content")
                )
            except Exception as exc:
                logger.warning("Tavily people search failed: %s", exc)

        system_prompt = (
            "You are a research analyst. Extract information about the company's key people. "
            "Respond with ONLY a valid JSON object:\n"
            '{"key_people": {"founders": "<string describing founders>", "ceo": "<string>", '
            '"directors": "<string listing directors>", "shareholders": "<string listing major shareholders>"}, '
            '"leadership": "<paragraph about leadership team>", '
            '"founders": "<paragraph about founders background>", '
            '"board": "<paragraph about board of directors>"}'
        )

        user_content = f"Company: {ctx['name']}\nIndustry: {ctx['industry']}\nCountry: {ctx['country']}\n"
        if web_context:
            user_content += f"\nWeb search results:\n{web_context}\n"
        user_content += "\nExtract key people information. Return JSON only."

        try:
            result = await self._client._chat(system_prompt, user_content, 0.2)
            return self._client._parse_json(result, default={})
        except Exception as exc:
            logger.warning("People research failed: %s", exc)
            return {}

    async def _research_industry(self, ctx: dict) -> dict:
        """Research the industry: TAM, trends, regulations."""
        try:
            result = await self._client.research_web(
                query=f"{ctx['industry']} industry market size growth rate trends {ctx['country']} Southeast Asia 2025 2026",
                company_context=ctx,
            )
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as exc:
            logger.warning("Industry research failed: %s", exc)
            return {"error": str(exc)}

    async def _research_peers(self, ctx: dict) -> dict:
        """Research comparable companies and competitors."""
        try:
            result = await self._client.research_web(
                query=f"{ctx['industry']} top companies competitors market leaders {ctx['country']} listed companies",
                company_context=ctx,
            )
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as exc:
            logger.warning("Peer research failed: %s", exc)
            return {"error": str(exc)}
