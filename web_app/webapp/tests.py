from django.test import TestCase
from django.urls import reverse


class SecurityResponseTests(TestCase):
    def test_traversal_request_is_rejected(self):
        response = self.client.get(
            reverse("tfa"),
            {
                "tfa_place_select": "../../Recommendation data/rec",
                "tfa_season_select": "dataset",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_security_headers_are_present(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])


class RecommendationViewTests(TestCase):
    def test_recommendation_page_uses_local_service(self):
        response = self.client.get(reverse("trs"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["RecommendationResults"]), 3)

    def test_invalid_recommendation_input_is_rejected(self):
        response = self.client.get(
            reverse("trs"), {"trs_preferences_select": "rooftops"}
        )

        self.assertEqual(response.status_code, 400)


class HotspotForecastViewTests(TestCase):
    def test_default_page_uses_shared_forecast_service(self):
        response = self.client.get(reverse("thf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_pred_date"], "Jul 2020")
        self.assertEqual(response.context["selected_hist_date"], "Apr 2020")
        self.assertEqual(len(response.context["top_10"]), 10)
        self.assertEqual(response.context["top_10"][0], "Tierpark Hellabrunn")

    def test_invalid_forecast_month_is_rejected(self):
        response = self.client.get(
            reverse("thf"), {"tfh_month_select": "Jun 2020"}
        )

        self.assertEqual(response.status_code, 400)


class TouristFlowViewTests(TestCase):
    def test_default_page_uses_shared_flow_service(self):
        response = self.client.get(reverse("tfa"))

        self.assertEqual(response.status_code, 200)
        result = response.context["flow_result"]
        self.assertEqual(result.place, "Olympiapark")
        self.assertEqual(result.season, "summer_pre_covid")
        self.assertEqual(len(result.attractions), 20)
        self.assertEqual(len(result.origins), 23)
        self.assertEqual(result.diagnostics[0].subject, "English Garden")

    def test_unknown_flow_place_is_rejected(self):
        response = self.client.get(
            reverse("tfa"), {"tfa_place_select": "Unknown Attraction"}
        )

        self.assertEqual(response.status_code, 400)

    def test_valid_empty_flow_selection_is_rendered(self):
        response = self.client.get(
            reverse("tfa"),
            {
                "tfa_place_select": "Bayerisches Nationalmuseum",
                "tfa_season_select": "winter_covid",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["flow_result"].origins, ())
