# Hotspot Forecast Migration Implementation Plan

> **For Codex:** Execute this plan task by task with the test-driven-development workflow.

**Goal:** Extract the tourist hotspot forecast into a framework-independent service and expose secure, server-rendered FastAPI HTML and typed JSON endpoints while retaining the Django route as the default fallback.

**Architecture:** A `cotour.forecasts` domain service owns CSV loading, month validation, coordinate joins, normalization, and ranking. Django and FastAPI consume the same immutable result objects. FastAPI renders CSP-safe static SVG maps, avoiding inline JavaScript and CDN dependencies.

**Tech Stack:** Python 3.12, pandas, Django 5.2, FastAPI, Pydantic 2, Jinja2, unittest.

---

### Task 1: Characterize the forecast domain

**Files:**
- Create: `web_app/tests/test_forecasts.py`
- Create: `web_app/cotour/forecasts.py`

1. Write failing tests for available months, default forecast results, deterministic ranking, normalization, and invalid months.
2. Run the focused test and confirm it fails because the service does not exist.
3. Implement immutable query/result types and a cached data service using repository-relative paths.
4. Run the focused test until it passes.
5. Commit the domain slice.

### Task 2: Move Django hotspot handling onto the service

**Files:**
- Modify: `web_app/webapp/tests.py`
- Modify: `web_app/webapp/views.py`
- Modify: `web_app/webapp/templates/webapp/tourist_hotspot_forecast.html`

1. Add failing Django tests for the default route and rejected month values.
2. Replace working-directory CSV reads and duplicate hotspot transformations with `ForecastService`.
3. Preserve the existing Django page contract and map presentation while deriving all data from the shared service.
4. Run the Django tests and commit the adapter migration.

### Task 3: Add FastAPI HTML and typed API routes

**Files:**
- Modify: `web_app/tests/test_fastapi_app.py`
- Modify: `web_app/cotour_web/app.py`
- Create: `web_app/cotour_web/templates/hotspot_forecast.html`
- Modify: `web_app/cotour_web/templates/base.html`
- Modify: `web_app/cotour_web/templates/home.html`

1. Add failing tests for the HTML page, typed JSON API, invalid months, and security headers.
2. Inject `ForecastService` into application state and add `/tourist_hotspot_forecast/` plus `/api/v1/hotspot-forecast`.
3. Render accessible, CSP-safe SVG maps and ranked results without client-side JavaScript.
4. Run the FastAPI and service tests and commit the route slice.

### Task 4: Document and verify the vertical slice

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-16-fastapi-migration.md`

1. Document migrated routes, API parameters, Django fallback, and the next migration boundary.
2. Run all service, FastAPI, Django, artifact, security, and dependency checks.
3. Review the diff for security, regression, and maintainability concerns.
4. Commit the documentation and verification updates.
