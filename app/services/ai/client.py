"""
Anthropic Claude API wrapper with retry logic, rate limiting, and structured output.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
MAX_CONCURRENT_CALLS = 5

# ---------------------------------------------------------------------------
# Tool definitions for structured output
# ---------------------------------------------------------------------------
SCORING_TOOL = {
    "name": "record_score",
    "description": (
        "Record a structured scoring result for a dimension. "
        "The score must be an integer 0-100. sub_scores is an optional "
        "dict mapping sub-factor names to their individual integer scores."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Overall dimension score from 0 to 100.",
            },
            "reasoning": {
                "type": "string",
                "description": "Detailed reasoning explaining how the score was derived, referencing specific rubric criteria.",
            },
            "sub_scores": {
                "type": "object",
                "description": "Optional mapping of sub-factor names to their individual scores (0-100).",
                "additionalProperties": {"type": "integer", "minimum": 0, "maximum": 100},
            },
        },
        "required": ["score", "reasoning"],
    },
}

RESEARCH_TOOL = {
    "name": "record_research",
    "description": "Record structured research findings.",
    "input_schema": {
        "type": "object",
        "properties": {
            "industry_overview": {
                "type": "string",
                "description": "Summary of the industry landscape.",
            },
            "market_size": {
                "type": "string",
                "description": "Estimated TAM / SAM / SOM if available.",
            },
            "competitive_landscape": {
                "type": "string",
                "description": "Key competitors and positioning.",
            },
            "macro_factors": {
                "type": "string",
                "description": "PESTEL-relevant macro-economic factors.",
            },
            "growth_drivers": {
                "type": "string",
                "description": "Key growth drivers and tailwinds.",
            },
            "risks": {
                "type": "string",
                "description": "Key risks and headwinds.",
            },
        },
        "required": ["industry_overview"],
    },
}


class AnthropicClient:
    """Async wrapper around the Anthropic SDK with retry, rate-limiting, and structured output."""

    def __init__(self, api_key: str | None = None) -> None:
        resolved_key = api_key or settings.ANTHROPIC_API_KEY
        if not resolved_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment or passed explicitly."
            )
        self._client = anthropic.AsyncAnthropic(api_key=resolved_key)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def score_dimension(
        self,
        dimension_name: str,
        rubric: str,
        input_data: dict[str, Any],
        few_shot_examples: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Score a single dimension using tool_use for structured output.

        Returns ``{"score": int, "reasoning": str, "sub_scores": dict | None}``.
        """
        system_prompt = (
            "You are an expert capital-market analyst for IIFLE, a Malaysian "
            "capital structure advisory platform. You evaluate companies on specific "
            "dimensions using defined rubrics. Always be precise, fair, and reference "
            "specific rubric criteria in your reasoning. Return your assessment by "
            "calling the record_score tool."
        )

        user_content = self._build_scoring_prompt(
            dimension_name, rubric, input_data, few_shot_examples
        )

        response = await self._call_with_retry(
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            tools=[SCORING_TOOL],
            tool_choice={"type": "tool", "name": "record_score"},
            temperature=0.1,
            max_tokens=2048,
        )

        return self._extract_tool_input(response, "record_score")

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
                else "Write the response in both English and Mandarin Chinese (中文), clearly separated with headers."
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

        response = await self._call_with_retry(
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            tools=None,
            tool_choice=None,
            temperature=0.4,
            max_tokens=4096,
        )

        return self._extract_text(response)

    async def research_web(
        self,
        query: str,
        company_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Use Claude's built-in web_search tool to research a company/industry.

        Returns structured research findings.
        """
        system_prompt = (
            "You are a research analyst. Search the web for relevant information "
            "about the company and its industry. Summarise your findings by calling "
            "the record_research tool."
        )

        user_content = (
            f"Research query: {query}\n\n"
            f"Company context:\n{json.dumps(company_context, indent=2, default=str)}\n\n"
            "Search the web for the latest industry data, competitive landscape, "
            "and macro factors. Then call record_research with your findings."
        )

        # Combine web_search (built-in) and our record_research tool
        response = await self._call_with_retry(
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
            tools=[
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 5},
                RESEARCH_TOOL,
            ],
            tool_choice={"type": "any"},
            temperature=0.3,
            max_tokens=4096,
        )

        # The model may do multiple turns (search, then record).
        # We accumulate messages until we get our record_research call.
        return await self._run_tool_loop(response, "record_research", system_prompt)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_with_retry(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice: dict | None,
        temperature: float,
        max_tokens: int,
    ) -> anthropic.types.Message:
        """Call the API with exponential-backoff retry and semaphore-based rate limiting."""
        backoff = INITIAL_BACKOFF_SECONDS
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with self._semaphore:
                    kwargs: dict[str, Any] = {
                        "model": DEFAULT_MODEL,
                        "system": system,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if tools:
                        kwargs["tools"] = tools
                    if tool_choice:
                        kwargs["tool_choice"] = tool_choice

                    return await self._client.messages.create(**kwargs)

            except anthropic.RateLimitError as exc:
                last_error = exc
                logger.warning(
                    "Rate limited (attempt %d/%d). Retrying in %.1fs ...",
                    attempt,
                    MAX_RETRIES,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff *= 2

            except anthropic.APIStatusError as exc:
                last_error = exc
                if exc.status_code >= 500:
                    logger.warning(
                        "Server error %d (attempt %d/%d). Retrying in %.1fs ...",
                        exc.status_code,
                        attempt,
                        MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    raise

            except anthropic.APIConnectionError as exc:
                last_error = exc
                logger.warning(
                    "Connection error (attempt %d/%d). Retrying in %.1fs ...",
                    attempt,
                    MAX_RETRIES,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff *= 2

        raise RuntimeError(
            f"Anthropic API call failed after {MAX_RETRIES} retries"
        ) from last_error

    async def _run_tool_loop(
        self,
        initial_response: anthropic.types.Message,
        target_tool: str,
        system_prompt: str,
    ) -> dict[str, Any]:
        """Handle multi-turn tool-use conversations until `target_tool` is called."""
        messages: list[dict] = [
            {"role": "user", "content": "Please proceed with the research."},
        ]
        response = initial_response
        max_iterations = 10

        for _ in range(max_iterations):
            # Check if target tool was called
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and block.name == target_tool:
                    return block.input  # type: ignore[return-value]

            # If the model used web_search, we need to let the SDK handle it
            # and continue the conversation.
            tool_results = []
            has_tool_use = False
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    has_tool_use = True
                    if block.name != target_tool:
                        # For web_search, the SDK handles it internally
                        # For other tools, acknowledge with a placeholder
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "OK — results received. Now call record_research with your findings.",
                            }
                        )

            if not has_tool_use:
                # Model finished without calling our tool — return empty
                logger.warning("Model did not call %s — returning empty result.", target_tool)
                return {"industry_overview": "Research could not be completed."}

            # Build assistant message from response content
            assistant_content = []
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif getattr(block, "type", None) == "tool_use":
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

            response = await self._call_with_retry(
                system=system_prompt,
                messages=messages,
                tools=[
                    {"type": "web_search_20250305", "name": "web_search", "max_uses": 3},
                    RESEARCH_TOOL,
                ],
                tool_choice={"type": "any"},
                temperature=0.3,
                max_tokens=4096,
            )

        logger.warning("Tool loop exhausted without %s call.", target_tool)
        return {"industry_overview": "Research timed out."}

    @staticmethod
    def _build_scoring_prompt(
        dimension_name: str,
        rubric: str,
        input_data: dict[str, Any],
        few_shot_examples: list[dict[str, Any]] | None = None,
    ) -> str:
        parts = [
            f"## Dimension: {dimension_name}\n",
            "## Scoring Rubric\n",
            rubric,
            "\n## Company Data to Evaluate\n",
            json.dumps(input_data, indent=2, default=str),
        ]
        if few_shot_examples:
            parts.append("\n## Calibration Examples\n")
            for ex in few_shot_examples:
                parts.append(json.dumps(ex, indent=2, default=str))
                parts.append("")

        parts.append(
            "\n## Instructions\n"
            "1. Evaluate the company data against EACH criterion in the rubric.\n"
            "2. Determine which score band the company falls into.\n"
            "3. Assign a precise score within that band based on strength of evidence.\n"
            "4. If sub-factors are defined, score each one individually and provide in sub_scores.\n"
            "5. Call the record_score tool with your result.\n"
            "6. If data is missing for a sub-factor, note it in reasoning and default to a conservative score.\n"
        )
        return "\n".join(parts)

    @staticmethod
    def _extract_tool_input(response: anthropic.types.Message, tool_name: str) -> dict[str, Any]:
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                result = dict(block.input)  # type: ignore[arg-type]
                # Ensure score is clamped 0-100
                if "score" in result:
                    result["score"] = max(0, min(100, int(result["score"])))
                return result
        raise RuntimeError(
            f"Expected tool_use block for '{tool_name}' not found in response."
        )

    @staticmethod
    def _extract_text(response: anthropic.types.Message) -> str:
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts)
