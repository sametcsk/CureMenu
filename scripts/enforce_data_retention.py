"""Dry-run by default; pass --apply only during an approved maintenance window."""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.database import retention_summary_db
from src.memory import delete_expired_user_memory


def main() -> int:
    parser = argparse.ArgumentParser(description="CureMenu user-data retention maintenance")
    parser.add_argument("--apply", action="store_true", help="Delete expired records")
    args = parser.parse_args()

    retention_days = settings.CUREMENU_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    relational = retention_summary_db(cutoff.isoformat(), apply=args.apply)
    memory_count = delete_expired_user_memory(int(time.time()) - retention_days * 86400, apply=args.apply)
    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "retention_days": retention_days,
        "relational": relational,
        "timestamped_user_memory": memory_count,
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
