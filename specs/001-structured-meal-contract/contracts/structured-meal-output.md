# AI Output Contract: Structured Meals

AI output is untrusted. The backend accepts only JSON matching the requested shape.

## Recipe

```json
{
  "name": "Meal name",
  "ingredients": ["ingredient with practical amount"],
  "preparation": "Short preparation steps",
  "portion": "Optional portion guidance",
  "why_it_fits": "Optional plain-language fit explanation"
}
```

## Alternative Meal

```json
{
  "degisen_ogunler": [
    {
      "eski": "Original meal",
      "yeni": "Replacement meal",
      "ingredients": ["explicit replacement ingredient"]
    }
  ]
}
```

## Weekly Plan Addition

Each day keeps its current display strings and may include:

```json
{
  "meal_details": {
    "breakfast": {
      "name": "Display meal name",
      "ingredients": ["explicit ingredient"]
    }
  }
}
```

## Compatibility Rules

- Existing API response keys remain unchanged.
- Recipe JSON is rendered into the current Markdown result after validation.
- Additional structured fields are internal or additive.
- Missing or invalid structured content does not bypass text-based validation.
