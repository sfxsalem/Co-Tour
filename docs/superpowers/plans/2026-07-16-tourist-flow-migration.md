# Tourist Flow Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract tourist-flow analysis into a deterministic framework-independent service and provide Django plus FastAPI HTML/API parity without weakening the strict FastAPI content-security policy.

**Architecture:** `cotour.flows.FlowService` is a deep two-operation façade (`options`, `analyze`) over repository-relative CSV artifacts. It returns immutable visualization-neutral data and explicit diagnostics. Django temporarily retains Folium as an adapter; a focused FastAPI router renders escaped, CSP-safe SVG and typed JSON.

**Tech Stack:** Python 3.12, pandas, Django 5.2, FastAPI, Pydantic 2, Jinja2, Folium (Django fallback only), unittest.

---

### Task 1: Build the flow domain boundary

**Files:**
- Create: `web_app/tests/test_flows.py`
- Create: `web_app/cotour/flows.py`

- [ ] **Step 1: Write failing domain tests**

Cover the repository-backed catalog, default analysis, all 84 place/season combinations, valid empty seasons, invalid selections, deterministic ordering, and the known out-of-Munich attraction diagnostic:

```python
result = service.analyze(FlowQuery())
self.assertEqual(result.place, "Olympiapark")
self.assertEqual(len(result.attractions), 20)
self.assertEqual(len(result.origins), 23)
self.assertAlmostEqual(result.origins[0].share_percent, 32.876712, places=6)
self.assertEqual(result.diagnostics[0].code, "attraction-outside-munich")
```

- [ ] **Step 2: Verify the focused test fails**

Run: `LOKY_MAX_CPU_COUNT=2 PYTHONPATH=web_app .venv/bin/python -m unittest tests.test_flows -v`

Expected: import failure because `cotour.flows` does not exist.

- [ ] **Step 3: Implement the service façade**

Define frozen, slotted `FlowQuery`, `SeasonOption`, `FlowOptions`, `AttractionCluster`, `VisitorOrigin`, `FlowDiagnostic`, and `FlowResult` dataclasses plus `FlowInputError` and `FlowDataError`. `FlowService(data_directory)` must:

```python
def options(self) -> FlowOptions: ...
def analyze(self, query: FlowQuery = FlowQuery()) -> FlowResult: ...
```

Resolve only beneath the injected root; validate exact schemas, duplicate keys, finite numeric values, cluster integers, coordinate ranges, percentages, and non-empty totals near 100%. Build the season manifest from approved catalog values before request handling. Treat header-only files as `origins=()`. Join clusters and coordinates one-to-one, sort attractions by `(cluster, name)` and origins by `(-share_percent, country)`, exclude attraction coordinates outside the Munich bounds `(47.9..48.4, 11.3..11.8)`, and emit an explicit diagnostic naming the excluded attraction.

- [ ] **Step 4: Verify domain tests pass**

Run the command from Step 2 and expect all flow tests to pass.

- [ ] **Step 5: Commit the domain slice**

```bash
git add docs/superpowers/plans/2026-07-16-tourist-flow-migration.md web_app/cotour/flows.py web_app/tests/test_flows.py
git commit -m "Extract tourist flow domain service"
```

### Task 2: Move Django onto the shared service

**Files:**
- Modify: `web_app/webapp/tests.py`
- Modify: `web_app/webapp/views.py`
- Modify: `web_app/webapp/templates/webapp/tourist_flow_analysis.html`
- Modify: `web_app/webapp/static/webapp/js/tfa.js`

- [ ] **Step 1: Add failing Django adapter tests**

Assert the default page returns 20 rendered cluster inputs, 23 visitor origins, the coordinate diagnostic, and the existing selected values. Assert an unavailable place or season returns HTTP 400 and an empty valid season returns HTTP 200 with zero origins.

- [ ] **Step 2: Verify adapter tests fail against the legacy view**

Run:

