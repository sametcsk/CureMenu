# Implementation Plan: Structured Meal Safety Contract

**Branch**: current working branch | **Date**: 2026-08-02 | **Spec**: [spec.md](spec.md)

## Summary

Introduce validated structured meal payloads for recipe and alternative actions, extend weekly plans with optional structured meal details, and centralize conversion of recommendation payloads into safety-check inputs. Preserve all existing frontend response fields and retain text-based checks whenever structured ingredients are unavailable.

## Technical Context

**Language/Version**: Python 3.12, browser JavaScript
**Primary Dependencies**: FastAPI, Pydantic, LangChain message/model interfaces
**Storage**: Existing SQLite and Chroma behavior unchanged
**Testing**: pytest, Playwright, node syntax checks
**Target Platform**: Existing local/server web application
**Project Type**: Web application with FastAPI backend and static frontend
**Performance Goals**: No additional AI call per recommendation
**Constraints**: Dirty working tree; no unrelated edits; no API contract break; no security-policy relaxation
**Scale/Scope**: Recipe, alternative, snack, weekly plan, and shared tool-output validation

## Constitution Check

The project constitution is currently an unratified template. The implementation therefore follows the repository's established constraints:

- Preserve active-profile resolution and existing rule-engine behavior.
- Treat AI output as untrusted and validate before display.
- Keep the patch narrow and backward compatible.
- Add tests proportional to the health-safety impact.
- Do not modify RAG assets, authentication, database schema, or frontend design.

## Project Structure

### Documentation

```text
specs/001-structured-meal-contract/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- structured-meal-output.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code

```text
src/
|-- models.py
|-- nodes.py
|-- quality/
|   `-- recommendation_contract.py
`-- routers/
    `-- tools.py

tests/
|-- test_api.py
|-- test_medical_knowledge.py
`-- test_recommendation_contract.py
```

**Structure Decision**: Add one small quality-layer module for shared extraction. Extend existing models and integrate through existing tool and weekly-plan boundaries without moving unrelated logic.

## Design Decisions

1. Structured ingredients are authoritative only after Pydantic validation and when non-empty.
2. Missing structured data falls back to the current free-text check; it never becomes an automatic pass.
3. Recipe output is rendered back to the existing Markdown string response after validation.
4. Alternative output preserves existing fields and may carry additive ingredient data.
5. Weekly-plan display strings remain unchanged; optional structured details strengthen backend validation.
6. Fridge output continues through the shared safety extractor but stays text-based until the generated recipe itself supplies ingredients.

## Complexity Tracking

No constitutional violations or broad architectural exceptions are required.
