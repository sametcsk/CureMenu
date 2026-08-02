# Feature Specification: Structured Meal Safety Contract

**Feature Branch**: `001-structured-meal-contract`
**Created**: 2026-08-02
**Status**: Draft
**Input**: Replace fragile free-text-only meal checks with a shared, structured recommendation contract without breaking existing API or frontend behavior.

## User Scenarios & Testing

### User Story 1 - Safer Meal Actions (Priority: P1)

As a user, when I request a recipe, an alternative meal, or a snack, the system checks the actual proposed ingredients against my active health profile before showing the result.

**Why this priority**: These actions can immediately influence food choices, and free-text parsing can miss or misclassify ingredients.

**Independent Test**: Request a meal containing a registered allergen and verify that it is withheld; request a safe substitute and verify that it is shown.

**Acceptance Scenarios**:

1. **Given** a user has a milk-protein allergy, **When** a generated recommendation explicitly contains yogurt, **Then** the recommendation is not shown as suitable.
2. **Given** the same user, **When** a generated recommendation explicitly contains almond milk and no blocked ingredient, **Then** the recommendation can be shown.
3. **Given** the AI response is malformed or lacks required ingredients, **When** the result is processed, **Then** the system fails safely and does not claim the meal is suitable.

---

### User Story 2 - Consistent Weekly Plan Checks (Priority: P1)

As a user, I want weekly-plan meals to pass through the same safety contract as individual recommendations so safety behavior does not vary by screen.

**Why this priority**: A weekly plan has a wider impact than a single answer and should not receive weaker checks.

**Independent Test**: Produce a weekly plan with structured meal ingredients and verify that a blocked ingredient is caught by the same rule engine used for meal actions.

**Acceptance Scenarios**:

1. **Given** a weekly plan contains structured meal ingredients, **When** safety validation runs, **Then** those ingredients are the primary input to the rule engine.
2. **Given** an older or incomplete weekly-plan response has no structured ingredients, **When** validation runs, **Then** existing text-based validation remains active rather than assuming safety.
3. **Given** an existing frontend client, **When** it receives a weekly plan, **Then** the existing day and meal display fields remain available.

---

### User Story 3 - Stable Existing Product Flows (Priority: P2)

As a user, I want recipes, alternatives, snacks, weekly plans, and fridge results to keep their current visible response shapes while gaining stronger validation behind the scenes.

**Why this priority**: Safety improvements must not create demo regressions or force a frontend rewrite.

**Independent Test**: Run existing API and browser tests and verify that the established response fields and UI actions still work.

**Acceptance Scenarios**:

1. **Given** a valid recipe request, **When** the AI returns a structured result, **Then** the user still receives the familiar recipe text.
2. **Given** a valid alternative request, **When** the AI returns a structured result, **Then** the existing alternative-meal response remains usable by the frontend.
3. **Given** a fridge result that has no authoritative generated ingredient list, **When** it is validated, **Then** the system keeps conservative text-based validation and does not treat detected fridge items as the complete recipe.

### Edge Cases

- AI returns valid JSON with an empty ingredient list.
- AI wraps JSON in Markdown fences.
- AI returns extra fields or an unknown meal key.
- A recommendation contains safe substitutes whose names include an allergen word, such as almond milk or gluten-free bread.
- Structured data is unavailable for an older response.
- A generated recipe introduces ingredients that were not detected in the fridge image.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST define one shared structured meal recommendation contract containing a display name and a non-empty ingredient list.
- **FR-002**: Recipe, alternative-meal, and snack recommendations MUST be validated against the active resolved profile before being shown.
- **FR-003**: Weekly plans MUST support structured meal details while preserving existing day and meal display fields.
- **FR-004**: Structured ingredients MUST be the primary rule-engine input when a validated structured list exists.
- **FR-005**: When structured ingredients are unavailable or invalid, the system MUST retain conservative text-based safety checks and MUST NOT infer safety.
- **FR-006**: Malformed AI output MUST produce a safe, user-friendly failure instead of an unvalidated recommendation.
- **FR-007**: Existing public API response fields used by the frontend MUST remain available.
- **FR-008**: Fridge recommendations MUST NOT treat detected source items as a complete generated-recipe ingredient list unless the generated result explicitly supplies that list.
- **FR-009**: All recommendation flows MUST use the same safety-input extraction rules to decide whether validation is structured or text-based.
- **FR-010**: User-facing output MUST not expose internal validation scores, decision identifiers, or raw model payloads.

### Key Entities

- **Structured Meal Recommendation**: A generated meal with a name, explicit ingredients, preparation guidance, and optional user-facing context.
- **Meal Replacement**: An original meal, its proposed replacement, and the replacement's explicit ingredients.
- **Weekly Meal Detail**: Optional structured detail attached to an existing weekly-plan meal display field.
- **Recommendation Safety Input**: The normalized display text, ingredient list, and indication of whether structured validation is available.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All new tests for allergen-containing structured recipes, alternatives, snacks, and weekly meals are blocked before display.
- **SC-002**: Safe substitutes such as almond milk and gluten-free bread pass without false allergen or gluten violations in the covered tests.
- **SC-003**: Malformed or ingredient-free structured AI responses never bypass existing safety validation.
- **SC-004**: Existing API and browser regression suites pass without frontend response-contract changes.
- **SC-005**: The complete backend test suite and frontend parse checks pass after implementation.

## Assumptions

- Existing profile resolution, rule-engine policies, and ingredient catalog remain the source of health constraints.
- This feature improves the structure of AI output but does not claim clinical validation.
- The fridge flow remains conservatively text-validated until its generated recipe can provide authoritative structured ingredients.
