from unittest import TestCase

from fastapi.testclient import TestClient

from cotour_web.app import create_app


class FastAPIApplicationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def test_health_endpoint_and_security_headers(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])

    def test_rejects_untrusted_host(self):
        response = self.client.get("/health", headers={"Host": "attacker.example"})

        self.assertEqual(response.status_code, 400)

    def test_home_page_is_server_rendered(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("CO-TOUR", response.text)
        self.assertIn("integrity=\"sha384-", response.text)

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
