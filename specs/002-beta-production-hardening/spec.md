# Feature Specification: Controlled Beta Production Hardening

**Feature Branch**: `main`
**Created**: 2026-08-02
**Status**: Approved for implementation

## User Scenarios & Testing

### User Story 1 - Controlled beta starts safely (Priority: P1)

As the operator, I can start CureMenu for real beta users only when security-critical environment settings, persistent storage, dependency versions, and operational checks are explicit.

**Independent Test**: Start with safe beta settings and observe a ready service; start with an unsafe cookie, wildcard origin, default data path, tracing, or ambiguous scaling configuration and observe a clear startup failure.

### User Story 2 - Users control their persisted data (Priority: P1)

As an authenticated user, I can export the data CureMenu stores for my account and permanently delete my account after re-authentication, including profile, interaction history, clinical decision records, refresh sessions, and user-memory records.

**Independent Test**: Create two synthetic accounts, export and delete one, then prove that its records are gone while the other account remains unchanged.

### User Story 3 - Core chat remains maintainable without behavior drift (Priority: P2)

As a maintainer, I can change intent handling, response presentation, or stream orchestration independently while preserving the authenticated CureBot contract and safety outcomes.

**Independent Test**: Existing chat API, snapshot isolation, safety, stream, and presentation regression suites pass after responsibilities are moved behind focused modules.

### User Story 4 - Optional browser capabilities fail gracefully (Priority: P2)

As a beta user, I can still use the core dashboard when an optional external chart, QR, font, or formatting resource is unavailable, and I receive a clear fallback for the affected capability.

**Independent Test**: Block optional external resources in a browser test and verify the dashboard remains usable without a blank screen or raw exception.

### User Story 5 - External validation remains explicit (Priority: P3)

As the operator and product owner, I can distinguish completed software controls from items that require hosted infrastructure, a physical device, or clinical experts, so none are represented as completed without evidence.

**Independent Test**: The release checklist requires dated evidence for HTTPS, backup/restore, physical-device camera testing, dependency advisories, and expert pilot review.

## Edge Cases

- Vector storage is temporarily unavailable during account deletion.
- Historical memory records predate account-scoped deletion metadata.
- An export contains malformed legacy metadata.
- A user deletion request is repeated.
- A beta deployment is configured for multiple instances without shared rate-limit storage.
- An optional browser dependency is unavailable while the main API remains healthy.

## Requirements

### Functional Requirements

- **FR-001**: The service MUST reject unsafe real-user environment configurations before accepting traffic.
- **FR-002**: Real-user deployments MUST explicitly select single-instance operation or shared abuse-control storage.
- **FR-003**: Runtime and development dependencies MUST have a reviewed, reproducible version constraint set without local paths or secrets.
- **FR-004**: Authenticated users MUST be able to export only their own persisted account data.
- **FR-005**: Permanent account deletion MUST require recent credential confirmation and MUST be idempotent from the user's perspective.
- **FR-006**: Account deletion MUST remove relational account data and account-scoped user memory without affecting clinical evidence collections or other accounts.
- **FR-007**: If all account data cannot be deleted, the operation MUST fail safely and MUST NOT falsely report completion.
- **FR-008**: Newly persisted user memory MUST carry an opaque stable account deletion key in addition to the profile-specific namespace.
- **FR-009**: Historical profile-specific namespaces discoverable from account history MUST be included in deletion cleanup.
- **FR-010**: Chat intent, presentation, and stream orchestration MUST have separate ownership boundaries while preserving the existing API contract.
- **FR-011**: Optional browser dependency failures MUST NOT blank or disable unrelated dashboard workflows.
- **FR-012**: The release checklist MUST keep hosted, device, advisory, and clinical validation evidence incomplete until actually performed.

### Key Entities

- **Account Data Export**: A versioned, machine-readable snapshot of profile, interaction, decision, and event records owned by one account.
- **Account Deletion Result**: Per-store deletion outcome that is reported only after every required store succeeds.
- **User Memory Account Key**: An opaque deterministic identifier used solely to find and delete one account's vector-memory records.
- **Deployment Safety Mode**: Explicit declaration of instance topology and shared abuse-control availability.
- **External Validation Evidence**: Dated proof for operational or clinical checks that cannot be established by unit tests.

## Assumptions

- The controlled beta remains single-instance unless shared rate-limit storage is explicitly configured.
- SQLite is acceptable only for a small controlled beta with persistent volume, backup, and restore evidence.
- Clinical evidence collections are product assets and are not deleted with an individual user account.
- Clinical validation, real HTTPS termination, and physical-device camera permission cannot be proven solely in local automated tests.

## Success Criteria

- **SC-001**: Every unsafe real-user startup scenario in the checklist fails before serving user traffic.
- **SC-002**: A synthetic user can export all owned categories and no records from another account appear in the export.
- **SC-003**: A deleted synthetic account has zero owned relational and vector-memory records, while a control account is unchanged.
- **SC-004**: All current backend and browser regression suites pass after the chat responsibility split.
- **SC-005**: Blocking optional external browser resources leaves all unrelated critical demo flows usable.
- **SC-006**: Every remaining hosted/device/clinical item has an owner, evidence requirement, and status that cannot be mistaken for completed validation.