```bash
LOKY_MAX_CPU_COUNT=2 DJANGO_SECRET_KEY='test-secret-that-is-at-least-fifty-characters-long' DJANGO_DEBUG=true DJANGO_SECURE_SSL_REDIRECT=false .venv/bin/python web_app/manage.py test webapp.tests.TouristFlowViewTests -v 2
```

Expected: missing shared-service context and legacy exception behavior.

- [ ] **Step 3: Replace Django data orchestration**

Construct one `FlowService(settings.BASE_DIR / "data")`, translate the legacy GET names to `FlowQuery`, map `FlowInputError` to `SuspiciousOperation`, and render Folium figures strictly from immutable result tuples. Use a fixed cluster palette and bounded origin radius `4 + min(12, share_percent ** 0.5 * 2)`. Remove relative-path flow loaders, broad exception handling, random NumPy colors, and the redundant/broken Ajax request; retain a normal GET form.

- [ ] **Step 4: Verify all Django tests pass**

Run the focused command, then `... manage.py test webapp`, expecting zero failures.

- [ ] **Step 5: Commit the Django adapter**

```bash
git add web_app/webapp
git commit -m "Use flow service from Django analysis view"
```

### Task 3: Add FastAPI flow HTML and API routes

**Files:**
- Create: `web_app/cotour_web/flow_routes.py`
- Create: `web_app/cotour_web/templates/flow_analysis.html`
- Modify: `web_app/cotour_web/app.py`
- Modify: `web_app/cotour_web/templates/base.html`
- Modify: `web_app/cotour_web/templates/home.html`
- Modify: `web_app/webapp/static/webapp/css/fastapi.css`
- Modify: `web_app/tests/test_fastapi_app.py`

- [ ] **Step 1: Add failing FastAPI parity tests**

Require `GET /tourist_flow_analysis/` to render two accessible SVGs, 20 cluster markers, 23 origin markers, escaped diagnostics, and no inline-script CSP exception. Require `GET /api/v1/tourist-flow` to return the selected place/season and typed points. Assert invalid selections return 422 and a valid empty season returns 200.

- [ ] **Step 2: Verify the new routes return 404**

Run the focused FastAPI test methods and confirm the route assertions fail with 404.

- [ ] **Step 3: Implement the isolated FastAPI router**

Create an `APIRouter` with Pydantic response models mirroring the domain result. Keep projection and fixed palette in `flow_routes.py`: local attraction coordinates project into a Munich SVG viewport; global origins use an equirectangular world projection; origin radii are bounded. Register `FlowService(WEB_APP_DIRECTORY / "data")` on application state and include the router. The Jinja page uses regular GET forms, escaped text, SVG `<title>` elements, and a visible no-data state.

- [ ] **Step 4: Verify route and full service tests pass**

Run `LOKY_MAX_CPU_COUNT=2 PYTHONPATH=web_app .venv/bin/python -m unittest discover -s web_app/tests -v` and expect zero failures.

- [ ] **Step 5: Commit the FastAPI slice**

```bash
git add web_app/cotour_web web_app/webapp/static/webapp/css/fastapi.css web_app/tests/test_fastapi_app.py
git commit -m "Add FastAPI tourist flow slice"
```

### Task 4: Document, review, and verify

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-07-16-fastapi-migration.md`

- [ ] **Step 1: Update migration documentation**

Document the HTML/API routes, `place` and `season` parameters, empty-result behavior, explicit data diagnostics, and that only the contact page remains before the default service switch.

- [ ] **Step 2: Run the complete release gate**

Run all service/FastAPI tests, Django tests under production static settings, artifact tests, compilation, `manage.py check --deploy`, Bandit, pip-audit, secret-pattern scan, and `git diff --check`.

- [ ] **Step 3: Review the complete branch diff**

Review security, correctness, performance, accessibility, API compatibility, deterministic output, empty files, malformed input, and data-diagnostic visibility. Fix findings test-first and rerun the gate.

- [ ] **Step 4: Commit documentation/review updates**

```bash
git add README.md docs/superpowers/plans/2026-07-16-fastapi-migration.md
git commit -m "Document tourist flow migration parity"
```
