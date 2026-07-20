# FastAPI Migration Implementation Plan

> **Historical plan:** This migration is complete. ADR-0002 retired Django, its commands, and the rollback profile; the details below are retained as an implementation record only.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a production-ready FastAPI/Jinja entry point for Co-Tour's recommendation flow while retaining Django as a tested rollback path.

**Architecture:** Move recommendation behavior behind a framework-independent `RecommendationService` that owns artifact loading, input validation, scoring, and result construction. Django and FastAPI become thin adapters over the same service; FastAPI initially serves the home page, recommendation page, JSON recommendation API, health endpoint, static assets, and security headers.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Jinja2, HTMX-ready HTML, Pandas, scikit-learn, pytest/unittest, Django 5.2 retained during migration.

## Migration status after phase 4

The recommendation, tourist-hotspot, tourist-flow, and contact slices are complete. Phase 4 adds an honest, server-rendered contact page without the legacy dead form and switches the default container from Django/Gunicorn to FastAPI/Uvicorn. Django remains tested and available through the explicit `rollback` Compose profile.

## Global Constraints

- Preserve the existing Django routes and security tests during the migration.
- Do not perform live geocoding in request handlers.
- Resolve every artifact path from the application root, never the process working directory.
- Validate country, city, visit type, district, preference, and visit month before analytics work begins.
- Cache immutable source artifacts and the fitted clustering model; copy mutable frames per request.
- Keep deployment bound to port 8000 and retain the non-root container user.

---

### Task 1: Framework-independent recommendation service

**Files:**
- Create: `web_app/cotour/__init__.py`
- Create: `web_app/cotour/recommendations.py`
- Create: `web_app/tests/__init__.py`
- Create: `web_app/tests/test_recommendations.py`

**Interfaces:**
- Consumes: CSV artifacts under `web_app/data`.
- Produces: `RecommendationQuery`, `Recommendation`, `RecommendationOptions`, and `RecommendationService.recommend(query)`.

- [ ] **Step 1: Write failing domain tests**

```python
def test_classifies_origin_without_network():
    assert classify_origin("Germany", "Munich") == "provenance_Munich"
    assert classify_origin("Germany", "Berlin") == "provenance_outside Munich"
    assert classify_origin("France", None) == "provenance_EU apart from GER"
    assert classify_origin("Tunisia", None) == "provenance_Outisde EU"

def test_recommend_returns_three_ranked_attractions(service):
    results = service.recommend(RecommendationQuery())
    assert len(results) == 3
    assert all(result.name and result.address for result in results)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m unittest web_app/tests/test_recommendations.py -v`
Expected: FAIL because `cotour.recommendations` does not exist.

- [ ] **Step 3: Implement the service boundary**

Implement frozen dataclasses for validated inputs/results, deterministic origin classification, cached CSV/model loading, vectorized preference scoring, month lookup, and top-three result assembly. Raise `RecommendationInputError` for values outside the repository-backed option lists.

- [ ] **Step 4: Run domain tests and verify GREEN**

Run: `.venv/bin/python -m unittest web_app/tests/test_recommendations.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web_app/cotour web_app/tests
git commit -m "refactor: extract recommendation service"
```

### Task 2: Django adapter

**Files:**
- Modify: `web_app/webapp/views.py`
- Modify: `web_app/webapp/tests.py`

**Interfaces:**
- Consumes: `RecommendationService.recommend()` and `.options()` from Task 1.
- Produces: the existing `TrsView` context keys and route behavior.

- [ ] **Step 1: Add a failing Django adapter test**

```python
def test_recommendation_page_uses_local_service(self):
    response = self.client.get(reverse("trs"))
    self.assertEqual(response.status_code, 200)
    self.assertEqual(len(response.context["RecommendationResults"]), 3)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `DJANGO_SECRET_KEY=test-only DJANGO_DEBUG=1 .venv/bin/python web_app/manage.py test webapp.tests.RecommendationViewTests -v 2`
Expected: FAIL because the existing view attempts live geocoding.

- [ ] **Step 3: Replace Django recommendation orchestration**

Build a `RecommendationQuery` from `request.GET`, call the shared service, and map results/options into the existing template keys. Convert `RecommendationInputError` to `SuspiciousOperation` so invalid inputs receive HTTP 400.

- [ ] **Step 4: Run all Django tests and verify GREEN**

Run: `DJANGO_SECRET_KEY=test-only DJANGO_DEBUG=1 .venv/bin/python web_app/manage.py test -v 2`
Expected: PASS with no network access.

- [ ] **Step 5: Commit**

```bash
git add web_app/webapp/views.py web_app/webapp/tests.py
git commit -m "refactor: use shared recommendation service in django"
```

### Task 3: FastAPI/Jinja vertical slice

**Files:**
- Create: `web_app/cotour_web/__init__.py`
- Create: `web_app/cotour_web/app.py`
- Create: `web_app/cotour_web/templates/base.html`
- Create: `web_app/cotour_web/templates/home.html`
- Create: `web_app/cotour_web/templates/recommendations.html`
- Create: `web_app/tests/test_fastapi_app.py`
- Modify: `web_app/requirements.in`
- Modify: `web_app/requirements.txt`

**Interfaces:**
- Consumes: shared recommendation domain objects from Task 1.
- Produces: `create_app(service=None)`, `GET /`, `GET /health`, `GET /tourism_recommendation_system/`, and `POST /api/v1/recommendations`.

- [ ] **Step 1: Add FastAPI and test dependencies to the input lock**

Add `fastapi>=0.116,<1`, `httpx>=0.28,<1`, `python-multipart>=0.0.20,<1`, and `uvicorn[standard]>=0.35,<1`, then regenerate the hashed lock with `pip-compile`.

- [ ] **Step 2: Write failing adapter tests**

```python
def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}

def test_recommendation_api(client):
    response = client.post("/api/v1/recommendations", json={})
    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 3
```

- [ ] **Step 3: Run tests and verify RED**

Run: `.venv/bin/python -m unittest web_app/tests/test_fastapi_app.py -v`
Expected: FAIL because `cotour_web.app` does not exist.

- [ ] **Step 4: Implement the FastAPI adapter and templates**

Create routes using typed Pydantic query models, inject the recommendation service through `app.state`, mount `/static`, render Jinja templates, and add CSP, frame, content-type, and referrer security headers. The HTML form posts with HTMX when available and remains functional as a standard form submission.

- [ ] **Step 5: Run FastAPI and full tests and verify GREEN**

Run: `.venv/bin/python -m unittest discover -s web_app/tests -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web_app/cotour_web web_app/tests web_app/requirements.in web_app/requirements.txt
git commit -m "feat: add fastapi recommendation vertical slice"
```

### Task 4: Deployment, CI, and handoff

**Files:**
- Modify: `web_app/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.github/workflows/security.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `cotour_web.app:app` ASGI application.
- Produces: documented local, container, test, and rollback commands.

- [ ] **Step 1: Add deployment verification**

Run FastAPI tests in CI, change the container command to `uvicorn cotour_web.app:app --host 0.0.0.0 --port 8000 --workers 2`, and keep the existing socket health check.

- [ ] **Step 2: Document the staged migration**

Document `.venv` setup, FastAPI launch, `/docs`, tests, Docker launch, migrated routes, and the temporary Django rollback command.

- [ ] **Step 3: Run full verification**

Run Django tests, service/FastAPI tests, Django deployment checks, compile checks, and `git diff --check`.

- [ ] **Step 4: Commit**

```bash
git add web_app/Dockerfile docker-compose.yml .github/workflows/security.yml README.md
git commit -m "chore: deploy fastapi vertical slice"
```
