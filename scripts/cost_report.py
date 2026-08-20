"""AI cost report from recorded llm_usage telemetry.

Computes per-feature average cost/tokens PER INTERACTION (grouping model calls by
request_id, since one interaction — e.g. a CureBot turn through the graph — can be
several model calls), then projects light/normal/heavy per-user monthly cost and
simulates N active users.

Scenarios are configurable (do NOT hard-code business truth): pass --scenarios
<json> to override the defaults below. Costs are None until verified prices are
in config/pricing.json — token usage is always shown.

Usage:
    python -m scripts.cost_report
    python -m scripts.cost_report --scenarios my_scenarios.json --users 10 50 100
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

from src.database import _ensure_db, get_connection

# Configurable working assumptions — interactions per active user per month.
DEFAULT_SCENARIOS = {
    "light": {"curebot": 6, "menu_analysis": 2, "weekly_plan": 1, "fridge_analysis": 2, "shopping_list": 1},
    "normal": {"curebot": 20, "menu_analysis": 8, "weekly_plan": 4, "fridge_analysis": 10, "shopping_list": 4},
    "heavy": {"curebot": 60, "menu_analysis": 20, "weekly_plan": 8, "fridge_analysis": 25, "shopping_list": 10},
}
DEFAULT_USER_COUNTS = [10, 50, 100, 250, 500, 1000]


def per_feature_averages() -> dict[str, dict]:
    """Average cost/tokens/model-calls per INTERACTION (request_id), by feature."""
    _ensure_db()
    with get_connection(None) as conn:
        rows = conn.execute(
            """
            SELECT feature, request_id,
                   SUM(COALESCE(estimated_cost, 0)) AS cost,
                   SUM(estimated_cost IS NULL) AS unpriced_calls,
                   SUM(total_tokens) AS tokens,
                   COUNT(*) AS calls
            FROM llm_usage
            GROUP BY feature, request_id
            """
        ).fetchall()
    per_feature: dict[str, list] = defaultdict(list)
    for feature, _rid, cost, unpriced, tokens, calls in rows:
        per_feature[feature].append((cost, unpriced, tokens, calls))
    result: dict[str, dict] = {}
    for feature, interactions in per_feature.items():
        n = len(interactions)
        any_unpriced = any(u for _c, u, _t, _cl in interactions)
        avg_cost = None if any_unpriced else round(sum(c for c, _u, _t, _cl in interactions) / n, 8)
        result[feature] = {
            "interactions": n,
            "avg_cost": avg_cost,
            "avg_tokens": round(sum(t for _c, _u, t, _cl in interactions) / n, 1),
            "avg_model_calls": round(sum(cl for _c, _u, _t, cl in interactions) / n, 2),
        }
    return result


def user_monthly_cost(scenario: dict[str, int], averages: dict[str, dict]) -> tuple[float | None, int]:
    total_cost, total_tokens, priced = 0.0, 0, True
    for feature, count in scenario.items():
        stats = averages.get(feature)
        if not stats:
            continue
        total_tokens += int(stats["avg_tokens"] * count)
        if stats["avg_cost"] is None:
            priced = False
        elif priced:
            total_cost += stats["avg_cost"] * count
    return (round(total_cost, 6) if priced else None), total_tokens


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", help="JSON file overriding light/normal/heavy scenarios")
    parser.add_argument("--users", nargs="*", type=int, default=DEFAULT_USER_COUNTS)
    args = parser.parse_args()

    scenarios = DEFAULT_SCENARIOS
    if args.scenarios:
        scenarios = json.loads(open(args.scenarios, encoding="utf-8").read())

    averages = per_feature_averages()
    print("=== Per-feature averages (per interaction) ===")
    if not averages:
        print("  No llm_usage data yet. Exercise the app, then re-run.")
    for feature, stats in sorted(averages.items()):
        cost = "n/a (pricing not configured)" if stats["avg_cost"] is None else f"{stats['avg_cost']}"
        print(f"  {feature:16} interactions={stats['interactions']:4} avg_tokens={stats['avg_tokens']:8} "
              f"avg_model_calls={stats['avg_model_calls']} avg_cost={cost}")

    print("\n=== Per active user / month (A. VARIABLE AI COST) ===")
    per_user: dict[str, float | None] = {}
    for name, scenario in scenarios.items():
        cost, tokens = user_monthly_cost(scenario, averages)
        per_user[name] = cost
        cost_str = "n/a" if cost is None else f"{cost}"
        print(f"  {name:7} tokens/mo={tokens:9}  AI_cost/mo={cost_str}")

    print("\n=== Fleet simulation (VARIABLE AI COST only) ===")
    print("  NOTE: This is AI (A) cost only. Fixed/semi-fixed infra (B) and other")
    print("  variable infra (C) are separate; do NOT linearly divide Railway RAM per user.")
    for name, cost in per_user.items():
        if cost is None:
            print(f"  {name:7}: n/a until pricing configured")
            continue
        line = "  ".join(f"{u}u={round(cost * u, 2)}" for u in args.users)
        print(f"  {name:7}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
