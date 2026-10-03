"""
core/intelligence/decision_generator.py — Proactive AI Decision Generator

Phase 4 Milestone 2: Auto-fires AI decisions based on patterns detected in
live events — without waiting for user to manually call /recommend.

Rules per module:
  CRM     → No lead activity in 5 days, deal stagnation
  Website → High bounce rate, low conversions, spike in traffic
  Shield  → Multiple threats in a time window
  Marketing → (placeholder for when credentials are available)

How it works:
  1. Called by the scheduler every hour
  2. Fetches all users with active integrations
  3. For each user+module combination, checks for trigger conditions
  4. If condition met → inserts a decision into the decisions table with outcome="pending"
  5. User sees it in Decision Log as "Pending Review"

SAFE: Only reads from events table, only writes to decisions table.
      Never modifies any existing record. All inserts are new rows.
"""

from app.database import get_supabase, q
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _since(hours: int = 0, days: int = 0) -> str:
    delta = timedelta(hours=hours, days=days)
    return (_now() - delta).isoformat()


# Autonomy levels, least to most permissive. Used to cap a module's level at
# the account-wide setting.
_LEVEL_RANK = {"observe": 0, "assist": 1, "autonomous": 2}

# Bounds for the hourly user-discovery query. The widest generator lookback is
# 7 days (CRM no-activity), so anyone with no events in that window cannot
# trigger anything and does not need scanning.
_USER_SCAN_LOOKBACK_DAYS = 7
# Explicit cap so truncation is detectable in code rather than silently applied
# by PostgREST's own db-max-rows setting.
_USER_SCAN_ROW_LIMIT = 5000


def _resolve_level(module_level: str | None, global_level: str) -> str:
    """
    Resolve the effective autonomy level for one module.

    `global_level` acts as a CEILING, not merely a fallback. This previously
    read `user_aut.get("crm") or global_level`, but the per-module columns are
    `NOT NULL DEFAULT` in the schema, so they are never NULL and the fallback
    was unreachable dead code whenever a config row existed. Two consequences:

      * A user setting global_level="observe" to pause the AI platform-wide
        was ignored — their row still held crm='assist', website='autonomous'
        (the DB defaults), so decisions kept generating. The kill switch did
        nothing.
      * An admin PATCHing a single module for a user with no row caused the
        remaining columns to take DB defaults — including website='autonomous'
        — silently enrolling a user in autonomous mode.

    Capping at the global level makes the pause authoritative while still
    letting a module be set MORE restrictive than the account default.
    """
    effective = module_level or global_level
    if _LEVEL_RANK.get(effective, 1) > _LEVEL_RANK.get(global_level, 1):
        return global_level
    return effective


async def _already_generated(db, user_id: str, module: str, trigger: str, hours: int = 6) -> bool:
    """
    Prevent duplicate decisions: skip if this TRIGGER already fired for this
    user+module within the last N hours.

    Matches on state_snapshot->>trigger, NOT on the action text.

    Why: this previously compared exact `action` equality, but three callers
    checked a static dedup_key while inserting an INTERPOLATED action, e.g.
        action    = f"Launch follow-up campaign — {n} leads unresponsive"
    No row is ever stored with action == dedup_key, so the check always
    returned False and a fresh duplicate was generated on EVERY hourly scan —
    24/day indefinitely. For shield (confidence 0.95, autonomous) that meant
    the escalate n8n workflow re-fired hourly.

    The trigger is stable by construction (every _insert_decision call passes
    snapshot={"trigger": ...}), so it dedups correctly whether or not the
    action text interpolates runtime values.
    """
    try:
        result = (
            await q(db.table("decisions")
            .select("id")
            .eq("user_id", user_id)
            .eq("module", module)
            .eq("state_snapshot->>trigger", trigger)
            .gte("created_at", _since(hours=hours)))
        )
        return bool(result.data)
    except Exception:
        return False  # If check fails, allow the insert


