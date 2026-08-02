# Project conventions
- Turkish domain names/messages are common; preserve established terminology and UTF-8.
- Keep strict architecture boundaries from `docs/ARCHITECTURE.md`; governance records but does not decide, and quality scoring does not enforce medical rules.
- Risky, uncertain, child/pregnancy/renal, medication, or allergy cases must fail safely and direct users to professional review; deterministic known rules outrank generative output.
- Redact PII/health-sensitive data before logs, prompts, traces, Chroma metadata, or external calls; use helpers in `src/privacy/` and privacy-aware logging.
- Maintain account/family-member isolation through resolved profile snapshots and irreversible memory namespaces.
- Preserve decision IDs, evidence/rule provenance, risk/confidence metadata, and audit events across normal, blocked, fallback, and streaming paths.
- External URL/image/PDF inputs require size/type/time/SSRF/private-network validation before processing.
- Frontend renders untrusted/model content through safe formatting/escaping helpers; do not introduce raw HTML sinks.
- Existing tests encode safety and privacy invariants; add regression tests for every bug in these paths.