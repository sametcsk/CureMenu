# Task completion
- Do not overwrite or discard the user's dirty working tree; inspect `git status --short` first.
- Minimum backend gate: `.\.venv\Scripts\python.exe -m pytest -q --ignore=tests\e2e`.
- For frontend/API/user-flow changes also run: `.\.venv\Scripts\python.exe -m pytest -q tests\e2e`.
- For release/security/evidence changes also run source safety and evidence integrity commands from `mem:suggested_commands`.
- For migration changes, verify Alembic current/head against the intended test DB; never upgrade a real DB without an explicit backup/target check.
- Confirm no secrets, raw health data, token values, or unsafe archives entered source control or logs.
- Report exact test counts/failures from the current tree; do not rely on historical readiness documents.
- No linter/formatter/type-check gate is configured; do not claim these checks passed unless tooling is added and run.