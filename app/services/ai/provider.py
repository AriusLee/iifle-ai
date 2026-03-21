"""
AI provider factory — returns the Groq AI client.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_ai_client():
    """Get the Groq AI client."""
    from app.services.ai.groq_client import GroqClient
    logger.info("Using Groq AI provider (free tier)")
    return GroqClient()
