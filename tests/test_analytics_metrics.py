"""Regression tests for product-analytics measurement correctness.

Covers the beta measurement fixes:
- Funnel must not double-count a single user whose pre-auth (anonymous browser)
  id differs from the post-register (pseudonymous account) id.
- Screen active time is emitted as multiple bounded chunks; the aggregation must
  sum them so a long visit is not capped to a single chunk.
- Target-type classification allows self/family/member (caregiver segmentation).
"""
from datetime import datetime, timedelta, timezone

from src.analytics import build_completion_rows, build_funnel, build_retention, build_screen_rows, sanitize_metadata


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
    assert funnel["registration"]["signup_started"]["users"] == 1
    assert funnel["activation"]["signup_completed"]["users"] == 1
    assert funnel["activation"]["profile_completed"]["conversion_rate"] == 100.0
    assert funnel["activation"]["first_value"]["conversion_rate"] == 100.0


def test_funnel_empty_is_safe():
    funnel = build_funnel([])
    assert funnel["activation"]["signup_completed"]["users"] == 0
    assert funnel["activation"]["profile_completed"]["conversion_rate"] == 0.0


def test_activation_funnel_excludes_users_outside_signup_cohort():
    rows = [_row("signup_completed", "account-a"), _row("weekly_plan_generated", "account-a"), _row("weekly_plan_generated", "old-account")]
    funnel = build_funnel(rows)
    assert funnel["activation"]["first_value"] == {"users": 1, "conversion_rate": 100.0}


def test_retention_only_counts_mature_signup_cohorts(monkeypatch):
    now = datetime.now(timezone.utc)
    recent = _row("signup_completed", "recent")
    recent["event_time"] = now.isoformat()
    old = _row("signup_completed", "old")
    old["event_time"] = (now - timedelta(days=8)).isoformat()
    d1_visit = _row("screen_viewed", "old")
    d1_visit["event_time"] = (now - timedelta(days=7)).isoformat()
    d7_visit = _row("screen_viewed", "old")
    d7_visit["event_time"] = (now - timedelta(days=1)).isoformat()
    retention = build_retention([recent, old, d1_visit, d7_visit])
    assert retention["D1"] == {"users": 1, "eligible_users": 1, "rate": 100.0}
    assert retention["D3"]["eligible_users"] == 1
    assert retention["D7"] == {"users": 1, "eligible_users": 1, "rate": 100.0}


def test_retention_is_not_measurable_for_new_signup():
    retention = build_retention([_row("signup_completed", "new-account")])
    assert retention["D1"] == {"users": 0, "eligible_users": 0, "rate": None}


def test_completion_rows_separate_success_from_feature_event_volume():
    rows = [_row("weekly_plan_opened", "account-a"), _row("weekly_plan_generated", "account-a"), _row("weekly_plan_generated", "account-b"), _row("curebot_response_received", "account-a")]
    completions = {row["feature"]: row for row in build_completion_rows(rows)}
    assert completions["weekly_plan"] == {"feature": "weekly_plan", "successful_completions": 2, "distinct_users": 2}
    assert completions["curebot"] == {"feature": "curebot", "successful_completions": 1, "distinct_users": 1}


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
    assert screens["curebot"]["average_per_tracked_identity_active_duration_ms"] == 85000
    assert screens["curebot"]["distinct_users"] == 1


def test_target_type_member_accepted_invalid_dropped():
    assert sanitize_metadata({"target_type": "member"}) == {"target_type": "member"}
    assert sanitize_metadata({"target_type": "self"}) == {"target_type": "self"}
    assert sanitize_metadata({"target_type": "family"}) == {"target_type": "family"}
    assert sanitize_metadata({"target_type": "bogus"}) == {}
