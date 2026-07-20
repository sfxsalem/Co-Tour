# ADR-0002: Retire the Django web adapter

**Status:** Accepted

**Date:** 2026-07-20

**Deciders:** Co-Tour maintainers

## Context

ADR-0001 made FastAPI the default while retaining Django as a temporary rollback adapter. FastAPI now serves every public page and API, owns the health and security middleware, and has route and container-level regression coverage. Keeping Django duplicates templates, static assets, deployment configuration, tests, and security-sensitive dependencies without providing independent domain behavior.

## Decision

Remove the Django application, Gunicorn entry point, Compose rollback profile, and adapter-only dependencies. Keep `cotour_web.app:create_app` and `cotour_web.app:app` as the stable web boundary. Move the active CSS and recommendation images into `cotour_web/static` so FastAPI owns its complete presentation layer.

Use deployment revisions and immutable image digests for rollback. The last verified pre-retirement revision is `c2a69cc`; it is an emergency release artifact, not a second service that remains deployed or maintained.

## Options considered

| Option | Runtime surface | Maintenance | Rollback |
|---|---:|---:|---|
| Keep both adapters | Largest | Duplicate adapter, CI, assets, and dependencies | Application-level adapter switch |
| Replace both with a new framework | High migration risk | New implementation before a demonstrated need | Previous release image |
| Retain FastAPI and remove Django | Smallest | One adapter and one deployment contract | Previous verified image or revision |

The final option preserves the already-tested public contract while removing the temporary compatibility layer. Introducing protocols, a dependency-injection framework, or another adapter now would add abstraction without a second active implementation.

## Consequences

- `docker compose up --build -d web` is the only supported container launch path.
- CI verifies the domain services, FastAPI application, locked dependencies, security checks, and production image.
- Jinja2 and PyYAML are direct web dependencies because active FastAPI code imports them.
- Django, Gunicorn, WhiteNoise, Folium, and Geopy are no longer in the web runtime lock.
- Release rollback requires retained immutable images or a reproducible artifact built from a verified revision.
- Historical migration plans remain in the repository but are explicitly marked as non-operational records.
