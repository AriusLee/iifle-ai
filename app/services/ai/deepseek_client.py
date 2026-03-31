"""
DeepSeek API client — production AI provider with excellent Chinese quality.
Uses OpenAI-compatible API format. No rate limits.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

DEEPSEEK_MODEL = "deepseek-chat"  # V3 — fast, general purpose
DEEPSEEK_REASONER = "deepseek-reasoner"  # V3 thinking mode — better for analysis


class DeepSeekClient:
    """DeepSeek-backed AI client using OpenAI-compatible API."""

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or settings.DEEPSEEK_API_KEY
        if not resolved_key:
            raise ValueError("DEEPSEEK_API_KEY must be set.")
        self._client = AsyncOpenAI(
            api_key=resolved_key,
            base_url="https://api.deepseek.com",
        )
        # No semaphore needed — DeepSeek has no rate limits

    async def score_dimension(
        self,
        dimension_name: str,
        rubric: str,
        input_data: dict[str, Any],
        few_shot_examples: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Score a dimension using reasoning model for better analysis."""
        system_prompt = (
            "You are an expert capital-market analyst for IIFLE, a Malaysian "
            "capital structure advisory platform. You evaluate companies on specific "
            "dimensions using defined rubrics. Always be precise, fair, and reference "
            "specific rubric criteria in your reasoning.\n\n"
            "You MUST respond with ONLY a valid JSON object in this exact format:\n"
            '{"score": <integer 0-100>, "reasoning": "<string>", "sub_scores": {<optional key:int pairs>}}'
        )

        user_content = (
            f"## Dimension: {dimension_name}\n\n"
            f"## Scoring Rubric:\n{rubric}\n\n"
            f"## Company Input Data:\n{json.dumps(input_data, indent=2, default=str)}\n\n"
        )
        if few_shot_examples:
            user_content += f"## Calibration Examples:\n{json.dumps(few_shot_examples, indent=2, default=str)}\n\n"
        user_content += "Score this dimension. Return ONLY valid JSON."

        # Use reasoner for scoring — better analytical depth
        result = await self._chat(system_prompt, user_content, temperature=0.1, model=DEEPSEEK_REASONER)
        return self._parse_json(result, default={"score": 50, "reasoning": "Could not parse response", "sub_scores": {}})

    async def generate_narrative(
        self,
        section_name: str,
        context: dict[str, Any],
        language: str = "en",
    ) -> str:
        """Generate narrative text for a report section."""
        lang_instruction = (
            "Write in English."
            if language == "en"
            else (
                "Write in Mandarin Chinese (简体中文)."
                if language == "zh"
                else "Write in both Mandarin Chinese (简体中文) and English, clearly separated with ## 中文 and ## English headers."
            )
        )

        system_prompt = (
            "You are a professional financial report writer for IIFLE, "
            "a capital structure advisory platform based in Malaysia. "
            "Write clear, concise, and insightful narratives suitable for "
            "investor and board-level audiences. " + lang_instruction
        )

        user_content = (
            f"Write the narrative for report section: {section_name}\n\n"
            f"Context and scoring data:\n{json.dumps(context, indent=2, default=str)}"
        )

        # Use chat model for narratives — faster
        return await self._chat(system_prompt, user_content, temperature=0.4, model=DEEPSEEK_MODEL)

    async def research_web(
        self,
        query: str,
        company_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Research using Tavily web search + AI analysis."""
        from app.services.ai.web_search import get_web_search

        web_context = ""
        sources = []
        web_search = get_web_search()
        if web_search:
            try:
                company_name = company_context.get("legal_name", company_context.get("company_name", ""))
                industry = company_context.get("primary_industry", "")
                research = await web_search.research_company(company_name, industry)
                web_context = research.get("search_context", "")
                sources = research.get("sources", [])
            except Exception as exc:
                logger.warning("Tavily research failed: %s", exc)

        system_prompt = (
            "You are a research analyst. Analyze the provided web search results and your own knowledge "
            "to produce a comprehensive company/industry analysis. Respond with ONLY a valid JSON object:\n"
            '{"industry_overview": "<string>", "market_size": "<string>", '
            '"competitive_landscape": "<string>", "macro_factors": "<string>", '
            '"growth_drivers": "<string>", "risks": "<string>"}'
        )

        user_content = f"Research query: {query}\n\n"
        if web_context:
            user_content += f"## Web Search Results:\n{web_context}\n\n"
        user_content += (
            f"## Company Context:\n{json.dumps(company_context, indent=2, default=str)}\n\n"
            "Synthesize the web search results with your knowledge. Provide your analysis as JSON."
        )

        result = await self._chat(system_prompt, user_content, temperature=0.3)
        parsed = self._parse_json(result, default={"industry_overview": result})
        if sources:
            parsed["_sources"] = sources
        return parsed

    async def extract_structured_data(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Generic structured data extraction."""
        result = await self._chat(system_prompt, user_content, temperature=temperature)
        return self._parse_json(result, default={})

    # ------------------------------------------------------------------
    # Streaming for chat
    # ------------------------------------------------------------------

    async def stream_chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
    ):
        """Stream a chat response."""
        stream = await self._client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            temperature=temperature,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _chat(
        self,
        system: str,
        user_content: str,
        temperature: float,
        model: str = DEEPSEEK_MODEL,
    ) -> str:
        """Chat completion — no rate limit handling needed."""
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("DeepSeek API error: %s", exc)
            raise

    @staticmethod
    def _parse_json(text: str, default: dict) -> dict:
        """Extract JSON from a text response (handles markdown code blocks)."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```" in text:
            try:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                return json.loads(text[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass

        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            pass

        logger.warning("Could not parse JSON from response: %s", text[:200])
        return default
