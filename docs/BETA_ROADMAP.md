# CureMenu Beta Roadmap

Last updated: 2026-07-27

## Decision

Beta preparation can start, but new feature development should stay frozen until the current working tree is separated into clean commits and a staging smoke test is completed.

CureMenu should be presented as a decision-support MVP, not as a clinically validated medical product. The current technical work is enough to continue toward a controlled beta, but not enough for an open public launch.

## Beta Scope

Closed beta means:

- Limited users, invited manually.
- Synthetic or consented real data only.
- Clear disclaimer: CureMenu does not diagnose, treat, or replace a doctor/dietitian.
- Logs and traces must not contain raw health data.
- User feedback and expert review are part of the beta, not proof that the product is clinically validated.

## Current Technical Baseline

Current product areas:

- Auth, session handling, refresh token rotation, and rate limiting.
- Active profile snapshot isolation for self, family member, and family-wide flows.
- CureBot with safety checks, ingredient constraints, and user-facing language cleanup.
- Weekly plan, recipe, alternative meal, snack, Smart Grocery, menu scan, fridge scan, lab upload, and history flows.
- Lab and fridge persistence/rehydration work in progress.
- RAG/evidence registry and source governance work separated from product stability.

Last known validation results:

- `pytest`: 308 passed, 1 warning.
- Playwright E2E: 22 passed.
- Python compile: clean.
- Frontend `node --check`: clean.
- Package/source safety: SOURCE_SAFE.

These are software regression checks. They are not clinical validation.

## Working Tree Classification

### A. Product/Stability Changes To Preserve

These files appear to contain real product, demo, persistence, profile, CureBot, or test changes and should be reviewed for a clean stability baseline commit:

- `frontend/modules/api-client.js`
- `frontend/modules/auth-manager.js`
- `frontend/modules/chat-widget.js`
- `frontend/modules/lab-upload.js`
- `frontend/modules/menu-scanner.js`
- `frontend/modules/profile-family-manager.js`
- `frontend/modules/weekly-actions.js`
- `frontend/modules/weekly-plan-manager.js`
- `src/agent_state.py`
- `src/grocery/capability.py`
- `src/grocery/profile.py`
- `src/nodes.py`
- `src/presentation.py`
- `src/quality/scope_policy.py`
- `src/routers/chat.py`
- `src/routers/grocery.py`
- `src/routers/tools.py`
- `src/profile_context.py`
- `tests/e2e/conftest.py`
- `tests/e2e/test_critical_user_flows.py`
- `tests/test_api.py`
- `tests/test_governance_event_schema.py`
- `tests/test_medical_knowledge.py`
- `tests/test_profile_snapshot_invariants.py`
- `tests/test_scope_policy.py`

Status also shows these files, but current diff output suggests they may be line-ending/stat-only changes or need separate verification before staging:

- `.github/workflows/ci.yml`
- `frontend/app.js`
- `frontend/dashboard.html`
- `src/database.py`
- `src/ilac_etkilesim.py`
- `src/models.py`
- `tests/conftest.py`
- `tests/test_ilac_etkilesim.py`

### B. RAG / Research / Documentation Work

These should not be mixed into product stability commits:

- `data/rag_candidates/`
- `data/rag_knowledge_catalog.json`
- `docs/rag_source_gap_report.md`
- `docs/RAG_KNOWLEDGE_ASSET_MAP.md`
- `docs/CureMenu_Proje_Gelisim_Raporu.docx`
- `docs/MEETING_READINESS.md`
- `scripts/build_rag_knowledge_catalog.py`
- `tests/test_rag_knowledge_catalog.py`

Official or academic PDFs should remain outside Git until redistribution rights and source policy are settled.

### C. Never Commit Local Artifacts

Keep these out of Git:

- `.env`
- `*.db`, `*.db-wal`, `*.db-shm`
- `*.zip`
- `database_backups/`
- `security_quarantine/`
- `outputs/`
- `temp_extract/`
- `.pytest_cache/`
- `__pycache__/`
- Playwright screenshots/videos/test-results unless explicitly needed for a QA report.

### D. Risky Mixed Files

The safest assumption is that several files contain multiple rounds of work in the same diff:

- `frontend/modules/chat-widget.js`
- `frontend/modules/lab-upload.js`
- `frontend/modules/menu-scanner.js`
- `frontend/modules/profile-family-manager.js`
- `src/routers/chat.py`
- `src/routers/tools.py`
- `tests/e2e/test_critical_user_flows.py`
- `tests/test_api.py`

Hunk-based staging is possible but risky. Before committing, prefer one clean "beta stabilization baseline" commit that includes all tested product/stability changes, while keeping RAG/research/docs and local artifacts out.

## Beta Readiness Classification

### BLOCKER

These must be solved before inviting real beta users:

- Clean Git baseline: product/stability changes committed separately from RAG/research artifacts.
- HTTPS staging environment with `/live` and `/ready` passing.
- Production-like config: secure cookies, trusted hosts, non-wildcard CORS, debug off, explicit DB path.
- Backup and rollback procedure for the beta database.
- Secret rotation if old unsafe ZIP files were ever shared.
- Privacy baseline: user consent, disclaimer, retention note, deletion/export procedure.
- Real device smoke: mobile file picker, camera/QR behavior over HTTPS, keyboard/form behavior.
- Final smoke with real providers: one register/login, one profile, one plan, one CureBot question, one lab PDF, one menu/fridge flow, one Smart Grocery flow.

