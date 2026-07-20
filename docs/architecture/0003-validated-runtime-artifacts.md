# ADR-0003: Validate runtime artifacts as one release

**Status:** Accepted

**Date:** 2026-07-20

**Deciders:** Co-Tour maintainers

## Context

The three analytics services previously loaded related CSV files independently. Most deployed inputs were duplicated under the root research dataset, no publication manifest established which copy was authoritative, and readiness did not exercise every recommendation or cross-file dependency. This allowed tests and the deployed application to read different artifact trees.

## Decision

Treat `web_app/data` as the sole deployed artifact release. A checked-in JSON manifest records its schema and bundle versions plus the logical key, safe relative path, SHA-256, byte count, row count, and columns of every active CSV.

Load the release eagerly through one `load_artifact_bundle` boundary. The loader verifies integrity, schemas, finite values, identifiers, coordinate bounds, the complete flow place-season grid, visitor-share totals, and relationships among recommendation, forecast, address, cluster, and coordinate catalogs. FastAPI shares the resulting typed snapshots across all three domain services.

Keep artifact storage local and concrete. A repository protocol, remote store, codec registry, and schema-migration framework will be introduced only if a second implementation becomes necessary.

## Resolved data-quality issue

The initial release manifest temporarily allowed `Munich Residenz` to be absent from the forecast-coordinate catalog because that catalog incorrectly contained the nearby `Residenztheater`. The coordinate identity was corrected from the repository's authoritative Munich Residenz record, the exception was removed, and forecast results now contain all 23 declared attractions.

## Consequences

- Corrupt or incomplete artifacts prevent application construction instead of failing on a later request.
- Readiness represents the complete in-memory release rather than three partial option checks.
- Domain-service method signatures and deterministic results remain unchanged.
- Service constructors retain path compatibility but can share an already-loaded bundle.
- Data updates require an explicit manifest-generation command and reviewable manifest diff.
- Inactive raw inputs and generator scripts are excluded from the production image.
- Research data remains separate lineage and is not an alternative runtime source.
