"""
Google Gemini API client — free tier with web search (Google Search grounding).
Implements the same interface as AnthropicClient/GroqClient.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"


class GeminiClient:
    """Gemini-backed AI client with the same interface as AnthropicClient."""

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or settings.GEMINI_API_KEY
        if not resolved_key:
            raise ValueError("GEMINI_API_KEY must be set.")
        self._client = genai.Client(api_key=resolved_key)
        self._semaphore = asyncio.Semaphore(3)  # 15 RPM free tier, keep some margin

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
        """Research using Gemini with Google Search grounding — real web search for free."""
        system_prompt = (
            "You are a research analyst. Search the web for relevant information "
            "about the company and its industry. Respond with ONLY a valid JSON object:\n"
            '{"industry_overview": "<string>", "market_size": "<string>", '
            '"competitive_landscape": "<string>", "macro_factors": "<string>", '
            '"growth_drivers": "<string>", "risks": "<string>", "sources": ["<url1>", "<url2>"]}'
        )

        user_content = (
            f"Research query: {query}\n\n"
            f"Company context:\n{json.dumps(company_context, indent=2, default=str)}\n\n"
            "Search the web and provide your analysis as JSON. Include source URLs."
        )

        # Use Google Search grounding tool
        result = await self._chat_with_search(system_prompt, user_content)
        return self._parse_json(result, default={"industry_overview": result, "sources": []})

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
        """Stream a chat response. Yields text chunks."""
        # Build contents from messages
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

        async with self._semaphore:
            response = await asyncio.to_thread(
                self._client.models.generate_content_stream,
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    max_output_tokens=4096,
                ),
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _chat(self, system: str, user_content: str, temperature: float) -> str:
        """Simple chat completion — returns text response."""
        for attempt in range(3):
            try:
                async with self._semaphore:
                    response = await asyncio.to_thread(
                        self._client.models.generate_content,
                        model=GEMINI_MODEL,
                        contents=user_content,
                        config=types.GenerateContentConfig(
                            system_instruction=system,
                            temperature=temperature,
                            max_output_tokens=4096,
                        ),
                    )
                    await asyncio.sleep(1)  # Rate limit buffer
                    return response.text or ""
            except Exception as exc:
                if "429" in str(exc) or "RATE_LIMIT" in str(exc) or "quota" in str(exc).lower():
                    wait = 15 * (attempt + 1)
                    logger.warning("Gemini rate limited, waiting %ds (attempt %d/3)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    raise
        return ""

    async def _chat_with_search(self, system: str, user_content: str) -> str:
        """Chat with Google Search grounding enabled."""
        for attempt in range(3):
            try:
                async with self._semaphore:
                    response = await asyncio.to_thread(
                        self._client.models.generate_content,
                        model=GEMINI_MODEL,
                        contents=user_content,
                        config=types.GenerateContentConfig(
                            system_instruction=system,
                            temperature=0.3,
                            max_output_tokens=4096,
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                        ),
                    )
                    await asyncio.sleep(1)
                    return response.text or ""
            except Exception as exc:
                if "429" in str(exc) or "RATE_LIMIT" in str(exc) or "quota" in str(exc).lower():
                    wait = 15 * (attempt + 1)
                    logger.warning("Gemini rate limited (search), waiting %ds", wait)
                    await asyncio.sleep(wait)
                else:
                    raise
        return ""

    @staticmethod
    def _parse_json(text: str, default: dict) -> dict:
        """Extract JSON from a text response."""
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

        logger.warning("Could not parse JSON from Gemini response: %s", text[:200])
        return default
