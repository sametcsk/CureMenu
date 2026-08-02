# Research Decisions

## Deployment topology

**Decision**: Keep the first controlled beta single-instance and fail startup for multi-instance operation while the relational layer uses SQLite. A future multi-instance deployment also requires shared rate-limit storage.

**Rationale**: It closes silent abuse-control inconsistency without introducing an unconfigured Redis dependency.

## Data deletion

**Decision**: Require password confirmation and complete vector cleanup before committing relational deletion.

**Rationale**: A partial deletion must not be represented as complete, and cookie possession alone is insufficient for an irreversible action.

## Chroma retention

**Decision**: Add a stable opaque account key to new memory records and also derive historical namespaces from current profile and interaction metadata.

**Rationale**: Profile fingerprints change over time; deletion cannot rely only on the current namespace.

## Dependency reproducibility

**Decision**: Constrain the known-good environment without upgrading packages in this feature.

**Rationale**: Reproducibility can improve independently from dependency modernization and its regression risk.

## Browser dependencies

**Decision**: Guard optional libraries and prove graceful degradation now; schedule local bundling/build migration separately.

**Rationale**: Runtime Tailwind and QR/chart libraries require a deliberate asset pipeline, not an unsafe mechanical copy.

## Clinical validation

**Decision**: Keep it as an external evidence gate.

**Rationale**: Automated software tests cannot establish clinical validity.
