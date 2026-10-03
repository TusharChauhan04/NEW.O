"""
core/llm/gemini_client.py — Google Gemini LLM Adapter

Phase 4 Milestone 3: Connects NeuralOrbit to Google's Gemini 2.0 Flash.

Uses google-generativeai SDK (pinned for Supabase compatibility).
NOTE: google-genai (new SDK) requires httpx>=0.28 which conflicts with
supabase<0.26 requirement — staying on google-generativeai until Supabase
upgrades its httpx pin.

Handles:
- Context mapping from DB state → structured prompt
- JSON output parsing with safety fallback
- Error handling — never crashes the recommendation pipeline
"""

import json
import logging
import warnings

# Suppress the FutureWarning from google.generativeai until Supabase
# upgrades httpx so we can switch to the new google.genai SDK cleanly.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from app.core.llm.client import BaseLLMClient
from app.core.llm.prompts import get_system_prompt, build_user_prompt
from app.core.integrations.executor import get_registered_actions

logger = logging.getLogger(__name__)


class GeminiLLMClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        genai.configure(api_key=api_key)
        # Store the raw model name string for the response metadata
        self._model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        logger.info(f"[GeminiClient] Initialized with model={model_name}")

    async def recommend(self, module: str, context: dict, question: str) -> dict:
        try:
            # 1 — Build the full prompt
            valid_codes = get_registered_actions(module)
            system_instruction = get_system_prompt(
                module, known_mistakes=context.get("known_mistakes"), valid_action_codes=valid_codes
            )
            user_prompt = build_user_prompt(context)
            full_prompt = f"{system_instruction}\n\nUSER DATA:\n{user_prompt}"

            # 2 — Call Gemini (async)
            response = await self.model.generate_content_async(full_prompt)

            if not response.text:
                raise ValueError("Gemini returned an empty response body")

            # 3 — Parse JSON output
            result = json.loads(response.text)

            # 4 — Standardize and return
            raw_code = result.get("action_code")
            action_code = raw_code if raw_code in valid_codes else None
            return {
                "recommendation": result.get("recommendation", "Continue current strategy"),
                "action_code":    action_code,
                "reasoning":      result.get("reasoning", "No specific reasoning provided."),
                "confidence":     min(float(result.get("confidence", 0.7)), 0.99),
                "alternatives":   result.get("alternatives", []),
                "provider":       "gemini",
                "model":          self._model_name,
            }

        except json.JSONDecodeError as je:
            logger.error(f"[GeminiClient] JSON parse error: {je} — raw: {response.text[:200]}")
            return self._error_response(f"JSON parse failed: {je}")

        except Exception as e:
            logger.error(f"[GeminiClient] API call failed: {e}")
            return self._error_response(str(e))

    def _error_response(self, reason: str) -> dict:
        """Returns a safe, non-crashing fallback when Gemini fails."""
        return {
            "recommendation": "Maintain current operations",
            "action_code":    None,
            "reasoning":      f"AI recommendation unavailable: {reason}. Fallback engaged.",
            "confidence":     0.5,
            "alternatives":   [],
            "provider":       "gemini-fallback",
            "model":          self._model_name,
        }
