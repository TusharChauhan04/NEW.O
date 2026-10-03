"""
core/llm/claude_client.py — Anthropic Claude LLM Adapter

Phase 1 Update: Replaces Gemini with Claude Sonnet as the live AI provider.

Uses anthropic SDK (official Python client).
Model: claude-3-5-sonnet-20241022 — best balance of reasoning + speed.

Handles:
- Context mapping from DB state → structured prompt
- JSON output parsing with safety fallback
- Error handling — never crashes the recommendation pipeline

ADDITIVE: This file is new. Nothing existing is modified or removed.
          gemini_client.py and openai_client.py remain untouched.
"""

import json
import logging
import anthropic

from app.core.llm.client import BaseLLMClient
from app.core.llm.prompts import get_system_prompt, build_user_prompt
from app.core.integrations.executor import get_registered_actions

logger = logging.getLogger(__name__)


class ClaudeLLMClient(BaseLLMClient):
    """
    Claude Sonnet adapter for NeuralOrbit AI recommendations.

    Implements the same BaseLLMClient interface as MockLLMClient,
    GeminiLLMClient, and OpenAILLMClient — zero changes needed
    anywhere else in the codebase.
    """

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        logger.info(f"[ClaudeClient] Initialized with model={model}")

    async def recommend(self, module: str, context: dict, question: str) -> dict:
        try:
            # 1 — Build prompts
            valid_codes = get_registered_actions(module)
            system_prompt = get_system_prompt(
                module, known_mistakes=context.get("known_mistakes"), valid_action_codes=valid_codes
            )
            user_content  = build_user_prompt(context)

            # 2 — Append JSON instruction to system prompt
            json_instruction = (
                "\n\nCRITICAL: Respond ONLY with a valid JSON object. "
                "No markdown, no code fences, no explanation outside the JSON. "
                "Required fields: recommendation (string), action_code (string or null), "
                "reasoning (string), confidence (float 0.0–1.0), alternatives (array of "
                "objects with action and confidence fields)."
            )

            # 3 — Call Claude (synchronous SDK — wrapped for async compatibility)
            import asyncio
            response = await asyncio.to_thread(
                self.client.messages.create,
                model      = self._model,
                max_tokens = 1024,
                system     = system_prompt + json_instruction,
                messages   = [{"role": "user", "content": user_content}],
            )

            raw_text = response.content[0].text.strip()

            if not raw_text:
                raise ValueError("Claude returned an empty response")

            # 4 — Parse JSON output
            result = json.loads(raw_text)

            # 5 — Standardize and return
            raw_code = result.get("action_code")
            action_code = raw_code if raw_code in valid_codes else None
            return {
                "recommendation": result.get("recommendation", "Continue current strategy"),
                "action_code":    action_code,
                "reasoning":      result.get("reasoning", "No specific reasoning provided."),
                "confidence":     min(float(result.get("confidence", 0.7)), 0.99),
                "alternatives":   result.get("alternatives", []),
                "provider":       "claude",
                "model":          self._model,
            }

        except json.JSONDecodeError as je:
            logger.error(f"[ClaudeClient] JSON parse error: {je} — raw: {raw_text[:200] if 'raw_text' in dir() else 'N/A'}")
            return self._error_response(f"JSON parse failed: {je}")

        except Exception as e:
            logger.error(f"[ClaudeClient] API call failed: {e}")
            return self._error_response(str(e))

    def _error_response(self, reason: str) -> dict:
        """Safe non-crashing fallback when Claude fails."""
        return {
            "recommendation": "Maintain current operations",
            "action_code":    None,
            "reasoning":      f"AI recommendation unavailable: {reason}. Fallback engaged.",
            "confidence":     0.5,
            "alternatives":   [],
            "provider":       "claude-fallback",
            "model":          self._model,
        }
