from django.core.exceptions import SuspiciousOperation
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .views import resolve_season_dataset


class SeasonDatasetPathTests(SimpleTestCase):
    def test_valid_dataset_stays_inside_seasons_directory(self):
        dataset = resolve_season_dataset("Olympiapark", "summer_pre_covid")

        self.assertTrue(dataset.is_file())
        self.assertIn("Seasons", dataset.parts)

    def test_rejects_place_path_traversal(self):
        with self.assertRaises(SuspiciousOperation):
            resolve_season_dataset("../../Recommendation data/rec", "dataset")

    def test_rejects_unknown_season(self):
        with self.assertRaises(SuspiciousOperation):
            resolve_season_dataset("Olympiapark", "../../private")


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
