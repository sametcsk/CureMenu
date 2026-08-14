"""Privacy-first, first-party product analytics contracts and query helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from statistics import median
from typing import Any

from src.config import settings


EVENTS = frozenset({
    "session_started", "session_heartbeat", "session_ended", "signup_started", "signup_completed",
    "health_profile_started", "health_profile_completed", "health_profile_updated", "home_viewed",
    "curebot_opened", "curebot_message_sent", "curebot_response_received", "weekly_plan_opened",
    "weekly_plan_started", "weekly_plan_generated", "weekly_plan_action_used", "menu_analysis_opened",
    "menu_analysis_started", "menu_analysis_completed", "fridge_analysis_opened", "fridge_analysis_started",
    "fridge_analysis_completed", "lab_analysis_opened", "lab_analysis_started", "lab_analysis_completed",
    "grocery_opened", "grocery_list_created", "family_profile_created", "family_profile_switched",
    "meal_feedback_submitted", "screen_viewed", "screen_active_time", "cta_clicked",
})
SCREENS = frozenset({"home", "profile", "weekly_plan", "menu_analysis", "fridge", "lab", "grocery", "curebot", "family", "history"})
FEATURES = frozenset({"onboarding", "profile", "curebot", "weekly_plan", "menu_analysis", "fridge", "lab", "grocery", "family", "meal_feedback", "navigation"})
COHORT_RE = re.compile(r"^C\d{2,3}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
UUID_RE = re.compile(r"^[a-f0-9-]{16,64}$", re.IGNORECASE)
SAFE_METADATA_KEYS = frozenset({"source", "result", "action_id", "method", "target_type", "reason", "step"})
SAFE_METADATA_VALUES = {
    "source": {"home", "navigation", "widget", "onboarding", "dashboard"},
    "result": {"success", "error", "cancelled"},
    "method": {"photo", "link", "qr", "manual"},
    "target_type": {"self", "family", "member"},
}
FIRST_VALUE_EVENTS = frozenset({"weekly_plan_generated", "menu_analysis_completed", "curebot_response_received", "fridge_analysis_completed", "lab_analysis_completed", "grocery_list_created"})


def analytics_enabled() -> bool:
    return bool(settings.CUREMENU_ANALYTICS_ENABLED and settings.CUREMENU_ANALYTICS_HASH_KEY)


def pseudonymous_account_id(account_id: str) -> str:
    key = (settings.CUREMENU_ANALYTICS_HASH_KEY or "").encode("utf-8")
    if not key:
        raise ValueError("analytics hash key is unavailable")
    return hmac.new(key, str(account_id).encode("utf-8"), hashlib.sha256).hexdigest()


def sanitize_metadata(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, str] = {}
    for key, raw in value.items():
        if key not in SAFE_METADATA_KEYS or not isinstance(raw, (str, int)):
            continue
        clean = str(raw).strip().lower()
        if len(clean) > 64:
            continue
        if key in SAFE_METADATA_VALUES and clean not in SAFE_METADATA_VALUES[key]:
            continue
        if key in {"action_id", "reason", "step"} and not ID_RE.fullmatch(clean):
            continue
        safe[key] = clean
    return safe


def validate_event(payload: dict[str, Any], *, account_id: str | None) -> dict[str, Any]:
    event_name = str(payload.get("event_name") or "").strip()
    if event_name not in EVENTS:
        raise ValueError("unsupported_event")
    session_id = str(payload.get("session_id") or "").strip()
    if not UUID_RE.fullmatch(session_id):
        raise ValueError("invalid_session")
    client_anonymous_id = str(payload.get("anonymous_user_id") or "").strip()
    if account_id:
        anonymous_user_id = pseudonymous_account_id(account_id)
    elif UUID_RE.fullmatch(client_anonymous_id):
        anonymous_user_id = client_anonymous_id.lower()
    else:
        raise ValueError("invalid_anonymous_user")
    screen = str(payload.get("screen") or "").strip()
    feature = str(payload.get("feature") or "").strip()
    if screen and screen not in SCREENS:
        raise ValueError("invalid_screen")
    if feature and feature not in FEATURES:
        raise ValueError("invalid_feature")
    duration = payload.get("active_duration_ms")
    if duration is not None:
        if isinstance(duration, bool) or not isinstance(duration, int) or not 0 <= duration <= 3_600_000:
            raise ValueError("invalid_duration")
    cohort = str(payload.get("research_cohort") or "").strip().upper()
    if cohort and not COHORT_RE.fullmatch(cohort):
        raise ValueError("invalid_cohort")
    app_version = str(payload.get("app_version") or "").strip()
    if app_version and (len(app_version) > 32 or not ID_RE.fullmatch(app_version.lower())):
        raise ValueError("invalid_app_version")
    return {
        "anonymous_user_id": anonymous_user_id,
        "session_id": session_id.lower(), "event_name": event_name, "screen": screen or None,
        "feature": feature or None, "event_time": datetime.now(timezone.utc).isoformat(),
        "active_duration_ms": duration, "app_version": app_version or None,
        "research_cohort": cohort or None, "metadata": sanitize_metadata(payload.get("metadata")),
    }


def _parsed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        item = dict(row)
        item["when"] = datetime.fromisoformat(str(item["event_time"]).replace("Z", "+00:00"))
        try:
            item["metadata"] = json.loads(item.get("metadata_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            item["metadata"] = {}
        result.append(item)
    return result


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    events = _parsed_rows(rows)
    now = datetime.now(timezone.utc)
    users = {event["anonymous_user_id"] for event in events}
    active_24h = {e["anonymous_user_id"] for e in events if e["when"] >= now - timedelta(days=1)}
    active_7d = {e["anonymous_user_id"] for e in events if e["when"] >= now - timedelta(days=7)}
    sessions = {e["session_id"] for e in events}
    duration_by_session: dict[str, int] = defaultdict(int)
    for event in events:
        duration_by_session[event["session_id"]] += int(event.get("active_duration_ms") or 0)
    durations = list(duration_by_session.values())
    return {"users": {"total": len(users), "active_24h": len(active_24h), "active_7d": len(active_7d)}, "sessions": {"total": len(sessions), "average_active_duration_ms": round(sum(durations) / len(durations)) if durations else 0, "median_active_duration_ms": round(median(durations)) if durations else 0}}


def build_funnel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    events = _parsed_rows(rows)
    # signup_started fires before authentication (anonymous browser id); signup_completed
    # and every later stage fire authenticated (pseudonymous account id). Including the
    # pre-auth event would double-count a single real user, so the funnel base is
    # signup_completed, which shares the id space with the later stages.
    stages = {"signup": {"signup_completed"}, "profile_started": {"health_profile_started"}, "profile_completed": {"health_profile_completed"}, "first_value": FIRST_VALUE_EVENTS}
    counts = {name: len({e["anonymous_user_id"] for e in events if e["event_name"] in names}) for name, names in stages.items()}
    base = counts["signup"] or 0
    return {name: {"users": count, "conversion_rate": round((count / base) * 100, 1) if base else 0.0} for name, count in counts.items()}


def build_retention(rows: list[dict[str, Any]]) -> dict[str, Any]:
    events = _parsed_rows(rows)
    first: dict[str, datetime] = {}
    days: dict[str, set] = defaultdict(set)
    features: dict[str, set[str]] = defaultdict(set)
    for event in events:
        user, day = event["anonymous_user_id"], event["when"].date()
        first[user] = min(first.get(user, event["when"]), event["when"])
        days[user].add(day)
        if event.get("feature"):
            features[user].add(str(event["feature"]))
    def retained(offset: int) -> int:
        return sum(1 for user, started in first.items() if started.date() + timedelta(days=offset) in days[user])
    base = len(first)
    return {f"D{offset}": {"users": retained(offset), "rate": round(retained(offset) * 100 / base, 1) if base else 0.0} for offset in (1, 3, 7)}


def build_feature_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = _parsed_rows(rows)
    data: dict[str, dict[str, Any]] = defaultdict(lambda: {"events": 0, "users": set()})
    for e in events:
        if e.get("feature"):
            data[e["feature"]]["events"] += 1; data[e["feature"]]["users"].add(e["anonymous_user_id"])
    return [{"feature": k, "total_use": v["events"], "distinct_users": len(v["users"])} for k, v in sorted(data.items())]


def build_screen_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = _parsed_rows(rows)
    data: dict[str, dict[str, Any]] = defaultdict(lambda: {"duration": 0, "users": set()})
    for event in events:
        if event["event_name"] == "screen_active_time" and event.get("screen"):
            data[event["screen"]]["duration"] += int(event.get("active_duration_ms") or 0)
            data[event["screen"]]["users"].add(event["anonymous_user_id"])
    return [{"screen": name, "total_active_duration_ms": value["duration"], "average_active_duration_ms": round(value["duration"] / len(value["users"])) if value["users"] else 0, "distinct_users": len(value["users"])} for name, value in sorted(data.items())]


def build_cta_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = _parsed_rows(rows)
    data: dict[str, dict[str, Any]] = defaultdict(lambda: {"clicks": 0, "users": set()})
    for event in events:
        action_id = event.get("metadata", {}).get("action_id")
        if event["event_name"] == "cta_clicked" and action_id:
            data[action_id]["clicks"] += 1; data[action_id]["users"].add(event["anonymous_user_id"])
    return [{"action_id": name, "clicks": value["clicks"], "distinct_users": len(value["users"])} for name, value in sorted(data.items())]
