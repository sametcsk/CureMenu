"""Regression tests for product-analytics measurement correctness.

Covers the beta measurement fixes:
- Funnel must not double-count a single user whose pre-auth (anonymous browser)
  id differs from the post-register (pseudonymous account) id.
- Screen active time is emitted as multiple bounded chunks; the aggregation must
  sum them so a long visit is not capped to a single chunk.
- Target-type classification allows self/family/member (caregiver segmentation).
"""
from datetime import datetime, timezone

from src.analytics import build_funnel, build_screen_rows, sanitize_metadata


def _row(event_name, anonymous_user_id, *, screen=None, active_duration_ms=None):
    return {
        "anonymous_user_id": anonymous_user_id,
        "session_id": "00000000-0000-4000-8000-000000000000",
        "event_name": event_name,
        "screen": screen,
        "feature": None,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "active_duration_ms": active_duration_ms,
        "research_cohort": None,
        "metadata_json": "{}",
    }


def test_funnel_base_excludes_pre_auth_signup_started():
    """One real user: anonymous signup_started + authenticated (account id) rest.
    The pre-auth id must not inflate the base, so completed stages read 100%."""
    anon_browser_id = "a" * 32          # pre-auth, before register
    account_id = "b" * 40               # pseudonymous account id after register
    rows = [
        _row("signup_started", anon_browser_id),
        _row("signup_completed", account_id),
        _row("health_profile_started", account_id),
        _row("health_profile_completed", account_id),
        _row("weekly_plan_generated", account_id),  # a first-value event
    ]
    funnel = build_funnel(rows)
    assert funnel["signup"]["users"] == 1
    assert funnel["profile_completed"]["users"] == 1
    assert funnel["profile_completed"]["conversion_rate"] == 100.0
    assert funnel["first_value"]["conversion_rate"] == 100.0


def test_funnel_empty_is_safe():
    funnel = build_funnel([])
    assert funnel["signup"]["users"] == 0
    assert funnel["profile_completed"]["conversion_rate"] == 0.0


def test_screen_time_sums_multiple_active_chunks():
    """A long active visit is now emitted as several ~30s chunks; the backend
    must sum them instead of reporting only one capped chunk."""
    account_id = "b" * 40
    rows = [
        _row("screen_active_time", account_id, screen="curebot", active_duration_ms=30000),
        _row("screen_active_time", account_id, screen="curebot", active_duration_ms=30000),
        _row("screen_active_time", account_id, screen="curebot", active_duration_ms=25000),
    ]
    screens = {row["screen"]: row for row in build_screen_rows(rows)}
    assert screens["curebot"]["total_active_duration_ms"] == 85000
    assert screens["curebot"]["distinct_users"] == 1


def test_target_type_member_accepted_invalid_dropped():
    assert sanitize_metadata({"target_type": "member"}) == {"target_type": "member"}
    assert sanitize_metadata({"target_type": "self"}) == {"target_type": "self"}
    assert sanitize_metadata({"target_type": "family"}) == {"target_type": "family"}
    assert sanitize_metadata({"target_type": "bogus"}) == {}
