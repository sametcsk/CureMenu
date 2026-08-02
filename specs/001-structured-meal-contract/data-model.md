# Data Model: Structured Meal Safety Contract

## StructuredMealRecommendation

| Field | Type | Required | Validation |
|---|---|---:|---|
| name | string | yes | 2-160 characters |
| ingredients | list[string] | yes | 1-30 non-empty items |
| preparation | string | no | user-facing preparation text |
| portion | string | no | optional portion guidance |
| why_it_fits | string | no | optional plain-language context |

## MealReplacement

| Field | Type | Required | Validation |
|---|---|---:|---|
| eski | string | yes | original meal label/text |
| yeni | string | yes | replacement display text |
| ingredients | list[string] | yes | 1-30 explicit replacement ingredients |

## AlternativeMealsPayload

- `degisen_ogunler`: one or more `MealReplacement` values.

## WeeklyPlanDay Extension

Existing fields remain unchanged. An optional `meal_details` map may contain structured meal recommendations for `breakfast`, `lunch`, `dinner`, and snacks.

## RecommendationSafetyInput

| Field | Type | Meaning |
|---|---|---|
| display_text | string | Text retained for medication, scope, and fallback checks |
| ingredients | tuple[string] | Explicit validated ingredients collected from the payload |
| has_structured_ingredients | boolean | True only when at least one validated ingredient exists |

## Validation Transitions

1. Raw model text is parsed.
2. Parsed data is validated against its expected model.
3. Validated data is converted to `RecommendationSafetyInput`.
4. Explicit ingredients drive ingredient rules when present.
5. Otherwise the existing text path remains active.
6. Only a passing result is rendered into the existing API response.
