# ADR-0001: Make FastAPI the default web adapter

**Status:** Superseded by ADR-0002
**Date:** 2026-07-16
**Deciders:** Co-Tour maintainers

## Context

Co-Tour previously deployed Django while FastAPI was introduced route by route. The home, recommendation, hotspot-forecast, tourist-flow, and contact pages now have FastAPI parity tests. Analytics behavior lives behind framework-independent services, and FastAPI provides typed APIs, security headers, trusted-host validation, CSP-safe visualizations, and a health endpoint. The legacy contact form never submitted or stored messages, so preserving its appearance would falsely imply delivery.

## Decision

Run FastAPI/Uvicorn as the default `web` container. Render `/contact/` as contact information with a direct email link and an explicit no-storage notice. Retain Django/Gunicorn as an opt-in Compose `rollback` profile and continue running its tests in CI.

## Options considered

### Keep Django as the default

| Dimension | Assessment |
|---|---|
| Complexity | Medium: two adapters remain equally prominent |
| Security | Mature defaults, but legacy templates depend on broader third-party assets |
| Maintenance | Higher because new typed APIs still live in FastAPI |
| Rollback | Immediate |

### Make FastAPI the default and retain Django rollback

| Dimension | Assessment |
|---|---|
| Complexity | Low for normal operation; rollback remains explicit |
| Security | Strict CSP, trusted hosts, security headers, and no deceptive contact submission |
| Maintenance | Lower because the default adapter matches the typed API surface |
| Rollback | Available through a tested profile |

### Remove Django immediately

| Dimension | Assessment |
|---|---|
| Complexity | Lowest long term |
| Security | Smaller runtime surface |
| Maintenance | Requires deleting templates, settings, tests, and dependencies now |
| Rollback | No application-level fallback |

## Trade-off analysis

The staged cutover provides a clear default without coupling rollback removal to the release. Keeping Django temporarily costs dependency and CI time, but preserves a low-risk fallback while FastAPI becomes the production entry point. Immediate Django removal should be a separate, evidence-based cleanup after the new default has operated successfully.

## Consequences

- `docker compose up web` serves FastAPI on loopback port 8000.
- Django requires the `rollback` profile, a unique secret, and uses loopback port 8001.
- CI continues to verify both adapters and the shared domain services.
- The site does not accept contact submissions until a real delivery channel, abuse controls, retention policy, and privacy notice are designed.
- Django dependencies and legacy templates remain temporarily and should be reviewed for removal after the cutover stabilizes.

## Action items

1. Monitor the FastAPI health endpoint and application logs in the target environment.
2. Exercise the documented rollback command before production deployment.
3. Decide whether to remove Django after an agreed stabilization period.
