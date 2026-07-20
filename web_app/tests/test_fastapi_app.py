import csv
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import quote
from uuid import UUID

from fastapi.testclient import TestClient

from cotour.artifacts import ArtifactBundle
from cotour_web.app import create_app
from cotour_web.observability import request_logger


WEB_APP_DIRECTORY = Path(__file__).resolve().parents[1]


class FastAPIApplicationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())
        request_logger.handlers.clear()

    def test_health_endpoint_and_security_headers(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])

    def test_readiness_endpoint_checks_application_services(self):
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_default_services_share_one_validated_artifact_bundle(self):
        bundle = self.client.app.state.artifact_bundle

        self.assertIs(self.client.app.state.recommendation_service.artifacts, bundle)
        self.assertIs(self.client.app.state.forecast_service.artifacts, bundle)
        self.assertIs(self.client.app.state.flow_service.artifacts, bundle)

    def test_readiness_fails_closed_when_an_artifact_service_is_unavailable(self):
        with patch.object(
            ArtifactBundle, "assert_ready", side_effect=RuntimeError("private detail")
        ):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(), {"detail": "Application dependencies are unavailable"}
        )
        self.assertNotIn("private detail", response.text)

    def test_requests_receive_a_correlation_id(self):
        generated = self.client.get("/health")
        supplied = self.client.get(
            "/health", headers={"X-Request-ID": "release-check-20260720"}
        )

        UUID(generated.headers["x-request-id"])
        self.assertEqual(
            supplied.headers["x-request-id"], "release-check-20260720"
        )

    def test_invalid_correlation_id_is_not_reflected(self):
        response = self.client.get(
            "/health", headers={"X-Request-ID": "attacker value"}
        )

        UUID(response.headers["x-request-id"])
        self.assertNotEqual(response.headers["x-request-id"], "attacker value")

    def test_request_log_is_structured_and_avoids_query_values(self):
        with self.assertLogs("cotour.requests", level="INFO") as captured:
            response = self.client.get(
                "/api/v1/tourist-flow?place=Olympiapark",
                headers={"X-Request-ID": "structured-log-check"},
            )

        self.assertEqual(response.status_code, 200)
        event = json.loads(captured.output[-1].split(":", maxsplit=2)[-1])
        self.assertEqual(event["event"], "http_request")
        self.assertEqual(event["request_id"], "structured-log-check")
        self.assertEqual(event["method"], "GET")
        self.assertEqual(event["route"], "/api/v1/tourist-flow")
        self.assertEqual(event["status_code"], 200)
        self.assertGreaterEqual(event["duration_ms"], 0)
        self.assertNotIn("query", event)

    def test_unmatched_paths_use_a_bounded_log_route(self):
        with self.assertLogs("cotour.requests", level="INFO") as captured:
            response = self.client.get("/not-a-real-user-supplied-path")

        self.assertEqual(response.status_code, 404)
        event = json.loads(captured.output[-1].split(":", maxsplit=2)[-1])
        self.assertEqual(event["route"], "__unmatched__")

    def test_unhandled_errors_are_generic_correlated_and_structured(self):
        failing_app = create_app()

        @failing_app.get("/test-failure")
        def fail_for_test():
            raise RuntimeError("private user-derived detail")

        client = TestClient(failing_app)
        request_logger.handlers.clear()
        with self.assertLogs("cotour.requests", level="ERROR") as captured:
            response = client.get(
                "/test-failure", headers={"X-Request-ID": "failure-check-20260720"}
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Internal server error"})
        self.assertEqual(response.headers["x-request-id"], "failure-check-20260720")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        event = json.loads(captured.output[-1].split(":", maxsplit=2)[-1])
        self.assertEqual(event["error_type"], "RuntimeError")
        self.assertTrue(event["stack"])
        self.assertNotIn("private user-derived detail", captured.output[-1])

    def test_rejects_untrusted_host(self):
        response = self.client.get("/health", headers={"Host": "attacker.example"})

        self.assertEqual(response.status_code, 400)

    def test_home_page_is_server_rendered(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("CO-TOUR", response.text)
        self.assertIn("integrity=\"sha384-", response.text)

    def test_fastapi_owns_its_static_stylesheet(self):
        response = self.client.get("/static/css/fastapi.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn("--accent", response.text)

    def test_every_recommendation_catalog_place_has_an_image(self):
        catalog_path = (
            WEB_APP_DIRECTORY / "data" / "Recommendation data" / "rec_dataset.csv"
        )
        with catalog_path.open(newline="") as catalog:
            places = {row["place"] for row in csv.DictReader(catalog)}

        self.assertEqual(len(places), 23)
        for place in sorted(places):
            with self.subTest(place=place):
                response = self.client.get(f"/static/img/{quote(place)}.jpg")
                self.assertEqual(response.status_code, 200)

    def test_contact_page_is_server_rendered_without_a_dead_form(self):
        response = self.client.get("/contact/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Contact CO-TOUR", response.text)
        self.assertIn("mailto:ami.group16@tum.de", response.text)
        self.assertNotIn("<form", response.text.lower())

    def test_primary_navigation_links_to_contact_page(self):
        response = self.client.get("/")

        self.assertIn('href="/contact/"', response.text)

    def test_recommendation_page_is_server_rendered(self):
        response = self.client.get("/tourism_recommendation_system/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Recommendation System", response.text)
        self.assertEqual(response.text.count('data-testid="recommendation"'), 3)

    def test_recommendation_api_returns_typed_results(self):
        response = self.client.post("/api/v1/recommendations", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["recommendations"]), 3)
        self.assertEqual(
            [item["rank"] for item in payload["recommendations"]], [1, 2, 3]
        )

    def test_recommendation_api_rejects_unsupported_domain_value(self):
        response = self.client.post(
            "/api/v1/recommendations", json={"preference": "rooftops"}
        )

        self.assertEqual(response.status_code, 422)

    def test_htmx_form_returns_only_results_fragment(self):
        response = self.client.post(
            "/tourism_recommendation_system/",
            data={
                "country": "Tunisia",
                "german_city": "Munich",
                "visit_type": "solo",
                "accommodation": "Maxvorstadt",
                "visit_date": "2020-08-10",
                "preference": "outdoors",
            },
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<!doctype html>", response.text.lower())
        self.assertEqual(response.text.count('data-testid="recommendation"'), 3)

    def test_standard_form_returns_complete_page(self):
        response = self.client.post(
            "/tourism_recommendation_system/",
            data={
                "country": "Tunisia",
                "german_city": "Munich",
                "visit_type": "solo",
                "accommodation": "Maxvorstadt",
                "visit_date": "2020-08-10",
                "preference": "outdoors",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("<!doctype html>", response.text.lower())

    def test_malformed_form_returns_validation_error(self):
        response = self.client.post(
            "/tourism_recommendation_system/",
            data={
                "country": "",
                "german_city": "Munich",
                "visit_type": "solo",
                "accommodation": "Maxvorstadt",
                "visit_date": "2020-08-10",
                "preference": "outdoors",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_hotspot_forecast_page_is_server_rendered(self):
        response = self.client.get("/tourist_hotspot_forecast/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Tourist Hotspot Forecast", response.text)
        self.assertIn('<svg role="img"', response.text)
        self.assertEqual(response.text.count('data-testid="forecast-hotspot"'), 22)
        self.assertIn("Tierpark Hellabrunn", response.text)

    def test_hotspot_forecast_api_returns_typed_results(self):
        response = self.client.get("/api/v1/hotspot-forecast")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["predicted_month"], "2020-07-01")
        self.assertEqual(payload["historical_month"], "2020-04-01")
        self.assertEqual(len(payload["predicted"]), 22)
        self.assertEqual(len(payload["historical"]), 22)
        self.assertEqual(payload["top_attractions"][0], "Tierpark Hellabrunn")
        self.assertEqual(payload["predicted"][0]["color"], "darkred")

    def test_hotspot_routes_reject_unavailable_months(self):
        for path in (
            "/tourist_hotspot_forecast/?predicted_month=2020-06-01",
            "/api/v1/hotspot-forecast?historical_month=2020-07-01",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 422)

    def test_hotspot_page_keeps_strict_script_policy(self):
        response = self.client.get("/tourist_hotspot_forecast/")

        policy = response.headers["content-security-policy"]
        self.assertIn("script-src 'self' https://unpkg.com", policy)
        self.assertNotIn("'unsafe-inline'", policy)

    def test_tourist_flow_page_is_server_rendered(self):
        response = self.client.get("/tourist_flow_analysis/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Tourist Flow Analysis", response.text)
        self.assertEqual(response.text.count('<svg role="img"'), 2)
        self.assertEqual(response.text.count('data-testid="cluster-point"'), 20)
        self.assertEqual(response.text.count('data-testid="origin-point"'), 23)
        self.assertEqual(response.text.count('data-testid="cluster-row"'), 20)
        self.assertEqual(response.text.count('data-testid="origin-row"'), 23)
        self.assertIn("English Garden", response.text)

    def test_tourist_flow_api_returns_typed_results(self):
        response = self.client.get("/api/v1/tourist-flow")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["place"], "Olympiapark")
        self.assertEqual(payload["season"], "summer_pre_covid")
        self.assertEqual(len(payload["attractions"]), 20)
        self.assertEqual(len(payload["origins"]), 23)
        self.assertEqual(payload["origins"][0]["country"], "Germany")
        self.assertEqual(payload["diagnostics"][0]["subject"], "English Garden")

    def test_tourist_flow_routes_reject_unknown_options(self):
        for path in (
            "/tourist_flow_analysis/?place=Unknown%20Attraction",
            "/api/v1/tourist-flow?season=monsoon",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 422)

    def test_tourist_flow_routes_support_valid_empty_season(self):
        query = "place=Bayerisches%20Nationalmuseum&season=winter_covid"
        api_response = self.client.get(f"/api/v1/tourist-flow?{query}")
        page_response = self.client.get(f"/tourist_flow_analysis/?{query}")

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["origins"], [])
        self.assertEqual(page_response.status_code, 200)
        self.assertIn("No visitor-origin data", page_response.text)

    def test_tourist_flow_page_keeps_strict_script_policy(self):
        response = self.client.get("/tourist_flow_analysis/")

        self.assertNotIn(
            "'unsafe-inline'", response.headers["content-security-policy"]
        )
