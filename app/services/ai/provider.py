"""
AI provider factory — returns the configured AI client (Groq or Anthropic).
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def get_ai_client():
    """Get the configured AI client based on AI_PROVIDER setting.

    Returns GeminiClient, GroqClient, or AnthropicClient — all share the same interface.
    """
    provider = settings.AI_PROVIDER.lower()

    if provider == "gemini":
        from app.services.ai.gemini_client import GeminiClient
        logger.info("Using Gemini AI provider (free + web search)")
        return GeminiClient()
    elif provider == "groq":
        from app.services.ai.groq_client import GroqClient
        logger.info("Using Groq AI provider (free tier)")
        return GroqClient()
    else:
        from app.services.ai.client import AnthropicClient
        logger.info("Using Anthropic AI provider")
        return AnthropicClient()
