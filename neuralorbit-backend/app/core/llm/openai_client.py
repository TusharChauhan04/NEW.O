"""
core/llm/openai_client.py — OpenAI GPT-4o Adapter

Phase 4 Milestone 3: Connects NeuralOrbit to OpenAI.
Uses gpt-4o for high-reasoning business strategic recommendations.

Handles:
- Context mapping from DB state → Prompt
- JSON output parsing
- Error handling & retries
"""

import json
import logging
from openai import AsyncOpenAI
from app.core.llm.client import BaseLLMClient
from app.core.llm.prompts import get_system_prompt, build_user_prompt
from app.core.integrations.executor import get_registered_actions

logger = logging.getLogger(__name__)


class OpenAILLMClient(BaseLLMClient):
    def __init__(self, api_key: str, model_name: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_name = model_name

    async def recommend(self, module: str, context: dict, question: str) -> dict:
        try:
            # 1 — Build Prompts
            valid_codes = get_registered_actions(module)
            system_instruction = get_system_prompt(
                module, known_mistakes=context.get("known_mistakes"), valid_action_codes=valid_codes
            )
            user_prompt = build_user_prompt(context)

            # 2 — Call OpenAI
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("OpenAI returned an empty response")

            # 3 — Parse JSON
            result = json.loads(content)

            # 4 — Standardize Response
            raw_code = result.get("action_code")
            action_code = raw_code if raw_code in valid_codes else None
            return {
                "recommendation": result.get("recommendation", "Continue current strategy"),
                "action_code":    action_code,
                "reasoning":      result.get("reasoning", "No specific reasoning provided."),
                "confidence":     float(result.get("confidence", 0.7)),
                "alternatives":   result.get("alternatives", []),
                "provider":       "openai",
                "model":          self.model_name
            }

        except Exception as e:
            logger.error(f"[OpenAIClient] API Error: {e}")
            return {
                "recommendation": "Maintain status quo",
                "action_code":    None,
                "reasoning":      f"AI generation failed due to an API error: {str(e)}",
                "confidence":     0.5,
                "alternatives":   [],
                "provider":       "openai-error"
            }
