# Implementation Plan: Controlled Beta Production Hardening

## Technical Context

**Language/Version**: Python 3.12 and browser JavaScript
**Primary Dependencies**: FastAPI, SQLite, Chroma, SlowAPI, Playwright
**Storage**: Existing SQLite and Chroma persistence; no schema migration required for the first increment
**Testing**: pytest, Playwright, compile, node parse, source/package safety
**Constraints**: Preserve API compatibility, clinical evidence collections, user isolation, and current demo flows

## Constitution Check

The project constitution is still a template. This plan therefore applies the committed Serena conventions: deterministic safety before AI output, one profile resolver, privacy-preserving persistence, minimal changes, and regression tests proportional to risk.

## Design

1. Add a reviewed constraints file generated from the known-good environment and install it in CI.
2. Make deployment topology explicit. Shared rate-limit storage is optional for an explicitly single-instance beta and mandatory before multi-instance operation.
3. Add an authenticated privacy router for versioned export and password-confirmed deletion.
4. Add database helpers that export and delete only account-owned rows within controlled transactions.
5. Tag new Chroma user-memory records with a stable opaque account key and delete both tagged and historically derivable namespaces.
6. Split chat pure intent/presentation helpers from the route/stream orchestrator without changing responses.
7. Add browser dependency guards and offline regression coverage for optional features; defer a full frontend build migration.
8. Update deployment, retention, backup/restore, and external-validation runbooks with evidence gates.

## Safety Decisions

- Relational deletion is not reported successful when vector cleanup fails.
- Clinical evidence collections are never touched by account deletion.
- Legacy untagged vector memory requires a one-time pre-beta purge or explicit operator evidence.
- No Redis service is introduced blindly; unsafe multi-instance startup is blocked instead.
- No clinical or physical-device item is marked complete by software tests.

## Validation Gates

- Targeted privacy, deletion, rate-limit, config, and chat tests
- Full backend suite
- Full Playwright suite
- Compile and JavaScript parse checks
- Source/package safety and `git diff --check`
