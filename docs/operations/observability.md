# Co-Tour observability and rollback runbook

## Runtime contract

FastAPI writes one JSON object to standard output for every HTTP request. The schema is versioned and intentionally excludes query strings, request bodies, client IP addresses, and user-agent values.

| Field | Meaning |
|---|---|
| `schema_version` | Log contract version, currently `1` |
| `timestamp` | UTC completion timestamp |
| `event` | `http_request` |
| `service` | `cotour-web` |
| `request_id` | Generated UUID or validated inbound correlation ID |
| `method` | HTTP method |
| `route` | FastAPI route template; unmatched paths use `__unmatched__` |
| `status_code` | Final HTTP status |
| `duration_ms` | End-to-end request duration in milliseconds |

Every response includes `X-Request-ID`. An inbound ID is accepted only when it is 8–128 characters and contains letters, numbers, `.`, `_`, or `-`; otherwise the application generates a UUID. Use this value to correlate a user-visible failure with its request log.

## Health endpoints

- `GET /health` is the process liveness probe. It does not touch analytics artifacts.
- `GET /health/ready` verifies that the recommendation, forecast, and flow catalogs are available and non-empty. It returns HTTP 503 with a generic response when a required service is unavailable.
- The production container health check uses `/health/ready`, not an open-socket check.

## Golden signals

Derive the initial dashboard from `http_request` logs:

1. Traffic: count requests by `route` and `method` per minute.
2. Errors: count HTTP 5xx by route; chart 4xx separately because validation failures are not service failures.
3. Latency: p50, p95, and p99 of `duration_ms` by route.
4. Saturation: collect container CPU, memory, restart count, and health state from the deployment platform.

Keep `request_id` out of metric labels to avoid unbounded cardinality. It belongs in searchable logs only.

## Initial alerts

These thresholds are conservative starting points and must be tuned after real traffic establishes a baseline:

- Critical: readiness fails for three consecutive checks or the container restarts repeatedly within 10 minutes.
- Critical: HTTP 5xx exceeds 5% for 5 minutes with at least 20 requests.
- Warning: p95 latency exceeds 2 seconds for 10 minutes with at least 20 requests.
- Warning: container memory or CPU exceeds 85% for 15 minutes.
- Information: trusted-host rejections or validation 4xx increase sharply; investigate but do not page solely on these signals.

## Investigation

1. Confirm `/health` and `/health/ready` independently.
2. Find failing `http_request` events by status and route.
3. Use `request_id` to isolate the affected request without searching for user input.
4. Check container health, restarts, memory, and CPU.
5. Reproduce the route against the same image and artifact set.
6. If correctness, availability, or latency remains outside the thresholds, roll back.

## Rollback

Roll back at the release layer by redeploying the last verified immutable image or revision. Do not rebuild an old source checkout during an incident: rebuilding can resolve different dependencies or base-image layers. Record the active image digest before changing it, redeploy the known-good digest, then verify `/health`, `/health/ready`, and the affected route. Commit `c2a69cc` is the final verified revision before the Django adapter was retired.

Forward-fix only after the triggering issue is understood and covered by a regression test. A rollback must restore the complete application image and its matching analytics artifacts; the project no longer maintains a second web adapter.

## Stabilization evidence

On 2026-07-20, the merged production image passed all public FastAPI HTML routes, all three APIs, OpenAPI generation, static assets, validation behavior, trusted-host rejection, security headers, and the contact no-storage contract. The retired Django fallback also passed its historical compatibility checks before removal. The FastAPI container remained healthy and logged no runtime exception during the check.
