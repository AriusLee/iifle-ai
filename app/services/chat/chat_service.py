"""
ChatService — the main chat orchestrator that manages conversations,
streams Groq responses, and persists messages.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatConversation, ChatMessage, ContextType, MessageRole
from app.services.ai.provider import get_ai_client
from app.services.chat.context_builder import build_chat_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """You are the IIFLE AI Co-Pilot, an expert assistant for the IIFLE capital structure advisory platform based in Malaysia. Your role is to help analysts, consultants, and advisors analyze companies that are preparing for capital market activities (IPO, fundraising, restructuring, etc.).

You have access to the following company data and tools:

{context}

## Your Capabilities
- Answer questions about the company's assessment scores, intake data, and report content.
- Edit report sections when asked — use the edit_report_section tool.
- Look up specific company data — use the get_company_data tool.
- Search the web for industry or market information — use the search_web tool.

## Guidelines
- Be precise and data-driven. Reference specific scores, dimensions, and data points.
- When discussing scores, explain what the numbers mean in context of capital readiness.
- If the user asks to change a report section, use the edit_report_section tool.
- If you need data not in your context, use get_company_data or search_web.
- Always be professional and concise. This is a financial advisory context.
- Support bilingual responses (English and Chinese) when asked.
- If you don't have enough information to answer, say so clearly.
"""



class ChatService:
    """Orchestrates AI chat conversations with tool_use streaming."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = get_ai_client()

    # ------------------------------------------------------------------
    # Conversation management
    # ------------------------------------------------------------------

    async def create_conversation(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> ChatConversation:
        """Create a new chat conversation for a company."""
        conversation = ChatConversation(
            id=uuid.uuid4(),
            company_id=company_id,
            user_id=user_id,
            title=title or "New conversation",
            context_type=ContextType.general,
            is_active=True,
        )
        self._db.add(conversation)
        await self._db.flush()
        return conversation

    async def get_conversation_history(
        self,
        conversation_id: uuid.UUID,
    ) -> list[ChatMessage]:
        """Retrieve all messages in a conversation, ordered chronologically."""
        result = await self._db.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_conversations(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[ChatConversation]:
        """List all conversations for a company/user, newest first."""
        result = await self._db.execute(
            select(ChatConversation)
            .where(
                ChatConversation.company_id == company_id,
                ChatConversation.user_id == user_id,
            )
            .order_by(ChatConversation.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Send message (streaming with tool_use)
    # ------------------------------------------------------------------

    async def send_message(
        self,
        conversation_id: uuid.UUID,
        user_message: str,
        company_id: uuid.UUID,
    ) -> AsyncGenerator[str, None]:
        """Send a user message, stream Claude's response token by token.

        Handles tool calls in the loop: when Claude wants to use a tool,
        we execute it, feed the result back, and continue streaming.

        Yields text deltas as they arrive.
        """
        # 1. Persist the user message
        user_msg = ChatMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.user,
            content=user_message,
            metadata_={},
        )
        self._db.add(user_msg)
        await self._db.flush()

        # 2. Build system prompt with company context
        context_str = await build_chat_context(self._db, company_id)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context_str)

        # 3. Load conversation history for Claude messages list
        history = await self.get_conversation_history(conversation_id)
        messages = self._build_messages(history)

        # 4. Stream response via Groq
        full_response_text = ""

        async for chunk in self._client.stream_chat(system_prompt, messages):
            full_response_text += chunk
            yield chunk

        # 5. Persist the full assistant response
        assistant_msg = ChatMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.assistant,
            content=full_response_text,
            metadata_={},
        )
        self._db.add(assistant_msg)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # Token budget: ~3K for system prompt, ~1K for company context, ~4K for response
    # Leaves ~12K for conversation history on Haiku (200K context but we want to stay cheap)
    MAX_HISTORY_CHARS = 40_000  # ~10K tokens
    RECENT_MESSAGES_KEEP = 6    # Always keep the last 6 messages verbatim

    def _build_messages(self, history: list[ChatMessage]) -> list[dict[str, Any]]:
        """Convert DB message history to Claude-compatible messages, with compression.

        Strategy:
        - Always include the last RECENT_MESSAGES_KEEP messages in full
        - If older messages exist and total chars exceed MAX_HISTORY_CHARS,
          summarize the older portion into a single condensed message
        - This keeps the conversation coherent without blowing up token usage
        """
        # Filter to user/assistant only
        relevant = [
            m for m in history
            if m.role in (MessageRole.user, MessageRole.assistant)
        ]

        if not relevant:
            return []

        # Split into old and recent
        if len(relevant) <= self.RECENT_MESSAGES_KEEP:
            # Short conversation — return everything
            return [
                {"role": "user" if m.role == MessageRole.user else "assistant", "content": m.content}
                for m in relevant
            ]

        old_messages = relevant[:-self.RECENT_MESSAGES_KEEP]
        recent_messages = relevant[-self.RECENT_MESSAGES_KEEP:]

        # Check if old messages are too large
        old_chars = sum(len(m.content) for m in old_messages)
        recent_chars = sum(len(m.content) for m in recent_messages)

        messages: list[dict[str, Any]] = []

        if old_chars + recent_chars > self.MAX_HISTORY_CHARS:
            # Compress old messages into a summary
            summary = self._compress_old_messages(old_messages)
            messages.append({
                "role": "user",
                "content": f"[Previous conversation summary: {summary}]",
            })
            messages.append({
                "role": "assistant",
                "content": "Understood, I have the context from our earlier conversation.",
            })
        else:
            # Old messages fit — include them all
            for m in old_messages:
                messages.append({
                    "role": "user" if m.role == MessageRole.user else "assistant",
                    "content": m.content,
                })

        # Always include recent messages in full
        for m in recent_messages:
            messages.append({
                "role": "user" if m.role == MessageRole.user else "assistant",
                "content": m.content,
            })

        return messages

    @staticmethod
    def _compress_old_messages(messages: list[ChatMessage]) -> str:
        """Create a concise summary of older messages to preserve context."""
        # Extract key topics and decisions from the conversation
        user_points = []
        assistant_points = []

        for m in messages:
            # Take the first 150 chars of each message as a digest
            snippet = m.content[:150].replace("\n", " ").strip()
            if len(m.content) > 150:
                snippet += "..."

            if m.role == MessageRole.user:
                user_points.append(snippet)
            else:
                assistant_points.append(snippet)

        # Build a compact summary
        parts = []
        if user_points:
            # Keep at most 8 user points
            points = user_points[-8:] if len(user_points) > 8 else user_points
            parts.append("User discussed: " + " | ".join(points))
        if assistant_points:
            points = assistant_points[-8:] if len(assistant_points) > 8 else assistant_points
            parts.append("Assistant covered: " + " | ".join(points))

        return " ".join(parts) if parts else "General discussion about the company."
