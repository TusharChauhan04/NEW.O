"""
api/v1/analytics.py — Analytics & Overview Endpoints

GET /analytics/overview?module=crm  — KPI cards + chart data per module
                                       Admin: platform-wide aggregates
                                       User:  own business data only

GET /analytics/learning?module=crm  — Weekly accuracy/decisions/corrections
GET /analytics/mistakes?module=crm  — Mistake → correction log (from decisions)
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user, is_admin_user
from app.database import get_supabase, q
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Seed/Fallback data (shown when no real events yet) ──────────────────────────
# These are used as graceful fallbacks for new users with no event history

_SEED_KPIS = {
    "neural-orbit": {
        "kpis": [
            {"title": "Business Intelligence Score", "value": "—",    "unit": "/100", "change": "No data yet", "trend": "neutral", "icon": "bi-cpu",              "color": "#5B8CFF", "desc": "Connect your modules to start tracking"},
            {"title": "AI Decisions Made",           "value": "0",    "unit": "",     "change": "—",            "trend": "neutral", "icon": "bi-lightning",        "color": "#22C55E", "desc": "Decisions logged across all modules"},
            {"title": "Avg AI Confidence",           "value": "—",    "unit": "%",    "change": "—",            "trend": "neutral", "icon": "bi-bullseye",         "color": "#8B5CF6", "desc": "Average decision confidence level"},
            {"title": "Active Integrations",         "value": "0",    "unit": "",     "change": "—",            "trend": "neutral", "icon": "bi-plug-fill",        "color": "#F59E0B", "desc": "Connected platforms"},
        ],
        "chart_labels": [], "chart_a": [], "chart_b": [], "chart_c": [],
        "insight": "Connect your first integration to start generating AI insights.",
        "insight_sub": "NeuralOrbit AI — Waiting for your first data connection",
    },
    "crm": {
        "kpis": [
            {"title": "Active Leads",   "value": "—", "unit": "",   "change": "No CRM connected", "trend": "neutral", "icon": "bi-people",           "color": "#5B8CFF", "desc": "Connect Zoho or HubSpot to track leads"},
            {"title": "Conversion Rate","value": "—", "unit": "%",  "change": "—",                "trend": "neutral", "icon": "bi-graph-up",          "color": "#22C55E", "desc": "Leads converted to customers"},
            {"title": "Avg Deal Value", "value": "—", "unit": "",   "change": "—",                "trend": "neutral", "icon": "bi-currency-dollar",   "color": "#8B5CF6", "desc": "Average deal size"},
            {"title": "Pipeline Velocity","value":"—","unit":"/day","change": "—",                "trend": "neutral", "icon": "bi-lightning",         "color": "#F59E0B", "desc": "Leads advancing per day"},
        ],
        "chart_labels": [], "chart_a": [], "chart_b": [], "chart_c": [],
        "insight": "Connect Zoho CRM or HubSpot to see live pipeline data.",
        "insight_sub": "NeuralOrbit CRM AI — Waiting for CRM integration",
    },
    "marketing": {
        "kpis": [
            {"title": "Campaign ROAS",     "value": "—", "unit": "x",  "change": "No Ads connected", "trend": "neutral", "icon": "bi-bar-chart",      "color": "#8B5CF6", "desc": "Return on ad spend"},
            {"title": "Cost Per Lead",     "value": "—", "unit": "",   "change": "—",                "trend": "neutral", "icon": "bi-coin",           "color": "#22C55E", "desc": "Average cost per acquired lead"},
            {"title": "Email Open Rate",   "value": "—", "unit": "%",  "change": "—",                "trend": "neutral", "icon": "bi-envelope-open",  "color": "#5B8CFF", "desc": "AI-optimized send times"},
            {"title": "Ad Spend Efficiency","value":"—","unit": "%",  "change": "—",                "trend": "neutral", "icon": "bi-pie-chart",      "color": "#F59E0B", "desc": "Spend allocation accuracy"},
        ],
        "chart_labels": [], "chart_a": [], "chart_b": [], "chart_c": [],
        "insight": "Connect Meta Ads or Google Ads to see campaign performance.",
        "insight_sub": "NeuralOrbit Marketing AI — Waiting for ad platform connection",
    },
    "shield": {
        "kpis": [
            {"title": "Threats Blocked",       "value": "—", "unit": "",      "change": "Monitoring active", "trend": "neutral", "icon": "bi-shield-check",    "color": "#F59E0B", "desc": "Threats neutralized"},
            {"title": "False Positive Rate",   "value": "—", "unit": "%",     "change": "—",                    "trend": "neutral", "icon": "bi-check-circle",    "color": "#22C55E", "desc": "AI detection accuracy"},
            {"title": "Response Time",         "value": "—", "unit": "ms",    "change": "—",                    "trend": "neutral", "icon": "bi-lightning",       "color": "#5B8CFF", "desc": "Avg threat containment speed"},
            {"title": "Security Score",        "value": "—", "unit": "/100",  "change": "—",                    "trend": "neutral", "icon": "bi-shield-fill",     "color": "#8B5CF6", "desc": "Overall security health"},
        ],
        "chart_labels": [], "chart_a": [], "chart_b": [], "chart_c": [],
        "insight": "Shield is monitoring your environment. No threats detected yet.",
        "insight_sub": "NeuralOrbit Shield AI — Active monitoring, no events yet",
    },
    "website": {
        "kpis": [
            {"title": "Conversion Rate",  "value": "—", "unit": "%",    "change": "No tracker installed", "trend": "neutral", "icon": "bi-graph-up-arrow", "color": "#22C55E", "desc": "Install Website Tracker to start"},
            {"title": "Bounce Rate",      "value": "—", "unit": "%",    "change": "—",                    "trend": "neutral", "icon": "bi-arrow-left-right","color": "#5B8CFF", "desc": "Single-page session rate"},
            {"title": "Session Value",    "value": "—", "unit": "",     "change": "—",                    "trend": "neutral", "icon": "bi-currency-dollar", "color": "#8B5CF6", "desc": "Revenue per session"},
            {"title": "Core Web Vitals", "value": "—", "unit": "/100", "change": "—",                    "trend": "neutral", "icon": "bi-speedometer2",    "color": "#F59E0B", "desc": "Google performance score"},
        ],
        "chart_labels": [], "chart_a": [], "chart_b": [], "chart_c": [],
        "insight": "Install the NeuralOrbit Website Tracker snippet to start collecting visitor data.",
        "insight_sub": "NeuralOrbit Website AI — Waiting for tracker installation",
    },
}


@router.get("/overview")
async def get_overview(
    module:         str = Query("neural-orbit", description="Module key: neural-orbit | crm | marketing | shield | website"),
    target_user_id: Optional[str] = Query(None, description="Admin only: fetch overview for a specific user"),
    current_user:   dict = Depends(get_current_user),
):
    """
    Get overview KPIs and chart data.
    - Admin (without target_user_id): platform-wide aggregates across all users
    - Admin (with target_user_id):    that specific client's data
    - User:                           own data only
    Falls back to seed data if no real events exist yet.
    """
    is_admin = await is_admin_user(current_user)
    user_id  = target_user_id if (is_admin and target_user_id) else current_user["sub"]
    db       = get_supabase()

    # Compute real KPIs from database
    try:
        # ── Event counts (all modules) ────────────────────────────────────────
        evt_query = db.table("events").select("id, module, event_type, created_at")
        if not (is_admin and not target_user_id):
            evt_query = evt_query.eq("user_id", user_id)
        evt_query = evt_query.eq("module", module)
        evt_result = await q(evt_query)
        events     = evt_result.data or []

        # ── Decision counts ───────────────────────────────────────────────────
        dec_query = db.table("decisions").select("id, module, confidence, created_at")
        if not (is_admin and not target_user_id):
            dec_query = dec_query.eq("user_id", user_id)
        if module != "neural-orbit":
            dec_query = dec_query.eq("module", module)
        dec_result = await q(dec_query)
        decisions  = dec_result.data or []

        # ── Reward stats ──────────────────────────────────────────────────────
        rew_query = db.table("rewards").select("reward_value, module")
        if not (is_admin and not target_user_id):
            rew_query = rew_query.eq("user_id", user_id)
        if module != "neural-orbit":
            rew_query = rew_query.eq("module", module)
        rew_result = await q(rew_query)
        rewards    = rew_result.data or []

        total_decisions = len(decisions)
        # Confidence is STORED 0.0-1.0 by every writer (decision_generator uses
        # 0.74-0.99; the LLM clients clamp with min(..., 0.99)). It is DISPLAYED
        # as a percentage, so convert here rather than at each render site.
        # Previously this emitted e.g. 0.9 into a card labelled "%".
        avg_confidence  = round(
            (sum(d.get("confidence", 0) or 0 for d in decisions) / max(1, total_decisions)) * 100, 1
        )
        avg_reward      = round(sum(r.get("reward_value", 0) or 0 for r in rewards) / max(1, len(rewards)), 2)
        total_events    = len(events)

        if total_decisions > 0 or total_events > 0:

            # ── CRM-native KPIs ───────────────────────────────────────────────
            if module == "crm":
                # Count events by type from synced Zoho/Custom data
                type_counts = {}
                for ev in events:
                    t = ev.get("event_type", "unknown")
                    type_counts[t] = type_counts.get(t, 0) + 1

                active_leads   = type_counts.get("lead_created", 0) + type_counts.get("contact_created", 0)
                deals_closed   = type_counts.get("deal_closed", 0)
                meetings       = type_counts.get("meeting_booked", 0)
                qualified      = type_counts.get("lead_qualified", 0)
                total_pipeline = max(active_leads, 1)
                conv_rate      = round((deals_closed / total_pipeline) * 100, 1) if total_pipeline > 0 else 0

                kpis = [
                    {"title": "Active Leads",     "value": str(active_leads),  "unit": "",
                     "change": "From Zoho CRM",   "trend": "up",               "icon": "bi-people",
                     "color": "#5B8CFF",           "desc": "Leads & contacts in pipeline"},
                    {"title": "Deals Closed",     "value": str(deals_closed),  "unit": "",
                     "change": "Synced from CRM", "trend": "up" if deals_closed > 0 else "neutral",
                     "icon": "bi-trophy",          "color": "#22C55E",          "desc": "Won deals recorded"},
                    {"title": "Meetings Booked",  "value": str(meetings),      "unit": "",
                     "change": "—",               "trend": "up" if meetings > 0 else "neutral",
                     "icon": "bi-calendar-check", "color": "#8B5CF6",          "desc": "Meetings & calls logged"},
                    {"title": "Conversion Rate",  "value": str(conv_rate),     "unit": "%",
                     "change": "Leads → Deals",   "trend": "up" if conv_rate > 0 else "neutral",
                     "icon": "bi-graph-up",        "color": "#F59E0B",          "desc": "Deal close rate"},
                ]
                insight = (
                    f"{active_leads} leads in pipeline. {deals_closed} deals closed. "
                    f"Conversion rate: {conv_rate}%."
                    if active_leads > 0
                    else "CRM synced. No leads recorded yet — check your Zoho CRM data."
                )
                return {
                    "kpis":        kpis,
                    "chart_labels": [],
                    "chart_a":     [],
                    "chart_b":     [],
                    "chart_c":     [],
                    "insight":     insight,
                    "insight_sub": f"NeuralOrbit CRM AI — {total_events} events synced from Zoho CRM",
                    "has_data":    True,
                    "module":      module,
                }

            # ── Website-native KPIs ───────────────────────────────────────────
            if module == "website":
                type_counts = {}
                for ev in events:
                    t = ev.get("event_type", "unknown")
                    type_counts[t] = type_counts.get(t, 0) + 1

                page_views    = type_counts.get("page_view", 0)
                form_submits  = type_counts.get("form_submit", 0)
                bounces       = type_counts.get("session_bounce", 0)
                engaged       = type_counts.get("session_engaged", 0)
                cta_clicks    = type_counts.get("cta_click", 0)
                total_sessions = max(bounces + engaged + type_counts.get("session_end", 0), 1)
                bounce_rate   = round((bounces / total_sessions) * 100, 1)

                kpis = [
                    {"title": "Page Views",      "value": str(page_views),   "unit": "",
                     "change": "From tracker",   "trend": "up",              "icon": "bi-eye",
                     "color": "#22C55E",          "desc": "Total pages tracked"},
                    {"title": "Form Submits",    "value": str(form_submits), "unit": "",
                     "change": "—",              "trend": "up" if form_submits > 0 else "neutral",
                     "icon": "bi-envelope-check","color": "#5B8CFF",         "desc": "Conversion-intent actions"},
                    {"title": "Bounce Rate",     "value": str(bounce_rate),  "unit": "%",
                     "change": "—",              "trend": "up" if bounce_rate < 40 else "neutral",
                     "icon": "bi-arrow-left-right","color": "#F59E0B",       "desc": "Single-page sessions"},
                    {"title": "Engaged Sessions","value": str(engaged),      "unit": "",
                     "change": "—",              "trend": "up" if engaged > 0 else "neutral",
                     "icon": "bi-clock-history", "color": "#8B5CF6",         "desc": "Sessions > 5 minutes"},
                ]
                insight = (
                    f"{page_views} pages tracked. {form_submits} form conversions. "
                    f"Bounce rate: {bounce_rate}%."
                    if page_views > 0
                    else "Tracker is live. Data will appear when visitors land on your website."
                )
                return {
                    "kpis":        kpis,
                    "chart_labels": [],
                    "chart_a":     [],
                    "chart_b":     [],
                    "chart_c":     [],
                    "insight":     insight,
                    "insight_sub": f"NeuralOrbit Website AI — {total_events} events from tracker",
                    "has_data":    True,
                    "module":      module,
                }

            # ── Shield-native KPIs ────────────────────────────────────────────
            if module == "shield":
                type_counts = {}
                for ev in events:
                    t = ev.get("event_type", "unknown")
                    type_counts[t] = type_counts.get(t, 0) + 1

                threats_blocked = type_counts.get("threat_blocked", 0)
                false_positives = type_counts.get("false_positive", 0)
                breaches        = type_counts.get("breach", 0)
                data_misuse     = type_counts.get("data_misuse_detected", 0)
                total_alerts    = max(threats_blocked + false_positives, 1)
                fp_rate         = round((false_positives / total_alerts) * 100, 2)

                kpis = [
                    {"title": "Threats Blocked",    "value": str(threats_blocked), "unit": "",
                     "change": "From webhook",      "trend": "up",                 "icon": "bi-shield-check",
                     "color": "#F59E0B",             "desc": "Security threats neutralized"},
                    {"title": "False Positive Rate","value": str(fp_rate),         "unit": "%",
                     "change": "—",                 "trend": "up" if fp_rate < 5 else "neutral",
                     "icon": "bi-check-circle",      "color": "#22C55E",            "desc": "AI detection accuracy"},
                    {"title": "Breach Events",      "value": str(breaches),        "unit": "",
                     "change": "—",                 "trend": "up" if breaches == 0 else "down",
                     "icon": "bi-exclamation-triangle","color": "#EF4444",          "desc": "Security breaches detected"},
                    {"title": "Data Misuse",        "value": str(data_misuse),     "unit": "",
                     "change": "—",                 "trend": "up" if data_misuse == 0 else "down",
                     "icon": "bi-shield-exclamation","color": "#8B5CF6",           "desc": "Data policy violations"},
                ]
                insight = (
                    f"Shield blocked {threats_blocked} threats. {breaches} breach events. "
                    f"False positive rate: {fp_rate}%."
                    if total_events > 0
                    else "Shield webhook connected. Awaiting first security event."
                )
                return {
                    "kpis":        kpis,
                    "chart_labels": [],
                    "chart_a":     [],
                    "chart_b":     [],
                    "chart_c":     [],
                    "insight":     insight,
                    "insight_sub": f"NeuralOrbit Shield AI — {total_events} security events logged",
                    "has_data":    True,
                    "module":      module,
                }

            # ── Generic KPIs for neural-orbit and marketing ────────────────────
            kpis = [
                {"title": "AI Decisions Made", "value": str(total_decisions), "unit": "",
                 "change": "From your data", "trend": "up", "icon": "bi-lightning",
                 "color": "#22C55E", "desc": "Decisions logged"},
                {"title": "Avg AI Confidence", "value": str(avg_confidence), "unit": "%",
                 "change": "—", "trend": "up", "icon": "bi-bullseye",
                 "color": "#8B5CF6", "desc": "Average decision confidence"},
                {"title": "Avg Reward Score", "value": str(avg_reward), "unit": "",
                 "change": "—", "trend": "up" if avg_reward > 0.7 else "neutral",
                 "icon": "bi-star-fill", "color": "#F59E0B", "desc": "AI reward signal average"},
                {"title": "Total Events", "value": str(total_events), "unit": "",
                 "change": "—", "trend": "up", "icon": "bi-activity",
                 "color": "#5B8CFF", "desc": "Events tracked"},
            ]
            insight = (
                f"AI has made {total_decisions} decisions with {avg_confidence}% average confidence."
                if total_decisions > 0
                else "Events are being tracked. AI decisions will appear here soon."
            )
            return {
                "kpis":        kpis,
                "chart_labels": [],
                "chart_a":     [],
                "chart_b":     [],
                "chart_c":     [],
                "insight":     insight,
                "insight_sub": f"NeuralOrbit AI — Based on {total_events} events and {total_decisions} decisions",
                "has_data":    True,
                "module":      module,
            }

    except Exception as e:
        logger.warning(f"[Analytics] DB error, falling back to seed: {e}")

    # No real data or DB error → return seed/empty state
    seed = _SEED_KPIS.get(module, _SEED_KPIS["neural-orbit"])
    return {**seed, "has_data": False, "module": module}


@router.get("/learning")
async def get_learning(
    module:         str = Query("neural-orbit"),
    target_user_id: Optional[str] = Query(None, description="Admin only"),
    current_user:   dict = Depends(get_current_user),
):
    """
    Weekly accuracy/decisions/corrections from the decisions table.
    Groups decisions by week and computes accuracy from reward scores.
    Falls back to an empty/onboarding state for new users.
    """
    is_admin = await is_admin_user(current_user)
    user_id  = target_user_id if (is_admin and target_user_id) else current_user["sub"]
    db       = get_supabase()

    try:
        query = (
            db.table("decisions")
            .select("id, module, confidence, outcome, created_at")
            .order("created_at", desc=False)
            .limit(500)
        )
        if not (is_admin and not target_user_id):
            query = query.eq("user_id", user_id)
        if module != "neural-orbit":
            # NOTE: every writer (decision_generator, recommender, manual create)
            # stores module names lowercase — filter must match, not titlecase.
            query = query.eq("module", module)

        result    = await q(query)
        decisions = result.data or []

        if not decisions:
            return {
                "weekly_data":   [],
                "has_data":      False,
                "onboarding_msg": "Your AI is still learning. Decisions will appear here once your integrations are active.",
            }

        # Group decisions by week
        weeks: dict = {}
        for d in decisions:
            try:
                dt   = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
                week = f"W{(dt.isocalendar()[1])}"
                if week not in weeks:
                    weeks[week] = {"decisions": 0, "corrections": 0, "confidence_sum": 0}
                weeks[week]["decisions"]     += 1
                weeks[week]["confidence_sum"] += d.get("confidence", 0) or 0
                if d.get("outcome") == "rejected":
                    weeks[week]["corrections"] += 1
            except Exception:
                continue

        weekly_data = [
            {
                "week":        w,
                "accuracy":    round(v["confidence_sum"] / max(1, v["decisions"]), 1),
                "decisions":   v["decisions"],
                "corrections": v["corrections"],
            }
            for w, v in sorted(weeks.items())
        ]

        return {"weekly_data": weekly_data, "has_data": True}

    except Exception as e:
        logger.warning(f"[Analytics] Learning error: {e}")
        return {"weekly_data": [], "has_data": False, "error": str(e)}


@router.get("/mistakes")
async def get_mistakes(
    module:         str = Query("neural-orbit"),
    target_user_id: Optional[str] = Query(None, description="Admin only"),
    limit:          int = Query(10, ge=1, le=50),
    current_user:   dict = Depends(get_current_user),
):
    """
    Mistake → correction log: decisions that were overridden (outcome=rejected).
    These represent cases where the human disagreed with the AI.
    """
    is_admin = await is_admin_user(current_user)
    user_id  = target_user_id if (is_admin and target_user_id) else current_user["sub"]
    db       = get_supabase()

    try:
        query = (
            db.table("decisions")
            .select("*")
            .eq("outcome", "rejected")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if not (is_admin and not target_user_id):
            query = query.eq("user_id", user_id)
        if module != "neural-orbit":
            # NOTE: every writer (decision_generator, recommender, manual create)
            # stores module names lowercase — filter must match, not titlecase.
            query = query.eq("module", module)

        result    = await q(query)
        decisions = result.data or []

        mistakes = [
            {
                "id":         d.get("id", "")[:8].upper(),
                "module":     d.get("module", ""),
                "date":       d.get("created_at", "")[:10],
                "mistake":    d.get("action", ""),
                "correction": d.get("reasoning", "Human override applied"),
                # Compare on the stored 0.0-1.0 scale. This read `> 90`, which
                # no stored confidence can ever exceed, so the branch was
                # unreachable and every mistake was labelled "medium".
                "severity":   "high" if (d.get("confidence") or 0) > 0.90 else "medium",
                "confidence": d.get("confidence", 0),
            }
            for d in decisions
        ]

        return {"mistakes": mistakes, "count": len(mistakes), "has_data": bool(mistakes)}

    except Exception as e:
        logger.warning(f"[Analytics] Mistakes error: {e}")
        return {"mistakes": [], "count": 0, "has_data": False}


# ── NEW: GET /analytics/learning-stats ────────────────────────────────────────
# Phase 4 — Milestone 1: AI Learning Feedback Loop
# Returns per-module AI accuracy, trend data, and velocity.
# ADDITIVE: does not modify any existing endpoint above.
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/learning-stats")
async def get_learning_stats(
    module: Optional[str] = Query(None, description="Filter by module (or omit for all modules)"),
    days:   int           = Query(30,   ge=7, le=90, description="Trend window in days"),
    current_user: dict    = Depends(get_current_user),
):
    """
    Phase 4 (Milestone 1) — AI Learning Stats endpoint.

    Returns:
    - Per-module accuracy percentages from learning_stats table
    - Day-by-day accuracy trend for the selected module
    - Learning velocity: last 7 days vs previous 7 days
    - Summary: total decisions reviewed, overall accuracy

    Safe fallback: if learning_stats table doesn't exist yet (migration pending),
    returns empty-but-valid structure so the frontend doesn't break.
    """
    from app.core.intelligence.learning_engine import (
        get_all_module_accuracy,
        get_accuracy_trend,
        get_learning_velocity,
    )

    user_id = current_user["sub"]

    # ── 1. All-module accuracy breakdown ──────────────────────────────────────
    all_modules = await get_all_module_accuracy(user_id)

    # ── 2. Module-specific trend + velocity ───────────────────────────────────
    trend    = []
    velocity = {"velocity": 0.0, "label": "Stable", "recent_accuracy": 0.0, "prev_accuracy": 0.0}

    if module:
        trend    = await get_accuracy_trend(user_id, module, days=days)
        velocity = await get_learning_velocity(user_id, module)

    # ── 3. Overall summary ────────────────────────────────────────────────────
    total_decisions = sum(m.get("total_decisions", 0) for m in all_modules)
    total_correct   = sum(m.get("correct_decisions", 0) for m in all_modules)
    total_rejected  = sum(m.get("rejected_decisions", 0) for m in all_modules)
    scored          = total_correct + total_rejected
    overall_acc     = round((total_correct / scored) * 100, 1) if scored > 0 else 0.0

    # ── 4. Per-module formatted for frontend cards ─────────────────────────────
    module_cards = [
        {
            "module":           m.get("module"),
            "accuracy_pct":     m.get("accuracy_pct", 0.0),
            "total_decisions":  m.get("total_decisions", 0),
            "correct":          m.get("correct_decisions", 0),
            "rejected":         m.get("rejected_decisions", 0),
            "avg_confidence":   m.get("avg_confidence", 0.0),
            "last_decision_at": m.get("last_decision_at"),
            # Visual grade: A/B/C/D/F based on accuracy
            "grade": (
                "A" if m.get("accuracy_pct", 0) >= 90 else
                "B" if m.get("accuracy_pct", 0) >= 75 else
                "C" if m.get("accuracy_pct", 0) >= 60 else
                "D" if m.get("accuracy_pct", 0) >= 40 else
                "F"
            ),
        }
        for m in all_modules
    ]

    has_data = bool(all_modules) or bool(trend)

    return {
        "has_data":        has_data,
        "overall_accuracy": overall_acc,
        "total_decisions":  total_decisions,
        "total_correct":    total_correct,
        "total_rejected":   total_rejected,
        "module_cards":     module_cards,
        "trend":            trend,
        "velocity":         velocity,
        "module":           module,
        "days":             days,
    }
