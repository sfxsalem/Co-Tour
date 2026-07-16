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
