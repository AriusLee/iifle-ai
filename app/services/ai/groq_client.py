"""
Groq API client — primary AI provider using Groq's Llama models.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from groq import AsyncGroq

from app.config import settings

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"  # Free, fast, good quality
GROQ_CHAT_MODEL = "llama-3.1-8b-instant"  # Higher rate limits for chat (30K TPM)


class GroqClient:
    """Groq-backed AI client."""

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or settings.GROQ_API_KEY
        if not resolved_key:
            raise ValueError("GROQ_API_KEY must be set.")
        self._client = AsyncGroq(api_key=resolved_key)
        self._semaphore = asyncio.Semaphore(1)  # Groq free tier: 12K TPM, serialize calls

    async def score_dimension(
        self,
        dimension_name: str,
        rubric: str,
        input_data: dict[str, Any],
        few_shot_examples: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Score a dimension — returns {"score": int, "reasoning": str, "sub_scores": dict}."""
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

        result = await self._chat(system_prompt, user_content, temperature=0.1)
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
                "Write in Mandarin Chinese."
                if language == "zh"
                else "Write in both English and Mandarin Chinese, clearly separated."
            )
        )

        system_prompt = (
            "You are a professional financial report writer for IIFLE. "
            "Write clear, concise, and insightful narratives suitable for "
            "investor and board-level audiences. " + lang_instruction
        )

        user_content = (
            f"Write the narrative for report section: {section_name}\n\n"
            f"Context and scoring data:\n{json.dumps(context, indent=2, default=str)}"
        )

        return await self._chat(system_prompt, user_content, temperature=0.4)

    async def research_web(
        self,
        query: str,
        company_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Research — Groq doesn't have web search, so use the model's training knowledge."""
        system_prompt = (
            "You are a research analyst. Based on your knowledge, provide information "
            "about the company and its industry. Respond with ONLY a valid JSON object:\n"
            '{"industry_overview": "<string>", "market_size": "<string>", '
            '"competitive_landscape": "<string>", "macro_factors": "<string>", '
            '"growth_drivers": "<string>", "risks": "<string>"}'
        )

        user_content = (
            f"Research query: {query}\n\n"
            f"Company context:\n{json.dumps(company_context, indent=2, default=str)}\n\n"
            "Provide your analysis as JSON."
        )

        result = await self._chat(system_prompt, user_content, temperature=0.3)
        return self._parse_json(result, default={"industry_overview": result})

    async def extract_structured_data(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Generic structured data extraction — returns parsed JSON."""
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
        """Stream a chat response. Uses smaller model for higher rate limits."""
        async with self._semaphore:
            stream = await self._client.chat.completions.create(
                model=GROQ_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages,
                ],
                temperature=temperature,
                max_tokens=4096,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _chat(self, system: str, user_content: str, temperature: float) -> str:
        """Simple chat completion with rate limit retry."""
        for attempt in range(4):
            try:
                async with self._semaphore:
                    response = await self._client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_content},
                        ],
                        temperature=temperature,
                        max_tokens=4096,
                    )
                    # Small delay between calls to stay under TPM
                    await asyncio.sleep(2)
                    return response.choices[0].message.content or ""
            except Exception as exc:
                if "429" in str(exc) or "rate_limit" in str(exc):
                    wait = 20 * (attempt + 1)
                    logger.warning("Groq rate limited, waiting %ds (attempt %d/4)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    raise
        return ""

    @staticmethod
    def _parse_json(text: str, default: dict) -> dict:
        """Extract JSON from a text response (handles markdown code blocks)."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ``` blocks
        if "```" in text:
            try:
                start = text.index("```") + 3
                if text[start:start + 4] == "json":
                    start += 4
                end = text.index("```", start)
                return json.loads(text[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                pass

        # Try finding first { ... } block
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            pass

        logger.warning("Could not parse JSON from response: %s", text[:200])
        return default
