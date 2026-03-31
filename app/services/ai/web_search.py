"""
Web search service using Tavily API.
Provides real-time company and industry research for AI analysis.
"""

from __future__ import annotations

import logging
from typing import Any

from tavily import AsyncTavilyClient

from app.config import settings

logger = logging.getLogger(__name__)


class WebSearchService:
    """Tavily-backed web search for company/industry research."""

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or settings.TAVILY_API_KEY
        if not resolved_key:
            raise ValueError("TAVILY_API_KEY must be set for web search.")
        self._client = AsyncTavilyClient(api_key=resolved_key)

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Run a basic search and return results."""
        try:
            response = await self._client.search(
                query=query,
                max_results=max_results,
                search_depth="basic",
                include_answer=True,
            )
            results = []
            for r in response.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                })
            return results
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)
            return []

    async def research_company(self, company_name: str, industry: str = "") -> dict[str, Any]:
        """Research a company — searches for company info, industry, and competitors."""
        queries = [
            f"{company_name} company profile business overview",
            f"{industry or company_name} industry market size trends Malaysia Southeast Asia",
        ]

        all_results: list[dict[str, str]] = []
        for q in queries:
            results = await self.search(q, max_results=3)
            all_results.extend(results)

        # Build a research context from search results
        context_parts = []
        sources = []
        for r in all_results:
            if r["content"]:
                context_parts.append(f"### {r['title']}\n{r['content']}")
                sources.append({"title": r["title"], "url": r["url"]})

        return {
            "search_context": "\n\n".join(context_parts) if context_parts else "No search results found.",
            "sources": sources,
            "query_count": len(queries),
            "result_count": len(all_results),
        }

    async def research_industry(self, industry: str, country: str = "Malaysia") -> dict[str, Any]:
        """Research an industry — market size, trends, competitors."""
        queries = [
            f"{industry} industry market size growth {country} 2025 2026",
            f"{industry} top companies competitors {country}",
            f"{industry} industry trends challenges opportunities {country}",
        ]

        all_results: list[dict[str, str]] = []
        for q in queries:
            results = await self.search(q, max_results=3)
            all_results.extend(results)

        context_parts = []
        sources = []
        for r in all_results:
            if r["content"]:
                context_parts.append(f"### {r['title']}\n{r['content']}")
                sources.append({"title": r["title"], "url": r["url"]})

        return {
            "search_context": "\n\n".join(context_parts) if context_parts else "No search results found.",
            "sources": sources,
            "query_count": len(queries),
            "result_count": len(all_results),
        }


def get_web_search() -> WebSearchService | None:
    """Get web search service if Tavily is configured, else None."""
    if not settings.TAVILY_API_KEY:
        return None
    try:
        return WebSearchService()
    except Exception:
        return None
