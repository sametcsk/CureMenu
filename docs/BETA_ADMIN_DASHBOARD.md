# CureMenu Beta Operations & Quality Dashboard

## 1. Purpose
An internal, read-only observability screen for the closed-beta period. It lets
the founder/admin watch real product usage and review CureMenu output quality
(especially CureBot and other AI flows) without exposing personal or health data.

## 2. Internal-only scope
This is **not** an end-user feature. There is no navigation to it from the app.
It is intended only for the founder/admin (and, for the anonymous analytics tab,
business/growth review). It never edits, deletes, impersonates, or exports data.

## 3. Dashboard path
- Page: `GET /internal/beta-admin`
- APIs:
  - `GET /api/admin/beta/modules` — module (sayfa) values + counts
  - `GET /api/admin/beta/interactions` — filtered, paginated interaction review
  - `GET /api/admin/beta/quality` — aggregate usage + CureBot quality
  - Product Analytics tab reuses existing `GET /api/admin/analytics/*`

## 4. Required env
- `CUREMENU_ANALYTICS_ADMIN_TOKEN` — the admin bearer token (same one that
  already protects `/api/admin/analytics/*`).
  - If it is **not set**, every admin endpoint returns `403` and the rest of the
    application keeps working normally.
- No new environment variable is introduced for this dashboard.

## 5. Token usage
- Open the page and paste the admin token into the password field.
- The token is held only in page runtime memory for the session. It is **not**
  stored in localStorage/sessionStorage, not put in the URL, and not logged.
- API calls send `Authorization: Bearer <token>`.

## 6. Product Analytics vs Interaction Review
- **Product Analytics (Tab 1)** — anonymous/aggregate product behaviour
  (summary, funnel, retention, features, completions, screens, CTAs). Safe for
  growth/business/BiGG presentation. No health data, no message content.
- **Interactions / Quality (Tabs 2–3)** — redacted user-generated content and
  system outputs, for founder/technical quality review.

## 7. Data sources
- `analytics_events` — product behaviour (Tab 1). Source of truth for anonymous
  product usage; already pseudonymized and metadata-minimised at write time.
- `interaction_logs` — output/quality review (Tabs 2–3). Written by
  `etkilesim_logla()`, which redacts direct identifiers (phone, national id,
  email, IBAN, bearer tokens) before persistence.

## 8. Data shown
- Interactions: `id`, `timestamp`, `pseudonymous_user_id` (`U-XXXXXX`), `module`,
  redacted `input`, redacted `output`, and an allowlisted `metadata` subset.
- Quality: total interactions, module distribution (interactions + distinct
  users), daily interaction counts, and CureBot aggregates (response-path,
  evidence-level, target-resolution-source distributions; clarification,
  findings-present, and artifact-recall counts/rates over a recent sample).

## 9. Data intentionally NOT shown
- Raw phone number, real user name, email, passwords, JWT/refresh/session tokens.
- Family members' real names, full health profile, disease/medication/allergy
  lists as structured fields.
- Metadata identity fields: `target_name`, `target_key`, `target_id`,
  `target_profile_id`, `family_member_id`.
- Raw objects/free content in metadata (`last_object`, `structured_findings`,
  `recent_suggestion_topics`), internal/system prompts, or provider request bodies.
- No fabricated "AI accuracy", "clinical accuracy", or "safety score" metrics.

## 10. Privacy model
- Read-only: all queries are `SELECT`. No insert/update/delete, no export, no
  raw DB download, no profile/health-record browser.
- Content shown is the already-redacted stored text (pre-redaction content is
  never reconstructed).
- Metadata passes a strict **safe allowlist** (`SAFE_METADATA_KEYS`); anything
  not listed is dropped. Malformed/empty/legacy metadata degrades to `{}`.
- Admin API responses set `Cache-Control: no-store` (and inherit the app's
  `X-Content-Type-Options: nosniff`). CORS/trusted-host config is unchanged.

## 11. Pseudonymization
- Users are shown as `U-XXXXXX`, a deterministic label derived from the account
  key via keyed HMAC-SHA256 (`pseudonymous_user_label`).
- Secret: prefers `CUREMENU_ANALYTICS_HASH_KEY`, falls back to the JWT secret so
  the dashboard works even when product analytics is disabled. The secret itself
  is never returned by the API. The phone number cannot be recovered from the label.

## 12. Railway usage
- No change to Railway behaviour. Same SQLite persistent volume, same start
  command, same `/live` and `/ready`. No schema migration is introduced (the
  dashboard reads existing tables/columns).

## 13. Known limitations
- CureBot quality rates are computed over the most recent `QUALITY_SAMPLE_SIZE`
  (5000) turns; `total_turns`/`unique_users` are exact counts.
- The `user` filter resolves a pseudonym by scanning distinct accounts (fine at
  beta scale; would need a lookup table at large scale).
- Modules that do not persist to `interaction_logs` do not appear in Tabs 2–3.
- No dedicated indexes were added; at beta volume the existing table is adequate.

## 14. Future RBAC note
Today a single admin token gates everything. The code separates the anonymous
**business analytics** surface from the **quality reviewer** surface, so a future
role split (`business_analytics` vs `quality_reviewer`) can be layered on without
restructuring the endpoints.