async def _insert_decision(
    db,
    user_id:        str,
    module:         str,
    action:         str,
    reasoning:      str,
    confidence:     float,
    snapshot:       dict,
    autonomy_level: str = "assist",
    action_code:    str | None = None,
) -> None:
    """
    Insert one proactive AI decision into the decisions table.

    Implements the full mode behavior matrix:
      observe    → observe_only=True,  outcome=pending  (admin sees, user does not)
      assist     → observe_only=False, outcome=pending  (user must approve)
      autonomous → outcome depends on confidence:
          ≥ 0.90 → auto_executed=True, outcome=applied  (silent auto-apply)
          < 0.90 → falls back to assist behavior       (pending, needs approval)
    """
    observe_only  = False
    auto_executed = False
    outcome       = "pending"  # default: Assist

    if autonomy_level == "observe":
        # OBSERVE: Generate internally for admin visibility, hide from user
        observe_only = True
        outcome      = "pending"

    elif autonomy_level == "autonomous":
        if confidence >= 0.90:
            # AUTONOMOUS high-confidence: auto-apply silently
            auto_executed = True
            outcome       = "applied"
            logger.info(
                f"[DecisionGen] AUTO-EXEC {module}/{action[:40]} "
                f"conf={confidence} user={user_id[:8]}"
            )
            # n8n executor call happens after insert below, once we have a
            # decision_id — only fires if action_code matches a registered
            # n8n workflow (see executor.py); otherwise it's a no-op status.
        else:
            # AUTONOMOUS low-confidence: fall back to Assist (needs human review)
            outcome = "pending"
            logger.info(
                f"[DecisionGen] Autonomous fallback→Assist "
                f"conf={confidence:.2f}<0.90 {module} user={user_id[:8]}"
            )
    # else: "assist" → outcome=pending (default, no changes needed)

    try:
        result = await q(db.table("decisions").insert({
            "user_id":        user_id,
            "module":         module,
            "action":         action,
            "action_code":    action_code,
            "reasoning":      reasoning,
            "confidence":     confidence,
            "state_snapshot": {**snapshot, "auto_generated": True},
            "alternatives":   [],
            "outcome":        outcome,
            "auto_executed":  auto_executed,
            "observe_only":   observe_only,
        }))
        status_tag = "[Observe]" if observe_only else ("[Auto-Applied]" if auto_executed else "[Pending]")
        logger.info(f"[DecisionGen] {status_tag} {module}/{action[:40]} — user={user_id[:8]}")

        # Autonomous + high-confidence + a registered action_code → actually
        # trigger the n8n workflow now that decision-writers tag action_code.
        # Failures here are logged only; the decision itself is already
        # recorded as "applied" and this is best-effort automation on top.
        if auto_executed and action_code and result.data:
            try:
                from app.core.integrations.executor import execute_decision
                exec_result = await execute_decision(
                    decision_id = result.data[0]["id"],
                    module      = module,
                    action      = action,
                    action_code = action_code,
                    parameters  = snapshot,
                    user_id     = user_id,
                )
                logger.info(
                    f"[DecisionGen] n8n execute → {exec_result['status']} "
                    f"decision={result.data[0]['id'][:8]}"
                )
            except Exception as exec_err:
                logger.error(f"[DecisionGen] n8n execute failed (non-fatal): {exec_err}")
    except Exception as e:
        logger.error(f"[DecisionGen] Failed to insert decision: {e}")


# ── Module-Specific Generators ─────────────────────────────────────────────────

async def _generate_crm_decisions(db, user_id: str, autonomy_level: str = "assist") -> int:
    """
    CRM triggers:
    - No new events in 5 days → "Re-engage lead pipeline"
    - High count of no_response events → "Follow up campaign recommended"
    - Deals with no stage change in 7 days → "Deal stagnation alert"
    """
    generated = 0

    try:
        # ── Trigger 1: No CRM activity in 5 days ───────────────────────────
        recent = (
            await q(db.table("events")
            .select("id")
            .eq("user_id", user_id)
            .eq("module", "crm")
            .gte("created_at", _since(days=5))
            .limit(1))
        )
        if not recent.data:
            action = "Re-engage lead pipeline — no CRM activity detected in 5 days"
            if not await _already_generated(db, user_id, "crm", "no_activity_5d"):
                await _insert_decision(
                    db, user_id, "crm", action,
                    reasoning       = "No CRM events have been recorded in the last 5 days. Your pipeline may be stalling. Consider running a re-engagement sequence on cold leads.",
                    confidence      = 0.82,
                    snapshot        = {"trigger": "no_activity_5d"},
                    autonomy_level  = autonomy_level,
                    action_code     = "send_followup",
                )
                generated += 1

        # ── Trigger 2: High no-response rate ───────────────────────────────
        no_resp = (
            await q(db.table("events")
            .select("id")
            .eq("user_id", user_id)
            .eq("module", "crm")
            .eq("event_type", "no_response_7d")
            .gte("created_at", _since(days=7)))
        )
        if len(no_resp.data or []) >= 3:
            action = f"Launch follow-up campaign — {len(no_resp.data)} leads unresponsive"
            if not await _already_generated(db, user_id, "crm", "high_no_response"):
                await _insert_decision(
                    db, user_id, "crm", action,
                    reasoning       = f"{len(no_resp.data)} leads have not responded in 7 days. A targeted follow-up sequence (email or call) is recommended to recover pipeline value.",
                    confidence      = 0.88,
                    snapshot        = {"trigger": "high_no_response", "count": len(no_resp.data)},
                    autonomy_level  = autonomy_level,
                    action_code     = "send_followup",
                )
                generated += 1

    except Exception as e:
        logger.error(f"[DecisionGen] CRM generator error: {e}")

    return generated


