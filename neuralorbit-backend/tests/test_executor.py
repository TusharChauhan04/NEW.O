"""
Tests for BUG-10's fix: the n8n executor previously matched on (module, action)
where `action` was always a free-text sentence written by both the rule-based
generator and the LLM recommender — never matching the registry, so execution
always returned "no_webhook". Decisions are now also tagged with a structured
action_code, and the executor matches on that instead.
"""

import pytest

from app.core.integrations import executor
from app.core.llm.client import MockLLMClient


def test_get_registered_actions_returns_only_that_modules_codes():
    crm_actions = executor.get_registered_actions("crm")
    assert "assign_lead" in crm_actions
    assert "pause_campaign" not in crm_actions  # that's a marketing action


@pytest.mark.parametrize("module", ["crm", "marketing", "shield", "website", "neural-orbit"])
def test_mock_llm_action_codes_are_always_valid_or_none(module):
    """Every action_code the mock client can produce must either be None or a
    real entry in that module's registered actions — guards against typos in
    the mock insight data silently breaking execution."""
    valid = set(executor.get_registered_actions(module))
    insights = MockLLMClient._MODULE_INSIGHTS.get(module, MockLLMClient._MODULE_INSIGHTS["neural-orbit"])
    for _, _, action_code in insights:
        assert action_code is None or action_code in valid


async def test_execute_decision_no_webhook_without_action_code():
    # Legacy behavior preserved: a decision with no action_code (e.g. an old
    # row from before this migration) still can't be executed.
    result = await executor.execute_decision(
        decision_id="d1", module="crm", action="Some free-text sentence",
        parameters={}, user_id="u1", action_code=None,
    )
    assert result["status"] == "no_webhook"


async def test_execute_decision_no_webhook_for_unregistered_code():
    result = await executor.execute_decision(
        decision_id="d1", module="crm", action="text", parameters={},
        user_id="u1", action_code="not_a_real_action",
    )
    assert result["status"] == "no_webhook"
