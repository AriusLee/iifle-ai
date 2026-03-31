"""
AI provider factory — returns the configured AI client.

Supported providers:
  - groq: Free tier, uses Qwen3-32B (excellent Chinese/English)
  - deepseek: Production, DeepSeek V3 API (cheap, no rate limits, best Chinese)
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def get_ai_client():
    """Get the configured AI client based on AI_PROVIDER setting."""
    provider = settings.AI_PROVIDER.lower()

    if provider == "deepseek":
        from app.services.ai.deepseek_client import DeepSeekClient
        logger.info("Using DeepSeek AI provider")
        return DeepSeekClient()

    # Default: Groq (free tier with Qwen3-32B)
    from app.services.ai.groq_client import GroqClient
    logger.info("Using Groq AI provider (Qwen3-32B)")
    return GroqClient()
