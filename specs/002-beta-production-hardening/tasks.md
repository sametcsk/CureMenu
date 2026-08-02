# Tasks: Controlled Beta Production Hardening

## Phase 1: Foundational configuration

- [x] T001 Add reproducible dependency constraints in `constraints.txt`
- [x] T002 Update CI install commands to use `constraints.txt` in `.github/workflows/ci.yml`
- [x] T003 Add deployment topology settings and validation in `src/config.py`
- [x] T004 Configure optional shared limiter storage in `src/rate_limit.py`
- [x] T005 Add topology fail-fast tests in `tests/test_production_readiness.py`

## Phase 2: User Story 1 - Data control

- [x] T006 [US1] Add account export/delete request models in `src/models.py`
- [x] T007 [US1] Add account export and relational deletion helpers in `src/database.py`
- [x] T008 [US1] Add stable account memory key and deletion helpers in `src/memory.py`
- [x] T009 [US1] Tag new user-memory writes in `src/routers/tools.py`
- [x] T010 [US1] Add authenticated privacy endpoints in `src/routers/privacy.py`
- [x] T011 [US1] Register the privacy router in `api.py`
- [x] T012 [US1] Add isolation, export, re-authentication, and deletion tests in `tests/test_account_privacy.py`

## Phase 3: User Story 2 - Chat ownership boundaries

- [x] T013 [US2] Move pure intent helpers to `src/chat_intents.py`
- [x] T014 [US2] Move response composition helpers to `src/chat_response.py`
- [x] T015 [US2] Keep route and SSE orchestration in `src/routers/chat.py`
- [x] T016 [US2] Run and strengthen chat/snapshot regression tests in `tests/test_api.py` and `tests/test_profile_snapshot_invariants.py`

## Phase 4: User Story 3 - Browser resilience

- [x] T017 [US3] Inventory critical versus optional external assets in `frontend/`
- [x] T018 [US3] Verify existing guarded fallbacks for chart and QR capabilities in `frontend/modules/`
- [x] T019 [US3] Verify external-resource failure coverage in `tests/e2e/`

## Phase 5: Operational evidence

- [x] T020 Add single-instance beta deployment runbook in `docs/DEPLOYMENT_RUNBOOK.md`
- [x] T021 Add backup/restore verification script and instructions in `scripts/` and `docs/`
- [x] T022 Add retention, export, deletion, and legacy Chroma purge procedure in `docs/DATA_LIFECYCLE.md`
- [x] T023 Update `RELEASE_READINESS.md` with evidence-gated external checks
- [x] T024 Run targeted and full validation suites
- [x] T025 Report which hosted/device/clinical risks still require external evidence
