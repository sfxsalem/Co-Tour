# Co-Tour : Applied Machine Intelligence Project SS20

A tourism analysis, clustering and recommendation system for the post-COVID period in the city of Munich contributing to the management of the tourism flow of the city and the policies concerning COVID-19 in the region.


 * For a full description of the project, please read the project documentation included
 in the repository:

   ```https://gitlab.ldv.ei.tum.de/ami2020/group16/-/tree/master/docs```

 * To submit bug reports and feature suggestions, or track changes:

     ```https://gitlab.ldv.ei.tum.de/ami2020/group16/-/issues```

Getting Started
-------------
These instructions will get you a copy of the project up and running on your local machine
for development and testing purposes.

Clone this repo to your local machine using:

```
git clone https://gitlab.ldv.ei.tum.de/ami2020/group16.git
```
TripAdvisor Web Scraping App
-------------

* This project contains a web scraping app for TripAdvisor. This sub-project will help us
scrape information found in the travel-related website “TripAdvisor”.
Key factors such as Reviews, Ratings, Satisfaction  levels, Visit period, Origin of the visitor and Trip type (solo, couple, family, business and friends) of Munich’  tourist attractions and turning them into a database, helping us later to cluster these attractions and unveil the tourism patterns changes during the corona crisis. For further information about this sub-project, the Readme file can be found under :

    ```https://gitlab.ldv.ei.tum.de/ami2020/group16/-/tree/master/Tripadvisor_web_scraper```


Prerequisites
-------------

This project requires the following software:

 * Python 3.12
 * Docker with Docker Compose (optional)


Configuration
-------------

 * If the project is directly cloned from Gitlab, the database paths are already contained in the ./data directory and implemented in the code. In case of any changes, you can find the requested database in the according sub-directory ./data/...

 * Copy `.env.example` to `.env` and keep `.env` untracked. Production deployments must terminate TLS at a reverse proxy and configure the public host through `FASTAPI_ALLOWED_HOSTS`.

 * All the required packages and modules that don’t come as part of the python standard library are to be found in the requirements.txt file.



Local development
-----------------

FastAPI is the sole web adapter. It calls framework-independent recommendation, hotspot-forecast, and tourist-flow services in `web_app/cotour/`. Requests use validated, repository-relative local artifacts; recommendation requests no longer perform live geocoding or fit a clustering model on every request.

Create a virtual environment and install the reproducible web dependency lock:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r web_app/requirements.txt
```

Run FastAPI locally:

```bash
cd web_app
LOKY_MAX_CPU_COUNT=2 uvicorn cotour_web.app:app --reload
```

The application is available at [http://localhost:8000](http://localhost:8000), its OpenAPI documentation at [http://localhost:8000/docs](http://localhost:8000/docs), liveness check at [http://localhost:8000/health](http://localhost:8000/health), and readiness check at [http://localhost:8000/health/ready](http://localhost:8000/health/ready). Every public route now has FastAPI parity:

- `/` — server-rendered home page
- `/tourism_recommendation_system/` and `POST /api/v1/recommendations`
- `/tourist_hotspot_forecast/` and `GET /api/v1/hotspot-forecast`
- `/tourist_flow_analysis/` and `GET /api/v1/tourist-flow`
- `/contact/` — project contact information; the site does not collect messages

The hotspot API accepts optional ISO month query parameters, for example:

```text
/api/v1/hotspot-forecast?predicted_month=2020-08-01&historical_month=2019-08-01
```

Only months exposed by the local forecast artifacts are accepted. Invalid or unavailable values return HTTP 422.

The tourist-flow API accepts repository-backed place and season values:

```text
/api/v1/tourist-flow?place=Olympiapark&season=summer_pre_covid
```

All 84 place/season combinations are validated. Seven COVID-period artifacts contain no origin observations and return an empty `origins` list rather than an error. The UI and API also expose a data diagnostic for the source coordinate that places English Garden outside Munich; that attraction is omitted from the Munich cluster map until the artifact is corrected.

Run the test suites from the repository root:

```bash
LOKY_MAX_CPU_COUNT=2 PYTHONPATH=web_app .venv/bin/python -m unittest discover -s web_app/tests -v
```

Container deployment
--------------------

The repository has one container service:

```bash
cp .env.example .env
docker compose up --build -d web
```

It is bound to the local loopback interface at [http://localhost:8000](http://localhost:8000); the development server is not used.

That service runs Uvicorn as the non-root container user. Release rollback redeploys a previously verified immutable image; there is no second application adapter or rollback profile.

Operations
----------

FastAPI emits privacy-conscious JSON request logs with route, status, duration, and a validated correlation ID. Every response returns `X-Request-ID`; query strings and request bodies are not logged. The production health check verifies the local analytics catalogs through `/health/ready`.

See the [observability and rollback runbook](docs/operations/observability.md) for the log schema, golden signals, initial alert thresholds, investigation flow, and rollback triggers.


Additional Features
-------------

You can use the web scraping app to create your own database. To do so please follow the instructions under:

```
https://gitlab.ldv.ei.tum.de/ami2020/group16/-/tree/master/Tripadvisor_web_scraper
```
## Run from python files
**Tourist flow analysis**
```
1- K-means_clustring.py
2- tourism_flow_data.py
3- visual K means.py
4- Geocoding.py
```
**Hotsport forcast**
```
1- hotspot_forecast_data.py
2- hotspot_forecast_train.py
3- hotspot_forecast_prediction.py
```
**Recommendation system**
```
1- K-means_recommendation_system.py
2- scoring_system_data.py
3- recommendation_system.py
```
## Versioning

We use [Gitlab](https://gitlab.ldv.ei.tum.de/) for versioning. For the versions available, see the [tags on this repository](https://gitlab.ldv.ei.tum.de/ami2020/group16/-/commits/master).

## Authors

* **Alaeddine Yacoub** - *alaeddine.yacoub@tum.de* -
* **Kheireddine Achour** - *kheireddine.achour@tum.de* -
* **Stephan Rappenpserger** - *stephan.rappenpserger@tum.de* -
* **Yosra Bahri** - *yosra.bahri@tum.de* -
* **Mohamed Mezghanni** - *mohamed.mezghanni@tum.de* -
* **Oumaima Zneidi** - *oumaima.zneidi@tum.de* -
* **Salem Sfaxi** - *salem.sfaxi@tum.de* -

## License

This project is licensed under the Chair For Data Processing
Technical University of Munich
