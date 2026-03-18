"""
ChatService — the main chat orchestrator that manages conversations,
streams Claude responses with tool_use, and persists messages.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatConversation, ChatMessage, ContextType, MessageRole
from app.services.ai.client import AnthropicClient, DEFAULT_MODEL
from app.services.chat.context_builder import build_chat_context
from app.services.chat.tools import CHAT_TOOLS, execute_tool

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

MAX_TOOL_ITERATIONS = 8


class ChatService:
    """Orchestrates AI chat conversations with tool_use streaming."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = AnthropicClient()

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

        # 4. Stream with tool-use loop
        full_response_text = ""
        tool_calls_metadata: list[dict[str, Any]] = []

        for iteration in range(MAX_TOOL_ITERATIONS):
            # Stream the response
            collected_text = ""
            tool_use_blocks: list[dict[str, Any]] = []
            current_tool_use: dict[str, Any] | None = None
            current_tool_json = ""

            async with self._client._client.messages.stream(
                model=DEFAULT_MODEL,
                system=system_prompt,
                messages=messages,
                tools=CHAT_TOOLS,
                max_tokens=4096,
                temperature=0.3,
            ) as stream:
                async for event in stream:
                    # Handle different event types from the streaming API
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            current_tool_use = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {},
                            }
                            current_tool_json = ""
                        elif event.content_block.type == "text":
                            pass  # text blocks start empty

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            collected_text += event.delta.text
                            yield event.delta.text
                        elif event.delta.type == "input_json_delta":
                            if current_tool_use is not None:
                                current_tool_json += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool_use is not None:
                            # Parse accumulated JSON
                            try:
                                current_tool_use["input"] = json.loads(current_tool_json) if current_tool_json else {}
                            except json.JSONDecodeError:
                                current_tool_use["input"] = {}
                            tool_use_blocks.append(current_tool_use)
                            current_tool_use = None
                            current_tool_json = ""

            full_response_text += collected_text

            # If no tool calls, we're done
            if not tool_use_blocks:
                break

            # Build the assistant message content (text + tool_use blocks)
            assistant_content: list[dict[str, Any]] = []
            if collected_text:
                assistant_content.append({"type": "text", "text": collected_text})
            for tu in tool_use_blocks:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tu["id"],
                    "name": tu["name"],
                    "input": tu["input"],
                })

            messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and build tool results
            tool_results: list[dict[str, Any]] = []
            for tu in tool_use_blocks:
                tool_calls_metadata.append({
                    "tool": tu["name"],
                    "input": tu["input"],
                })

                result_str = await execute_tool(
                    tu["name"], tu["input"], self._db, company_id
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result_str,
                })

                tool_calls_metadata[-1]["result_preview"] = result_str[:200]

            messages.append({"role": "user", "content": tool_results})

            # Signal to the frontend that tool processing happened
            yield f"\n"

        # 5. Persist the full assistant response
        assistant_msg = ChatMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=MessageRole.assistant,
            content=full_response_text,
            metadata_={"tool_calls": tool_calls_metadata} if tool_calls_metadata else {},
        )
        self._db.add(assistant_msg)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(history: list[ChatMessage]) -> list[dict[str, Any]]:
        """Convert DB message history to Claude-compatible messages format.

        Skips system messages and tool call/result messages (those are handled
        within a single request turn). Keeps the last N messages to avoid
        exceeding context limits.
        """
        MAX_HISTORY_MESSAGES = 50
        messages: list[dict[str, Any]] = []

        # Only include user and assistant messages for conversation context
        for msg in history[-MAX_HISTORY_MESSAGES:]:
            if msg.role == MessageRole.user:
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.assistant:
                messages.append({"role": "assistant", "content": msg.content})

        return messages