### WARNING

These do not block a controlled beta, but must be disclosed internally:

- SQLite is acceptable only for local/demo or very small closed beta; not for larger production.
- In-memory rate limiting is acceptable only for single-instance beta.
- CDN/runtime asset dependency can still affect offline or restricted networks.
- RAG registry is useful for traceability, but source coverage is not complete clinical validation.
- Ingredient catalog and rule engine reduce obvious unsafe suggestions, but do not cover every medical edge case.
- Model responses can vary; deterministic guardrails reduce risk but do not eliminate it.
- PyMuPDF licensing needs review before SaaS/commercial use.

### ACCEPTED RISK

These are conscious limits of the current MVP:

- No claim of clinical validation.
- No diagnosis or treatment.
- No guarantee that every drug-food interaction is covered.
- No open public launch before expert pilot and production operations are ready.
- RAG is a source/explanation layer, not the final medical decision-maker.

### POST-BETA

Work after the first controlled beta:

- Move production persistence to PostgreSQL or managed DB.
- Move rate limiting/session revocation to Redis or equivalent shared store.
- Add structured monitoring, error budgets, and privacy-safe observability.
- Build dependency lock/constraints workflow and scheduled security audit.
- Expand official evidence registry through a documented source approval process.
- Add expert review workflow and clinical pilot protocol.
- Add account deletion, data export, and retention automation.
- Prepare hosted deployment runbook and incident checklist.

## Six-Month Roadmap

### Weeks 1-2: Freeze And Baseline

- Stop new feature work.
- Separate product/stability commits from RAG/research changes.
- Update `RELEASE_READINESS.md` with current test counts.
- Run full regression: pytest, Playwright, Python compile, node checks, package/source safety.
- Create a repeatable local demo script and demo account.

### Weeks 3-4: Staging Setup

- Bring up HTTPS staging.
- Configure production-like environment values.
- Verify `/live`, `/ready`, auth, cookies, CORS, body limits, timeouts, and logs.
- Run real-provider smoke with low-cost calls.
- Test physical mobile device flows.

### Months 2-3: Expert And User Validation

- Run 10-20 controlled user tests.
- Interview dietitians/clinicians and document objections.
- Collect failure cases: false positives, false negatives, confusing language, slow responses.
- Improve source registry only through approved, traceable sources.
- Keep product claims conservative.

### Months 4-6: Controlled Beta Expansion

- Expand to 30-50 invited users if failure rate is acceptable.
- Add operational metrics: activation, profile completion, first useful answer, blocked unsafe suggestions, latency, retention.
- Prepare legal/privacy review.
- Decide whether to continue B2C, B2B dietitian tooling, clinic pilot, or restaurant/menu compliance angle.

## Source And RAG Enrichment Plan

Do not add random PDFs just because they are scientific. Prioritize sources that can be defended:

- Official drug labels for common medications.
- Official guidelines for diabetes, hypertension, celiac disease, CKD, gout, allergy, and cardiovascular risk.
- Dietitian-reviewed internal rules with review status.
- Source metadata: title, issuer, date, URL/file hash, topic, authority tier, license/redistribution status, review status.

RAG should answer "what source supports this explanation?" It should not override the active profile snapshot or deterministic safety constraints.

## Expert Validation Plan

Needed roles:

- Dietitian/nutrition expert for meal suitability and wording.
- Physician/pharmacist input for drug-food and lab-result boundaries.
- Data privacy/KVKK reviewer for consent, retention, and health-data processing.
- Software/security reviewer for hosted beta readiness.

Potential academic outreach can focus on: "I have a working decision-support MVP and need expert review of safety boundaries, not endorsement of clinical accuracy."

## Demo Flow For Meetings

Five-minute safe demo:

1. Register/login with a synthetic user.
2. Create a health profile with allergy, medication, and dietary restriction examples.
3. Ask CureBot one safe alternative question and one allergy-blocking question.
4. Generate a weekly plan.
5. Show recipe/alternative/snack actions.
6. Upload a small synthetic lab PDF and show history/graph empty-state or chart.
7. Show menu/fridge scan only if local smoke passed that day.
8. Close with: this is a decision-support MVP that needs expert pilot validation.

Avoid saying:

- "Clinically validated."
- "Zero risk."
- "Doctor/dietitian replacement."
- "All interactions are covered."
- "Fully production ready."

Use instead:

- "Safety-oriented decision-support MVP."
- "Profile-aware guardrails."
- "Source traceability."
- "Expert validation is the next step."
- "Closed beta candidate after staging and privacy checks."

## Immediate Next Actions

1. Keep feature freeze.
2. Inspect and separate the current working tree.
3. Commit only product/stability baseline after full test pass.
4. Keep RAG/research assets in a separate branch or later commit.
5. Update release readiness with current validation numbers.
6. Build HTTPS staging and run the smoke plan.
7. Prepare expert outreach and beta consent/disclaimer text.

## Freeze Rule

After the beta baseline commit, code should change only for:

- Security vulnerability.
- Data loss or data leakage.
- Demo/beta blocker.
- Verified critical bug.
- Source/policy update through the approved evidence workflow.

Everything else goes to post-beta backlog.
