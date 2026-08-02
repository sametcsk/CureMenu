# Tasks: Structured Meal Safety Contract

**Input**: Design documents from `specs/001-structured-meal-contract/`

## Phase 1: Shared Contract

- [x] T001 Add failing unit tests for structured and fallback safety extraction in `tests/test_recommendation_contract.py`
- [x] T002 Add structured meal and replacement models in `src/models.py`
- [x] T003 Implement the pure recommendation safety-input extractor in `src/quality/recommendation_contract.py`
- [x] T004 Route the existing tools safety wrapper through the shared extractor in `src/routers/tools.py`

## Phase 2: Safer Meal Actions

- [x] T005 Add API regression tests for structured recipe and alternative outputs in `tests/test_api.py`
- [x] T006 Update recipe AI output parsing, validation, and backward-compatible rendering in `src/routers/tools.py`
- [x] T007 Update alternative-meal output validation and explicit ingredients in `src/routers/tools.py`
- [x] T008 Confirm snack output uses the same extraction and safety path without changing its API response

## Phase 3: Weekly Plan Integration

- [x] T009 Add weekly structured-detail model tests in `tests/test_recommendation_contract.py`
- [x] T010 Extend weekly-plan output with optional structured meal details in `src/models.py` and `src/nodes.py`
- [x] T011 Verify weekly safety extraction prefers details and falls back to display text when details are absent

## Phase 4: Regression and Verification

- [x] T012 Run targeted recommendation and API tests
- [x] T013 Run full pytest and Playwright E2E suites
- [x] T014 Run Python compile, frontend parse, source safety, and diff checks
- [x] T015 Record verified results and remaining fridge-structure limitation in the final report
