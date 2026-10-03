"""
core/llm/client.py — LLM Client Abstraction

Phase 1: MockLLMClient — structured responses, no API key needed.
Phase 3: Swap MockLLMClient for OpenAILLMClient with one config change.

Design: adapter pattern so the rest of the codebase never changes.
"""

import random
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    @abstractmethod
    async def recommend(self, module: str, context: dict, question: str) -> dict:
        pass


class MockLLMClient(BaseLLMClient):
    """
    Phase 1 Mock LLM — returns realistic, module-specific recommendations.
    Based on the AI Learning objectives in your Reward Frameworks doc:
    - CRM: best follow-up timing, best channel per industry, best rep assignment
    - Marketing: which creatives work, which audience converts, when to pause/scale
    - Shield: normal vs abnormal behavior, risk scoring, adaptive protection
    """

    # Third element is action_code — the n8n action this insight maps to
    # (see executor.py's N8N_WEBHOOKS), or None when the insight is advisory
    # only and has no matching automatable action.
    _MODULE_INSIGHTS: dict[str, list[tuple[str, str, str | None]]] = {
        "crm": [
            (
                "Follow up with leads that opened your email but didn't reply within 48h",
                "Reply cadence analysis shows the 48h window has a 34% higher conversion rate vs 7-day waiters",
                "send_followup",
            ),
            (
                "Prioritize leads in the SaaS industry — conversion rate is 2.1× higher",
                "12-week industry breakdown shows SaaS leads close at 34.2% vs 16.1% overall average",
                "assign_lead",
            ),
            (
                "Assign high-value leads (>$20K) to senior reps only",
                "Decision log shows senior reps close $20K+ deals at 41% vs 18% for junior reps",
                "assign_lead",
            ),
            (
                "Avoid Friday afternoon follow-ups — 22% lower meeting acceptance",
                "Meeting booking data across 847 touchpoints confirms this timing pattern",
                None,
            ),
        ],
        "marketing": [
            (
                "Reallocate 20% of budget from underperforming ad sets to top 2 performers",
                "Top 2 ad sets show 4.2× ROAS vs 1.8× average — marginal returns justify reallocation",
                "adjust_budget",
            ),
            (
                "Tuesday 9AM sends are outperforming other slots by 12% open rate",
                "A/B test data across 14 active campaigns confirms this send-time pattern",
                None,
            ),
            (
                "Pause campaigns with CPA > $28 — they are pulling down overall efficiency",
                "Budget waste events spiked 40% on campaigns exceeding this threshold",
                "pause_campaign",
            ),
            (
                "Creative fatigue detected on Campaign #7 — swap visual assets",
                "CTR dropped 31% over last 14 days; ad fatigue event rate increasing",
                "pause_ad",
            ),
        ],
        "shield": [
            (
                "Flag user account #4471 — login pattern deviates 3.2σ from their baseline",
                "IP geolocation + login hours analysis shows abnormal behavior signature",
                "send_alert",
            ),
            (
                "Increase monitoring sensitivity during 11PM–4AM window",
                "85% of breach events in the historical dataset occurred in this time window",
                None,
            ),
            (
                "False positive rate elevated on Rule #12 — consider adjusting threshold",
                "Rule #12 triggered 43 false positives this week vs 8 actual threats",
                None,
            ),
        ],
        "website": [
            (
                "Reduce pricing page options from 7 to 3 — decision fatigue is causing drop-off",
                "Hick's Law + bounce rate correlation shows 31% drop-off increase with 7+ options",
                "notify_team",
            ),
            (
                "Add social proof (testimonials/logos) directly above the CTA button",
                "Heatmap data shows users scroll past CTA without converting — trust gap detected",
                "notify_team",
            ),
            (
                "Mobile checkout flow has 3 redundant steps — streamline to improve conversion",
                "Session recordings show 67% of mobile users abandon at step 4 of 6",
                "notify_team",
            ),
        ],
        "neural-orbit": [
            (
                "CRM module is your strongest performer this week — allocate more AI cycles",
                "CRM cumulative reward: +142 vs Marketing: +87 — highest ROI module",
                None,
            ),
            (
                "AI decision confidence improved 4.1% this week across all modules",
                "Based on 1,847 data points analyzed — system is learning effectively",
                None,
            ),
            (
                "Shield module needs attention — false positive rate above recommended threshold",
                "15 false positive events logged this week; recommend reviewing detection rules",
                None,
            ),
        ],
    }

    async def recommend(self, module: str, context: dict, question: str) -> dict:
        insights = self._MODULE_INSIGHTS.get(
            module, self._MODULE_INSIGHTS["neural-orbit"]
        )
        recommendation, reasoning, action_code = random.choice(insights)

        # Adjust confidence slightly based on how many events we have
        event_count = len(context.get("recent_events", []))
        base_confidence = 0.65 + min(event_count * 0.03, 0.28)
        confidence = round(random.uniform(base_confidence - 0.05, base_confidence + 0.05), 2)

        logger.info(f"[MockLLM] Recommendation for module={module} confidence={confidence}")

        return {
            "recommendation": recommendation,
            "action_code": action_code,
            "reasoning": reasoning,
            "confidence": min(confidence, 0.97),
            "alternatives": [
                {
                    "action": "Continue current strategy and collect more data",
                    "confidence": round(random.uniform(0.30, 0.55), 2),
                },
                {
                    "action": "Request human review before acting",
                    "confidence": round(random.uniform(0.20, 0.40), 2),
                },
            ],
            "provider": "mock",
            "llm_note": "Phase 1 Mock LLM — real AI intelligence arrives in Phase 3 with OpenAI/Mistral.",
        }


def get_llm_client() -> BaseLLMClient:
    """Factory — returns the correct LLM client based on LLM_PROVIDER setting."""
    from app.config import settings

    provider = (settings.LLM_PROVIDER or "mock").lower()

    # ── Option 1: Gemini (Recommended) ───────────────────────────────────
    if provider == "gemini":
        if settings.GEMINI_API_KEY:
            try:
                from app.core.llm.gemini_client import GeminiLLMClient
                return GeminiLLMClient(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.error(f"[LLM] Failed to initialize Gemini: {e}")
        else:
            logger.warning("[LLM] GEMINI_API_KEY is missing — falling back to mock")

    # ── Option 2: OpenAI ────────────────────────────────────────────────
    elif provider == "openai":
        if settings.OPENAI_API_KEY:
            try:
                from app.core.llm.openai_client import OpenAILLMClient
                return OpenAILLMClient(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                logger.error(f"[LLM] Failed to initialize OpenAI: {e}")
        else:
            logger.warning("[LLM] OPENAI_API_KEY is missing — falling back to mock")

    # ── Option 3: Claude (Anthropic) ────────────────────────────────────
    elif provider == "claude":
        if settings.CLAUDE_API_KEY:
            try:
                from app.core.llm.claude_client import ClaudeLLMClient
                return ClaudeLLMClient(api_key=settings.CLAUDE_API_KEY)
            except Exception as e:
                logger.error(f"[LLM] Failed to initialize Claude: {e}")
        else:
            logger.warning("[LLM] CLAUDE_API_KEY is missing — falling back to mock")

    # ── Fallback: Mock ──────────────────────────────────────────────────
    return MockLLMClient()