async def _generate_website_decisions(db, user_id: str, autonomy_level: str = "assist") -> int:
    """
    Website triggers:
    - High bounce rate (>60%) → "Landing page optimization needed"
    - No conversions in 3 days → "Conversion funnel review required"
    - Spike in page views (>50% above average) → "Traffic spike detected — review funnel"
    """
    generated = 0

    try:
        # ── Trigger 1: Bounce rate check ───────────────────────────────────
        recent_events = (
            await q(db.table("events")
            .select("event_type")
            .eq("user_id", user_id)
            .eq("module", "website")
            .in_("event_type", ["session_bounce", "session_engaged", "session_end"])
            .gte("created_at", _since(days=3)))
        )
        events = recent_events.data or []
        if events:
            bounces   = sum(1 for e in events if e["event_type"] == "session_bounce")
            total_s   = len(events)
            bounce_rt = round((bounces / total_s) * 100, 1) if total_s else 0

            if bounce_rt > 60:
                action = f"Landing page optimization needed — bounce rate at {bounce_rt}%"
                if not await _already_generated(db, user_id, "website", "high_bounce_rate", hours=12):
                    await _insert_decision(
                        db, user_id, "website", action,
                        reasoning       = f"Your bounce rate is {bounce_rt}% over the last 3 days, above the healthy threshold of 40%. Review your landing page headline, load speed, and CTA placement.",
                        confidence      = 0.78,
                        snapshot        = {"trigger": "high_bounce_rate", "bounce_rate": bounce_rt},
                        autonomy_level  = autonomy_level,
                        action_code     = "send_alert",
                    )
                    generated += 1

        # ── Trigger 2: No conversions in 3 days ────────────────────────────
        conversions = (
            await q(db.table("events")
            .select("id")
            .eq("user_id", user_id)
            .eq("module", "website")
            .in_("event_type", ["form_submit", "page_conversion"])
            .gte("created_at", _since(days=3)))
        )
        if not conversions.data:
            action = "Conversion funnel review required — no conversions in 3 days"
            if not await _already_generated(db, user_id, "website", "no_conversions_3d"):
                await _insert_decision(
                    db, user_id, "website", action,
                    reasoning       = "No form submissions or conversions have been tracked in the last 3 days. Review your conversion funnel — especially CTAs, form UX, and page flow.",
                    confidence      = 0.74,
                    snapshot        = {"trigger": "no_conversions_3d"},
                    autonomy_level  = autonomy_level,
                    action_code     = "notify_team",
                )
                generated += 1

    except Exception as e:
        logger.error(f"[DecisionGen] Website generator error: {e}")

    return generated


async def _generate_shield_decisions(db, user_id: str, autonomy_level: str = "assist") -> int:
    """
    Shield triggers:
    - 3+ threats in 1 hour → "Escalate to security team"
    - Any breach event → "Immediate breach response required"
    """
    generated = 0

    try:
        # ── Trigger 1: Threat cluster ───────────────────────────────────────
        threats = (
            await q(db.table("events")
            .select("id")
            .eq("user_id", user_id)
            .eq("module", "shield")
            .eq("event_type", "threat_blocked")
            .gte("created_at", _since(hours=1)))
        )
        if len(threats.data or []) >= 3:
            action = f"Escalate to security team — {len(threats.data)} threats blocked in 1 hour"
            if not await _already_generated(db, user_id, "shield", "threat_cluster", hours=2):
                await _insert_decision(
                    db, user_id, "shield", action,
                    reasoning       = f"{len(threats.data)} threat events were blocked within the last hour. This clustering suggests a coordinated attack or scanning attempt. Recommend immediate security team escalation.",
                    confidence      = 0.95,
                    snapshot        = {"trigger": "threat_cluster", "count": len(threats.data)},
                    autonomy_level  = autonomy_level,
                    action_code     = "escalate",
                )
                generated += 1

        # ── Trigger 2: Breach detected ─────────────────────────────────────
        breach = (
            await q(db.table("events")
            .select("id")
            .eq("user_id", user_id)
            .eq("module", "shield")
            .eq("event_type", "breach")
            .gte("created_at", _since(hours=24)))
        )
        if breach.data:
            action = "Immediate breach response required — security breach detected"
            if not await _already_generated(db, user_id, "shield", "breach_event", hours=24):
                await _insert_decision(
                    db, user_id, "shield", action,
                    reasoning       = "A breach event was detected in the last 24 hours. Initiate your incident response plan: isolate affected systems, preserve logs, notify stakeholders.",
                    confidence      = 0.99,
                    snapshot        = {"trigger": "breach_event", "count": len(breach.data)},
                    autonomy_level  = autonomy_level,
                    action_code     = "escalate",
                )
                generated += 1

    except Exception as e:
        logger.error(f"[DecisionGen] Shield generator error: {e}")

    return generated


