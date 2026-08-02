# Data Model

## AccountDataExport

- `schema_version`: export contract version
- `exported_at`: UTC timestamp
- `account`: non-secret account/profile representation
- `interactions`: account-owned interaction records
- `clinical_decisions`: account-owned decision records
- `decision_events`: events belonging to exported decisions

## AccountDeletionRequest

- `password`: current password used for re-authentication
- `confirmation`: fixed destructive-action confirmation text

## AccountDeletionResult

- `success`: true only when required stores completed
- `deleted_relational`: boolean
- `deleted_memory`: boolean

## UserMemoryMetadata

- `kullanici_id`: profile-specific opaque namespace
- `account_key`: stable opaque account deletion key
- `context_json`: redacted optional context

## DeploymentSafetyMode

- `instance_count`: expected process/application instance count
- `rate_limit_storage_uri`: optional shared store URI
- Safe state implemented for this phase: one instance. Multiple instances also require a PostgreSQL migration and shared storage.
