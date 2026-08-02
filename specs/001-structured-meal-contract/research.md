# Research: Structured Meal Safety Contract

## Decision 1: Preserve display fields and add structured safety data

**Decision**: Keep existing recipe strings and weekly-plan meal strings for clients while parsing new AI responses into validated models before rendering.

**Rationale**: The current frontend consumes strings. Replacing them with nested objects would create a broad contract migration unrelated to the safety goal.

**Alternatives considered**:
- Replace every meal string with an object: rejected because it breaks clients and expands scope.
- Continue free-text checks only: rejected because ingredient identity remains ambiguous.

## Decision 2: One safety-input extractor

**Decision**: Introduce a small pure helper that extracts display text and explicit ingredients from known recommendation shapes.

**Rationale**: Existing extraction is embedded in the tools router. A pure helper is independently testable and lets all supported flows make the same structured-versus-text fallback decision.

**Alternatives considered**:
- Add flow-specific checks: rejected because safety behavior would continue to drift.
- Rewrite the rule engine: rejected because existing rule behavior is outside scope.

## Decision 3: Fail closed on malformed structured AI output

**Decision**: Recipe, alternative, and snack JSON must pass Pydantic validation. Invalid output returns an existing safe error/fallback path.

**Rationale**: Attempting to salvage incomplete health-sensitive output can omit ingredients and produce false confidence.

## Decision 4: Do not treat fridge detections as recipe ingredients

**Decision**: Detected fridge items are context, not an authoritative list of everything in a generated recipe.

**Rationale**: A model can introduce oil, sauces, dairy, gluten, or garnishes not present in the image. Marking only detected items as structured would weaken allergen checks.

## Decision 5: Optional weekly meal details

**Decision**: Weekly plans may include structured meal details alongside current breakfast/lunch/dinner strings.

**Rationale**: This allows incremental adoption and safe fallback for older or imperfect model responses.
