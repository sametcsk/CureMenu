# Privacy API Contract

## `GET /api/account/export`

- Requires authenticated account.
- Returns a versioned JSON export containing only data owned by that account.
- Never returns password hashes, token values, secret configuration, or another account's data.

## `DELETE /api/account`

Request:

```json
{
  "password": "current password",
  "confirmation": "DELETE"
}
```

Behavior:

- Requires authenticated account and valid current password.
- Rejects an incorrect confirmation or password.
- Removes user-memory records and relational account records.
- Clears authentication cookies on success.
- Returns a safe error and does not claim completion if a required store fails.