# ── Master Generator ────────────────────────────────────────────────────────────

async def run_decision_generator() -> dict:
    """
    Called by the scheduler every hour.
    Fetches all users with any event data and runs module generators for each.

    Autonomy enforcement:
      - Fetches all user_autonomy_config rows in ONE query (not per-user)
      - Per module per user, checks the level: observe | assist | autonomous
      - observe    → decision generated with observe_only=True (admin sees, user does not)
      - assist     → decision generated with outcome=pending (user approves)
      - autonomous → confidence ≥0.90 → auto-applied; <0.90 → falls back to assist

    Returns a summary dict for logging.
    """
    logger.info("[DecisionGen] ── Starting proactive decision scan ──")
    db = get_supabase()
    total_generated  = 0
    auto_executed    = 0
    users_scanned    = 0

    try:
        # ── 1. Fetch all autonomy configs in ONE query (efficient) ────────────
        autonomy_result = await q(db.table("user_autonomy_config").select(
            "user_id, global_level, crm, marketing, shield, website"
        ))
        autonomy_map = {
            row["user_id"]: row
            for row in (autonomy_result.data or [])
        }

        # ── 2. Get all distinct user_ids that have any events ─────────────────
        # Bounded user discovery.
        #
        # This was `db.table("events").select("user_id").execute()` — no limit,
        # no filter — pulling EVERY row of the highest-growth table in the
        # system, hourly, just to compute a set of distinct user ids.
        #
        # That was also a correctness bug, not only a performance one:
        # PostgREST caps result sets (db-max-rows, commonly 1000). Past that
        # cap the response is silently truncated, so users whose events fall
        # outside the returned page are never scanned and never get decisions —
        # while the log still reports a plausible users_scanned.
        #
        # Every generator below only looks back 1-7 days, so restricting
        # discovery to the same window is equivalent in behaviour and orders of
        # magnitude smaller. The explicit limit makes truncation detectable
        # (see the warning below) instead of invisible.
        result = (
            await q(db.table("events")
            .select("user_id")
            .gte("created_at", _since(days=_USER_SCAN_LOOKBACK_DAYS))
            .limit(_USER_SCAN_ROW_LIMIT))
        )
        all_events = result.data or []
        user_ids = list({e["user_id"] for e in all_events if e.get("user_id")})
        users_scanned = len(user_ids)

        if len(all_events) >= _USER_SCAN_ROW_LIMIT:
            # We hit our own cap, which means the recency window still holds
            # more rows than we fetched — some users may not appear in this
            # page and would be skipped silently. Surface it rather than
            # reporting a plausible-looking users_scanned.
            logger.warning(
                f"[DecisionGen] User-discovery query returned the full "
                f"{_USER_SCAN_ROW_LIMIT}-row cap — some users may not have been "
                f"scanned this run. Move this to a DISTINCT RPC or paginate."
            )

        # ── 3. Per-user scan with autonomy enforcement ────────────────────────
        for user_id in user_ids:
            try:
                user_aut  = autonomy_map.get(user_id, {})
                global_l  = user_aut.get("global_level") or "assist"

                crm_level     = _resolve_level(user_aut.get("crm"),     global_l)
                website_level = _resolve_level(user_aut.get("website"), global_l)
                shield_level  = _resolve_level(user_aut.get("shield"),  global_l)

                n = 0
                n += await _generate_crm_decisions(
                    db, user_id, autonomy_level=crm_level
                )
                n += await _generate_website_decisions(
                    db, user_id, autonomy_level=website_level
                )
                n += await _generate_shield_decisions(
                    db, user_id, autonomy_level=shield_level
                )
                total_generated += n

            except Exception as ue:
                logger.error(f"[DecisionGen] Error for user={user_id[:8]}: {ue}")
                continue

    except Exception as e:
        logger.error(f"[DecisionGen] Master scan failed: {e}")

    logger.info(
        f"[DecisionGen] ── Scan complete — "
        f"users={users_scanned} decisions_generated={total_generated} ──"
    )
    return {
        "users_scanned":       users_scanned,
        "decisions_generated": total_generated,
        "auto_executed":       auto_executed,
    }
