# Quickstart: Structured Meal Safety Contract

## Targeted checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_recommendation_contract.py tests\test_api.py -k "recipe or alternative or snack or weekly"
```

## Full backend suite

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Syntax and source safety

```powershell
.\.venv\Scripts\python.exe -m compileall -q api.py src tests
node --check frontend\app.js
Get-ChildItem frontend\modules\*.js | ForEach-Object { node --check $_.FullName }
.\.venv\Scripts\python.exe scripts\check_package_safety.py --source-root .
git diff --check
```

## Expected behavior

- Unsafe explicit ingredients are blocked.
- Safe substitutes are not false positives.
- Malformed JSON is not shown as a valid recommendation.
- Existing frontend-facing response fields continue to work.
